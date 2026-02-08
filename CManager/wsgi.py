"""WSGI config for CManager project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/

特别注意：本配置文件已针对宝塔面板环境优化。
"""

import os
import sys

# 添加项目根目录到Python路径，确保宝塔面板能正确找到项目模块
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# 设置Django环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CManager.settings')

# 获取WSGI应用程序
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
