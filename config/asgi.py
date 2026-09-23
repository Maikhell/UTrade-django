import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import UTrade_app.routing 

application = ProtocolTypeRouter({
    # Standard HTTP requests
    "http": get_asgi_application(),
    
    # WebSocket (Chat) requests
    "websocket": AuthMiddlewareStack(
        URLRouter(
            UTrade_app.routing.websocket_urlpatterns
        )
    ),
})