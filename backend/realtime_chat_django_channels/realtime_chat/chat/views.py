"""
REST API views for rooms and messages.
WebSocket handles real-time; REST handles CRUD + history.
"""

from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import Room, RoomMember, Message, MessageReadStatus
from .serializers import (
    RoomSerializer,
    RoomCreateSerializer,
    RoomMemberSerializer,
    MessageSerializer,
    MessageCreateSerializer,
    DirectRoomSerializer,
)
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

User = get_user_model()
channel_layer = get_channel_layer()


def broadcast_to_room(room_slug: str, event: dict):
    """Push a channel-layer event to all WebSocket clients in a room."""
    async_to_sync(channel_layer.group_send)(f'chat_{room_slug}', event)


# ─────────────────────────── Room Views ──────────────────────────────────────

@extend_schema(tags=['Rooms'])
class RoomListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/chat/rooms/  → List all rooms the user is a member of.
    POST /api/v1/chat/rooms/  → Create a new group room.
    """

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return RoomCreateSerializer
        return RoomSerializer

    def get_queryset(self):
        return Room.objects.filter(
            members=self.request.user
        ).prefetch_related('members', 'messages')

    def create(self, request, *args, **kwargs):
        serializer = RoomCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        room = serializer.save()
        return Response(
            RoomSerializer(room, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


@extend_schema(tags=['Rooms'])
class RoomDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/chat/rooms/<slug>/  → Room details
    PATCH  /api/v1/chat/rooms/<slug>/  → Update room (admin only)
    DELETE /api/v1/chat/rooms/<slug>/  → Delete room (admin only)
    """

    serializer_class = RoomSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return Room.objects.filter(members=self.request.user)

    def update(self, request, *args, **kwargs):
        room = self.get_object()
        # Only room admins can update
        if not RoomMember.objects.filter(
            room=room, user=request.user, role='admin'
        ).exists():
            return Response(
                {'error': 'Only admins can update the room.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)


@extend_schema(tags=['Rooms'])
class DirectRoomView(APIView):
    """
    POST /api/v1/chat/rooms/direct/
    Create or retrieve a 1-on-1 direct message room with another user.
    """

    def post(self, request):
        serializer = DirectRoomSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        target_user = serializer.validated_data['user_id']
        me = request.user

        # Check if a DM room between these two users already exists
        existing = Room.objects.filter(
            room_type='direct',
            members=me
        ).filter(members=target_user)

        if existing.exists():
            room = existing.first()
        else:
            # Create a new DM room
            slug = f"dm-{min(me.id, target_user.id)}-{max(me.id, target_user.id)}"
            room = Room.objects.create(
                name=f"{me.username} & {target_user.username}",
                slug=slug,
                room_type='direct',
                created_by=me,
            )
            RoomMember.objects.create(room=room, user=me, role='admin')
            RoomMember.objects.create(room=room, user=target_user, role='admin')

        return Response(
            RoomSerializer(room, context={'request': request}).data,
            status=status.HTTP_200_OK
        )


@extend_schema(tags=['Rooms'])
class RoomMembersView(generics.ListAPIView):
    """GET /api/v1/chat/rooms/<slug>/members/ → List room members."""

    serializer_class = RoomMemberSerializer

    def get_queryset(self):
        room = Room.objects.get(
            slug=self.kwargs['slug'],
            members=self.request.user
        )
        return RoomMember.objects.filter(room=room).select_related('user')


@extend_schema(tags=['Rooms'])
class AddMemberView(APIView):
    """POST /api/v1/chat/rooms/<slug>/members/add/ → Add user to room."""

    def post(self, request, slug):
        try:
            room = Room.objects.get(slug=slug)
        except Room.DoesNotExist:
            return Response({'error': 'Room not found.'}, status=404)

        # Must be admin
        if not RoomMember.objects.filter(
            room=room, user=request.user, role='admin'
        ).exists():
            return Response({'error': 'Only admins can add members.'}, status=403)

        user_id = request.data.get('user_id')
        try:
            new_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=404)

        _, created = RoomMember.objects.get_or_create(room=room, user=new_user)
        return Response({
            'message': f"{new_user.username} added to room.",
            'created': created
        })


@extend_schema(tags=['Rooms'])
class LeaveRoomView(APIView):
    """POST /api/v1/chat/rooms/<slug>/leave/ → Leave room."""

    def post(self, request, slug):
        try:
            room = Room.objects.get(slug=slug)
            membership = RoomMember.objects.get(room=room, user=request.user)
            membership.delete()
            return Response({'message': f"You left {room.name}."})
        except (Room.DoesNotExist, RoomMember.DoesNotExist):
            return Response({'error': 'Room or membership not found.'}, status=404)


# ─────────────────────────── Message Views ───────────────────────────────────

@extend_schema(tags=['Messages'])
class MessageListView(generics.ListAPIView):
    """
    GET /api/v1/chat/rooms/<slug>/messages/
    Paginated message history for a room (most recent last).
    """

    serializer_class = MessageSerializer

    def get_queryset(self):
        slug = self.kwargs['slug']
        room = Room.objects.get(slug=slug, members=self.request.user)
        return Message.objects.filter(
            room=room, is_deleted=False
        ).select_related('sender', 'parent__sender').order_by('created_at')


@extend_schema(tags=['Messages'])
class MessageCreateView(generics.CreateAPIView):
    """
    POST /api/v1/chat/messages/
    Send a message via REST (also broadcasts to WebSocket group).
    Prefer using WebSocket for real-time; this endpoint is for file uploads.
    """

    serializer_class = MessageCreateSerializer

    def perform_create(self, serializer):
        message = serializer.save(sender=self.request.user)
        # Broadcast to WebSocket clients in the room
        broadcast_to_room(message.room.slug, {
            'type': 'chat_message',
            'message_id': message.id,
            'room_slug': message.room.slug,
            'content': message.content,
            'sender_id': self.request.user.id,
            'sender_username': self.request.user.username,
            'sender_avatar': self.request.user.get_avatar_url(),
            'parent_id': message.parent_id,
            'created_at': message.created_at.isoformat(),
            'message_type': message.message_type,
        })
        return message


@extend_schema(tags=['Messages'])
class MessageDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    PATCH  /api/v1/chat/messages/<id>/  → Edit message (sender only)
    DELETE /api/v1/chat/messages/<id>/  → Soft-delete message (sender only)
    """

    serializer_class = MessageSerializer

    def get_queryset(self):
        return Message.objects.filter(sender=self.request.user)

    def update(self, request, *args, **kwargs):
        message = self.get_object()
        new_content = request.data.get('content', '').strip()
        if not new_content:
            return Response({'error': 'Content cannot be empty.'}, status=400)

        message.content = new_content
        message.is_edited = True
        message.save(update_fields=['content', 'is_edited', 'updated_at'])

        # Broadcast edit
        broadcast_to_room(message.room.slug, {
            'type': 'message_edited',
            'message_id': message.id,
            'new_content': new_content,
        })
        return Response(MessageSerializer(message, context={'request': request}).data)

    def destroy(self, request, *args, **kwargs):
        message = self.get_object()
        message.soft_delete()

        # Broadcast deletion
        broadcast_to_room(message.room.slug, {
            'type': 'message_deleted',
            'message_id': message.id,
        })
        return Response({'message': 'Message deleted.'})


@extend_schema(tags=['Messages'])
class MarkReadView(APIView):
    """POST /api/v1/chat/messages/<id>/read/ → Mark message as read."""

    def post(self, request, pk):
        try:
            message = Message.objects.get(id=pk)
            MessageReadStatus.objects.get_or_create(
                message=message,
                user=request.user
            )
            return Response({'message': 'Marked as read.'})
        except Message.DoesNotExist:
            return Response({'error': 'Message not found.'}, status=404)
