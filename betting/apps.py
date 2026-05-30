from django.apps import AppConfig


class BettingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'betting'
    verbose_name = 'Eventos y Apuestas'

    def ready(self):
        import betting.signals  # noqa: F401
