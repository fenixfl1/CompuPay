# pylint: disable=import-outside-toplevel

from django.apps import AppConfig


class NoticationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"

    def ready(self):
        import notifications.signals
