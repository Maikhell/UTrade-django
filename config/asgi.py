import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# 1. Initialize Django ASGI application FIRST
django_asgi_app = get_asgi_application()

# 2. Import channels components AFTER get_asgi_application()
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
import UTrade_app.routing

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(UTrade_app.routing.websocket_urlpatterns)
        ),
    }
)