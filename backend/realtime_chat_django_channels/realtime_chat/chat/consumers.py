"""
WebSocket Consumer for Real-Time Chat.

Each browser WebSocket connection maps to one ChatConsumer instance.
Django Channels routes incoming WS traffic here via chat/routing.py.

Message flow:
  Browser  ─WS─►  ChatConsumer.receive()  ──►  channel layer group  ──►  all room consumers
"""

import json
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Handles a single WebSocket connection for a chat room.

    URL pattern: ws://host/ws/chat/<room_slug>/
    Auth:        JWT token validated by JWTAuthMiddlewareStack (see middleware.py)
    """

    # ─────────────────────────── connection lifecycle ───────────────────────────

    async def connect(self):
        """Called when a WebSocket handshake is initiated."""
        self.room_slug = self.scope['url_route']['kwargs']['room_slug']
        self.room_group_name = f'chat_{self.room_slug}'
        self.user = self.scope['user']

        # Reject anonymous connections
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Verify room membership
        if not await self.is_room_member():
            await self.close(code=4003)
            return

        # Join the room's channel layer group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Join a personal group for notifications (e.g. DMs)
        self.user_group_name = f'user_{self.user.id}'
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )

        await self.accept()

        # Mark user online
        await self.set_user_online(True)

        # Broadcast presence to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_presence',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_online': True,
            }
        )

        # Send recent message history to the newly connected client
        messages = await self.get_recent_messages()
        await self.send(text_data=json.dumps({
            'type': 'message_history',
            'messages': messages,
        }))

    async def disconnect(self, close_code):
        """Called when the WebSocket closes."""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )

        if hasattr(self, 'user') and self.user.is_authenticated:
            await self.set_user_online(False)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_presence',
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'is_online': False,
                }
            )

    # ─────────────────────────── receiving from browser ──────────────────────────

    async def receive(self, text_data):
        """
        Handles messages sent FROM the browser over WebSocket.

        Expected JSON payload:
        {
            "type": "chat_message" | "typing_start" | "typing_stop" | "mark_read" | "ping",
            "message": "...",          # for chat_message
            "message_id": 123,         # for mark_read
            "parent_id": 456           # optional, for replies
        }
        """
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON payload.")
            return

        message_type = data.get('type', 'chat_message')
        handlers = {
            'chat_message': self.handle_chat_message,
            'typing_start': self.handle_typing,
            'typing_stop': self.handle_typing,
            'mark_read': self.handle_mark_read,
            'ping': self.handle_ping,
        }

        handler = handlers.get(message_type)
        if handler:
            await handler(data)
        else:
            await self.send_error(f"Unknown message type: {message_type}")

    # ─────────────────────────── message handlers ────────────────────────────────

    async def handle_chat_message(self, data):
        content = data.get('message', '').strip()
        if not content:
            await self.send_error("Message cannot be empty.")
            return

        parent_id = data.get('parent_id')
        message = await self.save_message(content, parent_id)
        if not message:
            await self.send_error("Failed to save message.")
            return

        # Broadcast to all group members (including sender)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message_id': message['id'],
                'room_slug': self.room_slug,
                'content': message['content'],
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'sender_avatar': self.user.get_avatar_url(),
                'parent_id': message.get('parent_id'),
                'created_at': message['created_at'],
                'message_type': 'text',
            }
        )

    async def handle_typing(self, data):
        is_typing = data.get('type') == 'typing_start'
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_typing': is_typing,
            }
        )

    async def handle_mark_read(self, data):
        message_id = data.get('message_id')
        if message_id:
            success = await self.mark_message_read(message_id)
            if success:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'read_receipt',
                        'message_id': message_id,
                        'user_id': self.user.id,
                        'username': self.user.username,
                    }
                )

    async def handle_ping(self, data):
        await self.send(text_data=json.dumps({'type': 'pong', 'timestamp': datetime.utcnow().isoformat()}))

    # ─────────────────────────── group event handlers ────────────────────────────
    # These are called by channel_layer.group_send() — they SEND to the browser.

    async def chat_message(self, event):
        """Forward a new chat message to the WebSocket client."""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message_id': event['message_id'],
            'room_slug': event['room_slug'],
            'content': event['content'],
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'sender_avatar': event['sender_avatar'],
            'parent_id': event.get('parent_id'),
            'created_at': event['created_at'],
            'message_type': event.get('message_type', 'text'),
        }))

    async def typing_indicator(self, event):
        """Forward typing indicator (skip if it's from self)."""
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing_indicator',
                'user_id': event['user_id'],
                'username': event['username'],
                'is_typing': event['is_typing'],
            }))

    async def user_presence(self, event):
        """Forward online/offline status updates."""
        await self.send(text_data=json.dumps({
            'type': 'user_presence',
            'user_id': event['user_id'],
            'username': event['username'],
            'is_online': event['is_online'],
        }))

    async def read_receipt(self, event):
        """Forward read receipts."""
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'username': event['username'],
        }))

    async def message_deleted(self, event):
        """Notify clients that a message was deleted."""
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'message_id': event['message_id'],
        }))

    async def message_edited(self, event):
        """Notify clients that a message was edited."""
        await self.send(text_data=json.dumps({
            'type': 'message_edited',
            'message_id': event['message_id'],
            'new_content': event['new_content'],
        }))

    # ─────────────────────────── helpers ─────────────────────────────────────────

    async def send_error(self, error_message: str):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message,
        }))

    # ─────────────────────────── database helpers ─────────────────────────────────

    @database_sync_to_async
    def is_room_member(self):
        from .models import Room
        try:
            room = Room.objects.get(slug=self.room_slug)
            return room.members.filter(id=self.user.id).exists()
        except Room.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content: str, parent_id=None):
        from .models import Room, Message
        try:
            room = Room.objects.get(slug=self.room_slug)
            parent = Message.objects.get(id=parent_id) if parent_id else None
            msg = Message.objects.create(
                room=room,
                sender=self.user,
                content=content,
                parent=parent,
            )
            return {
                'id': msg.id,
                'content': msg.content,
                'created_at': msg.created_at.isoformat(),
                'parent_id': msg.parent_id,
            }
        except Exception:
            return None

    @database_sync_to_async
    def get_recent_messages(self, limit=50):
        from .models import Room
        try:
            room = Room.objects.get(slug=self.room_slug)
            messages = room.messages.filter(
                is_deleted=False
            ).select_related('sender').order_by('-created_at')[:limit]
            return [
                {
                    'id': m.id,
                    'content': m.content,
                    'sender_id': m.sender.id if m.sender else None,
                    'sender_username': m.sender.username if m.sender else 'Unknown',
                    'sender_avatar': m.sender.get_avatar_url() if m.sender else '',
                    'parent_id': m.parent_id,
                    'is_edited': m.is_edited,
                    'created_at': m.created_at.isoformat(),
                    'message_type': m.message_type,
                }
                for m in reversed(list(messages))
            ]
        except Exception:
            return []

    @database_sync_to_async
    def set_user_online(self, is_online: bool):
        self.user.update_online_status(is_online)

    @database_sync_to_async
    def mark_message_read(self, message_id: int):
        from .models import Message, MessageReadStatus
        try:
            message = Message.objects.get(id=message_id)
            MessageReadStatus.objects.get_or_create(
                message=message,
                user=self.user
            )
            return True
        except Exception:
            return False
