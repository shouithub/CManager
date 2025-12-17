#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
社团管理系统 - 生产环境部署脚本

功能:
- 自动配置生产环境设置
- 数据库迁移
- 静态文件收集
- 启动Gunicorn服务

使用方法: python start_production.py [--no-migrate] [--no-static] [--workers N]
"""

import os
import sys
import subprocess
import logging
import argparse
import time
from pathlib import Path
from datetime import datetime

# 导入WSGI应用以支持直接启动
sys.path.insert(0, str(Path(__file__).parent))
try:
    from CManager.wsgi import application as app
except ImportError:
    app = None

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('production.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ProductionManager:
    """生产环境管理器"""
    
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.settings_file = self.base_dir / 'CManager' / 'settings.py'
        os.chdir(self.base_dir)
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CManager.settings')
    
    def run_command(self, cmd, description):
        """执行命令"""
        logger.info(f"{description}...")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )
            if result.stdout:
                logger.info(result.stdout)
            logger.info(f"✓ {description}完成")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ {description}失败: {e.stderr}")
            return False
    
    def check_dependencies(self):
        """检查依赖"""
        logger.info("检查依赖...")
        try:
            import django
            logger.info(f"✓ Django {django.get_version()}")
            
            try:
                import gunicorn
                logger.info(f"✓ Gunicorn {gunicorn.__version__}")
            except ImportError:
                logger.warning("Gunicorn未安装，尝试安装...")
                return self.run_command("pip install gunicorn", "安装Gunicorn")
            return True
        except ImportError:
            logger.warning("缺少依赖，安装requirements.txt...")
            return self.run_command("pip install -r requirements.txt", "安装依赖")
    
    def migrate_database(self):
        """数据库迁移"""
        return self.run_command("python manage.py migrate --noinput", "数据库迁移")
    
    def collect_static(self):
        """收集静态文件"""
        return self.run_command("python manage.py collectstatic --noinput", "收集静态文件")
    
    def verify_setup(self):
        """验证配置"""
        logger.info("验证配置...")
        try:
            import django
            django.setup()
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            logger.info("✓ 数据库连接正常")
            return True
        except Exception as e:
            logger.error(f"✗ 配置验证失败: {e}")
            return False
    
    def start_gunicorn(self, host='0.0.0.0', port=8000, workers=4):
        """启动Gunicorn服务器"""
        logger.info(f"启动Gunicorn (workers={workers})...")
        cmd = (
            f"gunicorn CManager.wsgi:application "
            f"--bind {host}:{port} "
            f"--workers {workers} "
            f"--timeout 300 "
            f"--access-logfile - "
            f"--error-logfile - "
            f"--log-level info"
        )
        try:
            subprocess.run(cmd, shell=True, check=True)
        except KeyboardInterrupt:
            logger.info("服务已停止")
    
    def show_info(self):
        """显示部署信息"""

        print(f"""
╔════════════════════════════════════════════════════════════╗
║            社团管理系统 - 生产环境已就绪                      ║
╠════════════════════════════════════════════════════════════╣
║ 项目路径: {self.base_dir}
║ WSGI应用: CManager.wsgi:application
║ 
║ 宝塔面板配置:
║ 1. 添加Python项目
║ 2. 启动文件: CManager/wsgi.py
║ 3. 启动命令: gunicorn CManager.wsgi:application \\
║              --bind 0.0.0.0:8000 --workers 4
║
║ 直接启动:
║ python start_production.py
╚════════════════════════════════════════════════════════════╝
        """)

def main():
    """主函数"""
    args = parse_args()
    base_dir = Path(__file__).parent
    
    print(f"""
╔════════════════════════════════════════════════════════════╗
║        社团管理系统 - 生产环境部署                           ║
║        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                              ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    manager = ProductionManager(base_dir)
    
    try:
        # 1. 检查依赖
        if not manager.check_dependencies():
            logger.error("依赖检查失败")
            sys.exit(1)
        
        # 2. 数据库迁移
        if not args.no_migrate:
            if not manager.migrate_database():
                logger.error("数据库迁移失败")
                sys.exit(1)
        
        # 3. 收集静态文件
        if not args.no_static:
            if not manager.collect_static():
                logger.warning("静态文件收集失败，但继续执行")
        
        # 4. 验证配置
        if not manager.verify_setup():
            logger.error("配置验证失败")
            sys.exit(1)
        
        # 5. 显示信息
        manager.show_info()
        
        # 6. 启动服务
        if not args.no_start:
            logger.info("准备启动服务...")
            manager.start_gunicorn(
                host=args.host,
                port=args.port,
                workers=args.workers
            )
        else:
            logger.info("环境准备完成，使用 --no-start 参数，跳过启动")
        
    except KeyboardInterrupt:
        logger.info("\n服务已停止")
    except Exception as e:
        logger.error(f"部署失败: {e}", exc_info=True)
        sys.exit(1)
def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='社团管理系统生产环境部署')
    parser.add_argument('--no-migrate', action='store_true', help='跳过数据库迁移')
    parser.add_argument('--no-static', action='store_true', help='跳过静态文件收集')
    parser.add_argument('--no-start', action='store_true', help='仅准备环境，不启动服务')
    parser.add_argument('--workers', type=int, default=4, help='Gunicorn worker数量')
    parser.add_argument('--port', type=int, default=8000, help='服务端口')
    parser.add_argument('--host', default='0.0.0.0', help='绑定地址')
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    base_dir = Path(__file__).parent
    
    print(f"""
╔════════════════════════════════════════════════════════════╗
║        社团管理系统 - 生产环境部署                           ║
║        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                              ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    manager = ProductionManager(base_dir)
    
    try:
        # 1. 检查依赖
        if not manager.check_dependencies():
            logger.error("依赖检查失败")
            sys.exit(1)
        
        # 2. 数据库迁移
        if not args.no_migrate:
            if not manager.migrate_database():
                logger.error("数据库迁移失败")
                sys.exit(1)
        
        # 3. 收集静态文件
        if not args.no_static:
            if not manager.collect_static():
                logger.warning("静态文件收集失败，但继续执行")
        
        # 4. 验证配置
        if not manager.verify_setup():
            logger.error("配置验证失败")
            sys.exit(1)
        
        # 5. 显示信息
        manager.show_info()
        
        # 6. 启动服务
        if not args.no_start:
            logger.info("准备启动服务...")
            manager.start_gunicorn(
                host=args.host,
                port=args.port,
                workers=args.workers
            )
        else:
            logger.info("环境准备完成，使用 --no-start 参数，跳过启动")
        
    except KeyboardInterrupt:
        logger.info("\n服务已停止")
    except Exception as e:
        logger.error(f"部署失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()