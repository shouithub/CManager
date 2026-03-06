from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.db.utils import OperationalError, ProgrammingError


class VisitTrackingMiddleware:
    """统计每日页面访问量，写入 DailyStat 表。
    静态文件、媒体文件、API 及管理接口不计入统计。
    使用缓存批量聚合访问量，每 VISIT_STAT_FLUSH_INTERVAL 次请求才写一次 DB。"""
    _SKIP_PREFIXES = ('/static/', '/media/', '/admin/', '/api/', '/sw.js', '/favicon')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path or ''
        if not any(path.startswith(p) for p in self._SKIP_PREFIXES):
            try:
                from django.utils import timezone
                from django.core.cache import cache
                from clubs.models import DailyStat
                from django.db.models import F

                today = timezone.localdate()
                flush_interval = getattr(settings, 'VISIT_STAT_FLUSH_INTERVAL', 20)
                lock_seconds = getattr(settings, 'VISIT_STAT_FLUSH_LOCK_SECONDS', 5)
                counter_key = f'visit_counter:{today}'

                # 原子性递增计数器；若 key 不存在则初始化
                if not cache.add(counter_key, 1, timeout=86400):
                    count = cache.incr(counter_key)
                else:
                    count = 1

                # 每累积 flush_interval 次才批量写入 DB
                if count % flush_interval == 0:
                    lock_key = f'visit_flush_lock:{today}'
                    if cache.add(lock_key, 1, timeout=lock_seconds):
                        DailyStat.objects.update_or_create(
                            date=today,
                            defaults={},
                            create_defaults={'visits': 0},
                        )
                        DailyStat.objects.filter(date=today).update(
                            visits=F('visits') + flush_interval
                        )
            except Exception:
                pass
        return response


class InitialSetupMiddleware:
    """首启引导中间件：如果还没有管理员账号，则强制进入 OOBE。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def _ensure_bootstrap_host_and_origin_trusted(self, request):
        """During first-run OOBE, trust current host/origin to avoid CSRF bootstrap deadlock."""
        raw_host = (request.META.get('HTTP_HOST') or '').strip()
        host = raw_host.split(':', 1)[0].strip().lower()
        if not host:
            return

        allowed_hosts = list(getattr(settings, 'ALLOWED_HOSTS', []))
        if host not in allowed_hosts:
            allowed_hosts.append(host)
            settings.ALLOWED_HOSTS = allowed_hosts

        trusted_origins = list(getattr(settings, 'CSRF_TRUSTED_ORIGINS', []))
        forwarded_proto = (request.META.get('HTTP_X_FORWARDED_PROTO') or '').split(',')[0].strip().lower()
        scheme = forwarded_proto or ('https' if request.is_secure() else 'http')

        candidates = [f'{scheme}://{host}']
        if scheme != 'https':
            candidates.append(f'https://{host}')

        changed = False
        for origin in candidates:
            if origin not in trusted_origins:
                trusted_origins.append(origin)
                changed = True
        if changed:
            settings.CSRF_TRUSTED_ORIGINS = trusted_origins

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
            if path.startswith('/oobe/'):
                self._ensure_bootstrap_host_and_origin_trusted(request)
            return self.get_response(request)

        if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.dummy':
            if path != oobe_url:
                return redirect(oobe_url)
            return self.get_response(request)

        try:
            from clubs.oobe_bootstrap import bootstrap_oobe_if_needed
            from clubs.models import UserProfile
            from django.core.cache import cache

            bootstrap_oobe_if_needed()

            cache_key = 'oobe:has_admin'
            has_admin = cache.get(cache_key)
            if has_admin is None:
                has_admin = UserProfile.objects.filter(role='admin').exists()
                cache.set(cache_key, has_admin,
                          timeout=getattr(settings, 'INITIAL_SETUP_CACHE_SECONDS', 30))
        except (OperationalError, ProgrammingError):
            has_admin = False
        except Exception:
            has_admin = False

        if not has_admin:
            self._ensure_bootstrap_host_and_origin_trusted(request)
            if path != oobe_url:
                return redirect(oobe_url)

        return self.get_response(request)
