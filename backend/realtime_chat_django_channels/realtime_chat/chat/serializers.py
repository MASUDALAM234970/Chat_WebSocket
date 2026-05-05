"""
Serializers for Chat models: Room, Message, RoomMember.
"""

from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.utils.crypto import get_random_string
from rest_framework import serializers

from accounts.serializers import UserPublicSerializer
from .models import Room, RoomMember, Message, MessageReadStatus

User = get_user_model()


class RoomMemberSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = RoomMember
        fields = ['id', 'user', 'role', 'joined_at', 'is_muted']


class MessageSerializer(serializers.ModelSerializer):
    """Full message serializer with sender info."""

    sender = UserPublicSerializer(read_only=True)
    is_read = serializers.SerializerMethodField()
    reply_to = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'room', 'sender', 'content', 'message_type',
            'file', 'parent', 'reply_to', 'is_edited', 'is_deleted',
            'is_read', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'sender', 'is_edited', 'is_deleted', 'created_at', 'updated_at'
        ]

    def get_is_read(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return MessageReadStatus.objects.filter(
                message=obj, user=request.user
            ).exists()
        return False

    def get_reply_to(self, obj):
        if obj.parent:
            return {
                'id': obj.parent.id,
                'content': obj.parent.content[:100],
                'sender': obj.parent.sender.username if obj.parent.sender else 'Unknown'
            }
        return None


class MessageCreateSerializer(serializers.ModelSerializer):
    """Used when sending a new message."""

    class Meta:
        model = Message
        fields = ['room', 'content', 'message_type', 'file', 'parent']

    def validate_room(self, room):
        user = self.context['request'].user
        if not room.members.filter(id=user.id).exists():
            raise serializers.ValidationError("You are not a member of this room.")
        return room


class RoomSerializer(serializers.ModelSerializer):
    """Full room serializer with member count and last message."""

    members_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    created_by = UserPublicSerializer(read_only=True)

    class Meta:
        model = Room
        fields = [
            'id', 'name', 'slug', 'description', 'room_type',
            'created_by', 'members_count', 'last_message',
            'unread_count', 'is_private', 'avatar', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def get_members_count(self, obj):
        return obj.members.count()

    def get_last_message(self, obj):
        msg = obj.get_last_message()
        if msg:
            return {
                'id': msg.id,
                'content': msg.content[:100],
                'sender': msg.sender.username if msg.sender else 'Unknown',
                'created_at': msg.created_at,
            }
        return None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.get_unread_count(request.user)
        return 0


class RoomCreateSerializer(serializers.ModelSerializer):
    """Used when creating a new group room."""

    member_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        many=True,
        write_only=True,
        required=False
    )

    class Meta:
        model = Room
        fields = ['name', 'description', 'room_type', 'is_private', 'member_ids']

    def create(self, validated_data):
        member_ids = validated_data.pop('member_ids', [])
        creator = self.context['request'].user

        # Auto-generate slug
        base_slug = slugify(validated_data.get('name', 'room'))
        slug = f"{base_slug}-{get_random_string(6)}"
        validated_data['slug'] = slug
        validated_data['created_by'] = creator

        room = Room.objects.create(**validated_data)

        # Add creator as admin
        RoomMember.objects.create(room=room, user=creator, role='admin')

        # Add other members
        for user in member_ids:
            if user != creator:
                RoomMember.objects.get_or_create(room=room, user=user)

        return room


class DirectRoomSerializer(serializers.Serializer):
    """Create or get a direct message room between two users."""

    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    def validate_user_id(self, target_user):
        request_user = self.context['request'].user
        if target_user == request_user:
            raise serializers.ValidationError("Cannot start a DM with yourself.")
        return target_user
