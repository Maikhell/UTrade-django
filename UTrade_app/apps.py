from django.apps import AppConfig

class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'UTrade_app'
    
    def ready(self):
        import UTrade_app.signals