# 项目脚本

此目录只存放不依赖 Django 命令发现机制的开发、检查和运维脚本。

## 目录

- `development/`：本地开发辅助脚本，不参与网站运行。

需要访问 Django ORM、配置或应用注册表的操作，应实现为
`clubs/management/commands/` 下的 Django 管理命令，并通过
`python manage.py <command>` 调用。
