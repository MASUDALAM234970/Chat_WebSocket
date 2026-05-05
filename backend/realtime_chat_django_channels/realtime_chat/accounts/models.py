"""
Custom User model for the chat application.
Extends AbstractUser with additional fields.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Extended user model with online status and avatar."""

    email = models.EmailField(unique=True)
    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True,
        default=None
    )
    bio = models.TextField(max_length=300, blank=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username} ({self.email})"

    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return f"https://ui-avatars.com/api/?name={self.username}&background=random"

    def update_online_status(self, is_online: bool):
        self.is_online = is_online
        if not is_online:
            self.last_seen = timezone.now()
        self.save(update_fields=['is_online', 'last_seen'])
