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
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('clubs.urls', namespace='clubs')),
    path('admin/', admin.site.urls),
]

# 在生产环境中，静态文件应该由Web服务器提供，但为了解决当前问题，我们添加这个配置
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# 媒体文件服务 - 确保在所有环境下都能访问媒体文件
# 注意：要确保这个配置不会与应用中的路由冲突
from django.views.static import serve
from django.urls import re_path

# 使用re_path而不是static函数，以确保正确处理中文文件名
# 将媒体文件路由放在应用路由之后，避免冲突
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]

