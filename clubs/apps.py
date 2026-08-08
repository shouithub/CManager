from django.apps import AppConfig
from django.utils.translation import gettext_lazy


class ClubsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'clubs'
    verbose_name = gettext_lazy('社团管理')

    def ready(self):
        import clubs.signals as signals  # noqa: F401
