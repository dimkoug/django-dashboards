"""Short-lived, single-use WebSocket tickets.

Browsers can't set Authorization headers on a WS handshake. Instead of
putting a long-lived JWT in the URL (logged by proxies, kept in history),
the client first POSTs to /api/ws-ticket/ (JWT-authenticated) to mint an
opaque ticket valid for ~30s and good for exactly one connection.
"""
import secrets

from django.core.cache import cache

_PREFIX = 'wsticket:'
TICKET_TTL = 30  # seconds


def issue_ticket(user_id):
    token = secrets.token_urlsafe(32)
    cache.set(_PREFIX + token, user_id, TICKET_TTL)
    return token


def consume_ticket(token):
    """Return the user id for a valid ticket and invalidate it
    (single use), or None."""
    if not token:
        return None
    key = _PREFIX + token
    user_id = cache.get(key)
    if user_id is None:
        return None
    cache.delete(key)
    return user_id
