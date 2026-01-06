from django.apps import AppConfig


class ClubsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'clubs'
    verbose_name = '社团管理'

    def ready(self):
        import clubs.signals
