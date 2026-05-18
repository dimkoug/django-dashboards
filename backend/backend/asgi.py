"""
ASGI config for backend project.

Routes HTTP to Django and WebSocket to Channels (ticket-authenticated).
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Initialise Django before importing anything that touches models/consumers.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from dashboard.ws import websocket_urlpatterns  # noqa: E402
from dashboard.ws_auth import TicketAuthMiddleware  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': TicketAuthMiddleware(URLRouter(websocket_urlpatterns)),
})
