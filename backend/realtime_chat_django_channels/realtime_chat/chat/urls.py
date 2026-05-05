"""REST API URL patterns for the chat app."""

from django.urls import path
from .views import (
    RoomListCreateView,
    RoomDetailView,
    DirectRoomView,
    RoomMembersView,
    AddMemberView,
    LeaveRoomView,
    MessageListView,
    MessageCreateView,
    MessageDetailView,
    MarkReadView,
)

urlpatterns = [
    # ── Rooms ────────────────────────────────────────────
    path('rooms/', RoomListCreateView.as_view(), name='room-list-create'),
    path('rooms/direct/', DirectRoomView.as_view(), name='room-direct'),
    path('rooms/<slug:slug>/', RoomDetailView.as_view(), name='room-detail'),
    path('rooms/<slug:slug>/members/', RoomMembersView.as_view(), name='room-members'),
    path('rooms/<slug:slug>/members/add/', AddMemberView.as_view(), name='room-add-member'),
    path('rooms/<slug:slug>/leave/', LeaveRoomView.as_view(), name='room-leave'),
    path('rooms/<slug:slug>/messages/', MessageListView.as_view(), name='room-messages'),

    # ── Messages ─────────────────────────────────────────
    path('messages/', MessageCreateView.as_view(), name='message-create'),
    path('messages/<int:pk>/', MessageDetailView.as_view(), name='message-detail'),
    path('messages/<int:pk>/read/', MarkReadView.as_view(), name='message-read'),
]
