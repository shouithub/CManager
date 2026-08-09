# CManager - 社团管理系统

[![License](https://img.shields.io/badge/license-GPLv2-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.2%2B-green)](https://www.djangoproject.com/)
[![最新版本](https://img.shields.io/badge/最新版本-v1.1.0-6750A4)](https://github.com/shouithub/CManager/releases/tag/v1.1.0)

[中文](README.md) | [English](README_EN.md)

## 📋 项目简介

**CManager** 是一个基于 **Django** 框架开发的现代化社团管理系统，由 **上海海洋大学社团管理服务中心** 开发。该系统旨在为高校社团提供全生命周期的数字化管理解决方案，涵盖社团注册、年审、换届、活动申请、报销管理及场地预约等核心业务流程。

系统采用 **Material Design 3 (MD3)** 设计语言，提供美观、统一且响应式的用户界面，完美适配桌面端与移动端访问。核心业务基于自研的**动态表单引擎**驱动，支持灵活配置表单字段、提交流程与审核策略，实现业务逻辑的高度解耦。

## ✨ 核心功能

### 👥 用户与权限体系
- **多角色支持**：社长、干事、管理员、社员（主分支）；老师、普通用户（v1 分支）。
- **精细化权限**：基于 RBAC 的权限控制，不同角色拥有专属工作台。
- **个人中心**：支持头像上传（自动裁剪）、个人信息管理（QQ / 微信 / 性别等）、政治面貌登记。
- **隐私保护**：用户可设置联系方式公开状态；支持"干事-社长"关联可见性逻辑（即社长可查看其负责社团对应干事的联系方式）。
- **社员管理**：支持社员加入表单、社员列表查看与批量管理。
- **扫码注册**：支持生成注册令牌（二维码），限定有效期与使用次数，方便社员快捷加入。

### ♻️ 账号生命周期
- **延期机制**：不活跃账号可由用户主动延期，恢复活跃并顺延 1 年。
- **管理员控制**：管理员可在用户管理中启用/禁用账号（禁用进入不活跃计时），并可二次确认后删除账号。
- **状态分离**：账号启用/禁用状态由 `account_status` 独立维护，与干事审核状态 `status` 互不影响。

### 🏢 社团全生命周期管理
- **社团申请**：新社团成立的全流程申请与材料提交，审核通过后自动创建社团并绑定社长。
- **社团注册**：支持自定义周期（年/月/日/计数）的社团注册流程。
- **社团年审**：年度审核流程，支持多种材料（自查表、章程、财务表等）的在线提交与驳回修改。
- **社团换届**：社长换届申请与审核流程，审核通过后自动更新社团负责人信息。
- **部门管理**：动态配置社团管理中心的部门结构与职能（支持重点工作 Highlights）。

### 🧩 动态表单与业务引擎
- **业务解耦架构**：所有业务流程（年审、注册、申请、报销、活动、换届）由统一的动态表单引擎驱动。
- **灵活字段配置**：支持文本、多行文本、数字、日期、文件上传（支持多文件）、单选、多选等 9 种字段类型。
- **周期驱动**：通道可按年/月/日或自定义数字周期循环，适配学期注册、年度审核等场景。
- **提交策略**：支持可重复提交、仅一次提交、每周期一次提交三种策略。
- **社团开关**：管理员可按社团粒度自由开启/关闭各业务通道。
- **外露提示**：通道可配置在"我的社团"界面的提示文案，引导社长办理业务。

### 📅 活动与报名
- **活动申请**：社团在线提交活动策划，审核通过后自动发布到活动公开展示页。
- **活动报名**：社员可浏览已发布活动并在线报名/取消报名（主分支已内置）。
- **报销管理**：经费报销申请、发票上传（支持 Word 合并）及审批流，支持金额统计与历史记录。

### 🏟️ 场地预约系统
- **智能预约**：专属活动室在线预约，支持自定义多个房间与时间段。
- **冲突检测**：内置时间段冲突检测算法，防止预约撞车。
- **固定时段**：支持配置固定的开放时间段，规范场地使用。
- **日历视图**：优化的桌面端与移动端日历视图，方便随时随地查看与预约。

### 🔍 审核中心
- **统一审核台**：干事与管理员的统一工作台，集中处理各类申请（活动、报销、注册、年审等）。
- **多审人审核**：支持配置所需通过人数，多个干事/管理员可独立审核同一提交。
- **逐字段打回**：支持针对单个字段或文件进行打回，申请人修改后重新提交（保留每次尝试的审核记录）。
- **历史记录**：完整的审核历史归档，支持按类型筛选与查看详情。

### 📱 移动端与 PWA
- **响应式设计**：全站页面适配手机屏幕。
- **底部导航**：移动端专属的底部导航栏，操作更便捷。
- **触控优化**：针对触摸屏优化的交互体验（如弹窗、滑动列表）。
- **PWA 支持**：内置 Service Worker，支持离线缓存与添加到主屏幕。
- **深色模式**：支持亮色/深色主题切换。

### 🔧 系统管理
- **OOBE 初始化向导**：首次访问引导创建管理员账户，配置站点基本信息与安全参数。
- **站点外观**：支持自定义站点 Logo、Favicon、字体等外观设置。
- **SMTP 配置**：数据库存储的邮件服务配置，支持 QQ / 163 / Outlook / Gmail 及自定义 SMTP。
- **CSV 批量导入**：支持批量导入用户与社团数据，含事务处理与错误反馈。
- **ZIP 打包下载**：统一压缩下载接口，方便批量获取提交材料。
- **通知 API**：提供通知计数接口，实时提醒待办事项。
- **每日访问统计**：内置每日访问量统计。

### 🌐 多语言与动态内容翻译
- **四种界面语言**：内置简体中文、英文、维吾尔文与蒙古文界面翻译。
- **用户语言偏好**：登录用户可在个人设置中保存首选语言，并在不同设备间同步。
- **站点默认语言**：管理员可为访客以及尚未设置偏好的用户配置全站默认语言。
- **动态内容翻译**：表单通道、字段、周期和示例文件等数据库内容可分别维护多语言译文。
- **自动翻译回退**：支持通过 UAPI 自动翻译；蒙古语、维吾尔语普通接口不可用时可回退 AI 翻译接口。

### 🔐 私有文件存储与预览
- **本地与 S3 统一存储**：业务代码使用统一存储接口，可在本地文件系统和 S3 兼容服务间切换。
- **短时授权访问**：本地私有材料使用限时签名地址；S3 私有材料使用短时预签名直链。
- **流量不经过本站**：S3 模式下浏览器或 Office Online 直接从对象存储获取文件，应用服务器只负责鉴权和签发地址。
- **明确的附件操作**：Office 文件提供“在线预览”和下载，PDF 提供浏览器预览和下载，图片可点击缩略图查看，其他格式仅提供下载。
- **私有媒体隔离**：Nginx 只公开头像、站点外观和轮播图等展示资源，提交材料、归档和去重文件不允许直接映射。

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| **后端** | Django 5.2+ (Python 3.12+) |
| **数据库** | SQLite（开发，WAL 模式）/ MySQL（生产，通过 PyMySQL） |
| **缓存** | Redis（django-redis） |
| **前端** | Django Templates + Material Design 3 (MD3) |
| **图标** | Google Material Icons |
| **图片处理** | Pillow |
| **文档处理** | python-docx（Word 合并）、PyMuPDF（PDF 处理） |
| **Excel** | openpyxl（导入/导出） |
| **二维码** | qrcode[pil]（注册令牌） |
| **PWA** | Service Worker |

## 🚀 安装与运行

### 环境要求

- Python 3.12+
- pip
- （可选，生产环境）MySQL、Redis

### 安装步骤

1.  **克隆项目**
    ```bash
    git clone https://github.com/shouithub/CManager.git
    cd CManager
    ```

2.  **创建虚拟环境**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **安装依赖**
    ```bash
    pip install --require-hashes -r requirements.txt
    ```

4.  **配置环境变量**
    本项目提供了 `.env.example` 示例文件。请将其复制为 `.env.local` 并填入你的配置：
    ```bash
    # Linux / macOS
    cp .env.example .env.local
    
    # Windows
    copy .env.example .env.local
    ```
    
    请务必修改 `.env.local` 文件中的 `SECRET_KEY`，并生成独立的
    `CREDENTIAL_ENCRYPTION_KEY`。后者用于加密数据库中的 SMTP 密码和 S3 Secret Key，
    丢失后无法解密已有凭据，请放入 Secret Manager 或受权限保护的环境文件中。
    
    示例 `.env.local` 配置：
    ```ini
    # 核心安全配置
    SECRET_KEY=your-long-random-secret-key
    CREDENTIAL_ENCRYPTION_KEY=your-fernet-key
    DEBUG=True
    ALLOWED_HOSTS=localhost,127.0.0.1
    CSRF_TRUSTED_ORIGINS=http://127.0.0.1,http://localhost

    # 邮件服务配置 (可选)
    ADMIN_CONTACT_EMAIL=admin@example.com
    EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
    EMAIL_HOST=smtp.example.com
    EMAIL_PORT=587
    EMAIL_HOST_USER=no-reply@example.com
    EMAIL_HOST_PASSWORD=your-email-password
    EMAIL_USE_TLS=True
    DEFAULT_FROM_EMAIL=no-reply@example.com

    # 生产环境安全增强（DEBUG=False 时必须启用）
    SECURE_BROWSER_XSS_FILTER=True
    SECURE_CONTENT_TYPE_NOSNIFF=True
    SESSION_COOKIE_SECURE=True
    CSRF_COOKIE_SECURE=True
    X_FRAME_OPTIONS=DENY
    ```

5.  **数据库迁移**
    ```bash
    python manage.py migrate
    ```

    > **生产环境提示**：如需使用 MySQL，请在 `.env.local` 中配置数据库参数。`DEBUG=False` 时系统默认拒绝不安全的 Secret、Cookie 和非 Redis 缓存配置；请设置 `CACHE_BACKEND=redis` 与 `REDIS_URL`。详见 `.env.example`。
    > `clubs` 应用已使用合并迁移（squashed migration），新环境仅需执行上述迁移命令即可。

6.  **首次启动初始化（推荐）**
    首次访问系统会进入 OOBE 初始化页面，用于创建管理员账户并写入本地配置（不会提交到 Git）。
    如需命令行方式，也可自行创建管理员用户并赋予 `admin` 角色。

7.  **运行开发服务器**
    ```bash
    python manage.py runserver
    ```

    访问 [http://127.0.0.1:8000](http://127.0.0.1:8000) 即可开始使用系统。

8.  **公网部署（Nginx 静态/媒体资源）**
    生产环境建议由 Nginx 直接托管静态和媒体文件。可在 Nginx 配置中加入：
    ```nginx
    location /static/ {
        alias /path/to/CManager/staticfiles/;
    }
    location ^~ /media/avatars/ {
        alias /path/to/CManager/media/avatars/;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
        add_header X-Content-Type-Options nosniff always;
    }
    location ^~ /media/site/ {
        alias /path/to/CManager/media/site/;
    }
    location ^~ /media/carousel/ {
        alias /path/to/CManager/media/carousel/;
    }
    location /media/ {
        return 404;
    }
    ```
    同时请在部署时执行：
    ```bash
    python manage.py collectstatic --noinput
    python manage.py check --deploy
    ```
    本地业务文件使用本站短时签名地址；S3 文件则直接生成 S3 预签名 URL，文件流量
    不经过本站。不要让 Nginx 直接映射整个 `media/`，S3 Bucket 也应保持私有。完整媒体规则见
    `docs/deployment/nginx-media-security.conf`，部署时请合并到站点配置。

    > **HTTPS 说明**：Django 本身不提供 HTTPS。若站点需要 HTTPS，请使用 Nginx
    > 反向代理终止 TLS（`listen 443 ssl` 并转发 `X-Forwarded-Proto`），同时在环境
    > 变量中设置 `IS_NGINX_PROXY=True`。HTTPS 强制跳转、Secure Cookie 与 HSTS 等
    > 设置仅在该开关开启时生效；直连端口（HTTP）部署时这些功能自动关闭。请勿使用
    > `django-sslserver` 或让 Django 直接监听 HTTPS——生产环境 HTTPS 一律由 Nginx
    > 反向代理提供。

9.  **多语言（可选）**
    系统内置 Django 国际化框架，源字符串以中文编写，支持简体中文、英文、
    维吾尔文（Uyghur）与蒙古文。界面右上角/侧边栏底部的语言按钮可即时切换。

    维护翻译时，先重新提取源码字符串，再运行种子脚本补全高频词条，最后编译：
    ```bash
    python manage.py makemessages --all
    python scripts/i18n_seed_all.py
    python manage.py compilemessages
    ```
    新增语言时在 `CManager/settings.py` 的 `LANGUAGES` 中注册语言代码即可；
    数据库中的动态内容（如表单通道名称）不参与 gettext 翻译。

## 🧭 开发目录指南

项目目录职责、Django 管理命令与独立脚本的区别见
[`docs/architecture/project-structure.md`](docs/architecture/project-structure.md)。
独立开发脚本统一放在 `scripts/`；需要 Django ORM 的命令保留在框架规定的
`clubs/management/commands/` 中。

### 提交与发布规范

- 提交标题使用 `<类型>: <中文摘要>`，例如 `fix: 修复附件预览响应头`；类型前缀保留
  Conventional Commits 约定，摘要和正文必须使用中文，代码标识符与专有名词除外。
- 除纯机械格式化等无需解释的变更外，每个提交都必须在标题下写正文条目，不能只有标题。
- 正文使用 `- ` 开头的中文条目，尽可能说明修改范围、用户可见行为、兼容性或安全影响、
  新增测试及实际验证结果。
- 一个提交包含多个独立修改时，每项分别成条，不使用“若干优化”“修复问题”等无法审计的笼统描述。
- 发布新版本时推送带说明的版本标签，由 GitHub 在 Release 页面自动生成提交列表；
  README 不设置按版本维护的更新日志栏目。
- 正式版本使用带说明的 `v<主版本>.<次版本>.<修订号>` 标签；标签推送后，CI 会在 SQLite 与
  MySQL 环境中执行静态检查、依赖审计、迁移、测试、部署检查和静态文件收集，全部通过后才创建 Release。

## 📖 角色使用指南

### 👤 社长
- **工作台**：查看所属社团状态、通知公告、待办业务提示。
- **业务办理**：通过动态表单提交活动申请、报销申请、年审材料、换届申请、社团注册。
- **场地预约**：查看可用时间段并预约活动室。
- **信息管理**：更新社团简介、查看负责干事联系方式。
- **社员管理**：查看本社社员列表、管理社员信息。

### 🛡️ 干事
- **审核中心**：审批负责社团的各类申请，支持逐字段审核打回。
- **社团管理**：查看并管理负责的社团信息。
- **数据统计**：查看社团活跃度、财务状况等。

### ⚙️ 管理员
- **系统配置**：管理轮播图、部门设置、SMTP 邮件服务、站点外观。
- **用户管理**：创建用户、分配角色、重置密码、启用/禁用账号、删除账号（二次确认）、批量导入。
- **全局管控**：管理动态表单通道、配置提交周期、按社团开启/关闭业务通道。
- **数据管理**：CSV 导入导出、ZIP 打包下载提交材料。

## 🌿 分支说明 (v1)

本项目包含一个 `v1` 分支，保留了以下在当前主分支（main）中已重构的功能的原始实现：
- **扩展角色**：支持 **老师** 和 **普通用户** 账户类型。
- **传统活动报名**：v1 分支中包含面向普通用户的活动报名流程（含老师审批环节）。

> **说明**：当前主分支已将核心业务迁移至动态表单引擎架构。如需参考传统固定模板实现，请检出 `v1` 分支。

## 📄 开源协议

本项目采用 [GPLv2](LICENSE) 开源协议。
