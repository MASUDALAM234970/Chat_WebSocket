from django.contrib import admin
from .models import Room, RoomMember, Message, MessageReadStatus


class RoomMemberInline(admin.TabularInline):
    model = RoomMember
    extra = 0
    readonly_fields = ['joined_at']


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'room_type', 'is_private', 'created_by', 'created_at']
    list_filter = ['room_type', 'is_private']
    search_fields = ['name', 'slug']
    readonly_fields = ['slug', 'created_at', 'updated_at']
    inlines = [RoomMemberInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'room', 'sender', 'content_preview', 'message_type', 'is_deleted', 'created_at']
    list_filter = ['message_type', 'is_deleted']
    search_fields = ['content', 'sender__username', 'room__name']
    readonly_fields = ['created_at', 'updated_at']

    def content_preview(self, obj):
        return obj.content[:60]
    content_preview.short_description = 'Content'


@admin.register(RoomMember)
class RoomMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'room', 'role', 'joined_at']
    list_filter = ['role']
    search_fields = ['user__username', 'room__name']


@admin.register(MessageReadStatus)
class MessageReadStatusAdmin(admin.ModelAdmin):
    list_display = ['user', 'message', 'read_at']
    search_fields = ['user__username']
