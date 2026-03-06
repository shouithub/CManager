"""
URL configuration for CManager project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.http import HttpResponse
from django.contrib.staticfiles import finders
from django.views.static import serve

def service_worker_view(request):
    """以正确的 Service-Worker-Allowed 头提供 sw.js，使其作用域覆盖整个站点。"""
    sw_path = finders.find('js/sw.js')
    if sw_path:
        with open(sw_path, 'rb') as f:
            content = f.read()
    else:
        content = b''
    response = HttpResponse(content, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response


# 不需要语言前缀的 URL（静态资源、Service Worker 等）
urlpatterns = [
    path('sw.js', service_worker_view, name='service_worker'),
    path('i18n/', include('django.conf.urls.i18n')),  # 语言切换
]

# 在生产环境中，静态文件应该由Web服务器提供，但为了解决当前问题，我们添加这个配置
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# 媒体文件服务 - 确保在所有环境下都能访问媒体文件
# 注意：要确保这个配置不会与应用中的路由冲突
# 使用re_path而不是static函数，以确保正确处理中文文件名
# 将媒体文件路由放在应用路由之后，避免冲突
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]

# 需要语言前缀的 URL
urlpatterns += i18n_patterns(
    path('', include('clubs.urls', namespace='clubs')),
    path('admin/', admin.site.urls),
    prefix_default_language=True,  # 默认语言也会添加前缀（如 /zh-hans/）
)

