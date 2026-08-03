# Django 管理命令

此目录是 Django 的固定约定，不能与根目录开发脚本合并。这里的每个 Python
模块都会被注册为 `python manage.py <模块名>` 命令。

当前命令：

- `seed_test_data`：为本地开发环境写入可重复执行的演示数据。

仅操作普通文件且不需要 Django ORM 的脚本应放在项目根目录的 `scripts/` 下。
