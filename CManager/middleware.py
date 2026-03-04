from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.db.utils import OperationalError, ProgrammingError


class InitialSetupMiddleware:
    """首启引导中间件：如果还没有管理员账号，则强制进入 OOBE。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ''
        oobe_url = reverse('clubs:oobe_setup')
        exempt_prefixes = (
            '/oobe/',
            '/static/',
            '/media/',
            '/admin/',
            '/favicon',
        )

        if path.startswith(exempt_prefixes):
            return self.get_response(request)

        if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.dummy':
            if path != oobe_url:
                return redirect(oobe_url)
            return self.get_response(request)

        try:
            from clubs.oobe_bootstrap import bootstrap_oobe_if_needed
            from clubs.models import UserProfile

            bootstrap_oobe_if_needed()
            has_admin = UserProfile.objects.filter(role='admin').exists()
        except (OperationalError, ProgrammingError):
            has_admin = False
        except Exception:
            has_admin = False

        if not has_admin:
            if path != oobe_url:
                return redirect(oobe_url)

        return self.get_response(request)
