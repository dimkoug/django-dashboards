"""Ticket auth for WebSockets.

The client connects with ?ticket=<one-time-ticket> (minted via the
JWT-authenticated /api/ws-ticket/ endpoint). No long-lived credential
ever appears in a WebSocket URL.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from .ws_tickets import consume_ticket

User = get_user_model()


@database_sync_to_async
def _resolve(token):
    user_id = consume_ticket(token)
    if user_id is None:
        return AnonymousUser()
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


class TicketAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get('query_string', b'').decode())
        ticket = (query.get('ticket') or [None])[0]
        scope['user'] = await _resolve(ticket)
        return await super().__call__(scope, receive, send)
