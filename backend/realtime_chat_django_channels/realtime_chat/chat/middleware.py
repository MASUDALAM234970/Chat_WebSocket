"""
JWT Authentication Middleware for Django Channels WebSocket connections.

HTTP requests use DRF's JWTAuthentication in the Authorization header.
WebSocket connections cannot set headers, so the JWT token is passed as
a query parameter: ws://host/ws/chat/room-slug/?token=<access_token>

This middleware validates the token and populates scope['user'],
making it available inside ChatConsumer via self.scope['user'].
"""

from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from channels.auth import AuthMiddlewareStack
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from channels.db import database_sync_to_async

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_key: str):
    """
    Validate JWT access token and return the associated User.
    Returns AnonymousUser if validation fails.
    """
    try:
        token = AccessToken(token_key)
        user_id = token.get('user_id')
        user = User.objects.get(id=user_id)
        return user
    except (InvalidToken, TokenError, User.DoesNotExist, Exception):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Validates JWT token from WebSocket query string.

    Usage: connect to ws://host/ws/chat/<slug>/?token=<jwt_access_token>
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token_list = query_params.get('token', [])

        if token_list:
            token = token_list[0]
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """
    Wraps the inner router with JWT auth middleware.
    Use this in asgi.py to protect WebSocket routes.
    """
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))
