"""
ASGI config for realtime_chat project.
Configures Django Channels with WebSocket routing.
"""

import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realtime_chat.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from chat.middleware import JWTAuthMiddlewareStack
import chat.routing

application = ProtocolTypeRouter({
    # HTTP requests → standard Django ASGI app
    'http': get_asgi_application(),

    # WebSocket connections → Channels routing
    'websocket': AllowedHostsOriginValidator(
        JWTAuthMiddlewareStack(
            URLRouter(
                chat.routing.websocket_urlpatterns
            )
        )
    ),
})
