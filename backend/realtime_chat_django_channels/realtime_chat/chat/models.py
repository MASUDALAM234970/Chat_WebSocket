"""
Chat application models:
- Room: A chat room (group or direct message)
- RoomMember: Through model for room membership
- Message: Individual chat messages
- MessageReadStatus: Read receipts
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class Room(models.Model):
    """A chat room. Can be a group or a 1-on-1 direct message."""

    ROOM_TYPE_CHOICES = [
        ('group', 'Group'),
        ('direct', 'Direct Message'),
    ]

    name = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(unique=True, max_length=120)
    description = models.TextField(max_length=500, blank=True)
    room_type = models.CharField(
        max_length=10,
        choices=ROOM_TYPE_CHOICES,
        default='group'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_rooms'
    )
    members = models.ManyToManyField(
        User,
        through='RoomMember',
        related_name='rooms'
    )
    is_private = models.BooleanField(default=False)
    avatar = models.ImageField(
        upload_to='room_avatars/',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rooms'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.room_type})"

    def get_last_message(self):
        return self.messages.filter(is_deleted=False).last()

    def get_unread_count(self, user):
        """Return count of messages unread by `user`."""
        read_ids = MessageReadStatus.objects.filter(
            user=user, message__room=self
        ).values_list('message_id', flat=True)
        return self.messages.exclude(id__in=read_ids).exclude(sender=user).count()


class RoomMember(models.Model):
    """Tracks room membership and roles."""

    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('member', 'Member'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_muted = models.BooleanField(default=False)

    class Meta:
        db_table = 'room_members'
        unique_together = ['room', 'user']

    def __str__(self):
        return f"{self.user.username} in {self.room.name}"


class Message(models.Model):
    """A single message in a room."""

    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('system', 'System'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_messages'
    )
    content = models.TextField(blank=True)
    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPE_CHOICES,
        default='text'
    )
    file = models.FileField(upload_to='message_files/', null=True, blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies'
    )
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'messages'
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.room.name}] {self.sender}: {self.content[:40]}"

    def soft_delete(self):
        self.is_deleted = True
        self.content = "This message was deleted."
        self.save(update_fields=['is_deleted', 'content', 'updated_at'])


class MessageReadStatus(models.Model):
    """Tracks which messages each user has read (read receipts)."""

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='read_statuses'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='read_statuses'
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'message_read_statuses'
        unique_together = ['message', 'user']

    def __str__(self):
        return f"{self.user.username} read message #{self.message.id}"
