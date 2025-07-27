from django.apps import AppConfig


class SmartPropertyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'smart_property'
def ready(self):
    import smart_property.signals
