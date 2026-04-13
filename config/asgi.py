import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import UTrade_app.routing 

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

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