from django.apps import AppConfig


class YouthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.youth"
    verbose_name = "Profils Jeunes"

    def ready(self):
        from apps.youth.signals import connect_signals
        connect_signals()
