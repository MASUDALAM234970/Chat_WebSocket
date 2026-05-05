"""
WebSocket URL routing for the chat application.
Registered in asgi.py → ProtocolTypeRouter → websocket.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # ws://host/ws/chat/<room-slug>/?token=<jwt>
    re_path(r'ws/chat/(?P<room_slug>[\w-]+)/$', consumers.ChatConsumer.as_asgi()),
]
