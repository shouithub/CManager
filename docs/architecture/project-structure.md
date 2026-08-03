# 项目目录结构

```text
CManager/
├── CManager/                  # Django 项目配置、根 URL、ASGI/WSGI
├── clubs/                     # 核心 Django 应用
│   ├── management/commands/   # Django 管理命令（框架固定目录）
│   ├── migrations/            # 数据库迁移（已发布后不得随意移动）
│   ├── services/              # 带事务边界的领域服务
│   ├── templatetags/          # Django 模板标签（框架固定目录）
│   ├── tests/                 # 自动化测试
│   └── views/                 # 按业务域拆分的 HTTP 请求入口
├── templates/clubs/           # 按 admin/auth/staff/user 业务角色组织的模板
├── static/                    # 源静态资源
├── docs/
│   ├── architecture/          # 架构和目录说明
│   └── deployment/            # 部署配置示例
├── scripts/
│   └── development/           # 不依赖 Django 的开发辅助脚本
├── requirements.in            # 生产直接依赖
├── requirements.txt           # 生产锁定依赖
├── requirements-dev.in        # 开发直接依赖
└── requirements-dev.txt       # 开发锁定依赖
```

## 放置原则

- 网站请求入口放在 Django 应用视图模块，事务业务操作放在 `services/`。
- 需要 ORM 或 Django 配置的命令放在 `management/commands/`。
- 独立文件处理、统计等开发脚本放在 `scripts/`。
- Nginx、部署平台等示例配置放在 `docs/deployment/`。
- 测试放在 `clubs/tests/`，按业务域继续拆分，不再堆叠到应用根目录。
- `migrations/`、`templatetags/` 和 `management/commands/` 是 Django 约定目录，
  即使职责看起来相近，也不应为了表面统一而移动。

本地数据库、上传文件、收集后的静态文件、虚拟环境与缓存均由 `.gitignore`
排除，不属于仓库结构。
