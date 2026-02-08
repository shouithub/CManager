# CManager - 社团管理系统

[![License](https://img.shields.io/badge/license-GPLv2-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-3.1%2B-green)](https://www.djangoproject.com/)

[中文](README.md) | [English](README_EN.md)

## 🌿 分支说明 (v1)

本项目包含一个 `v1` 分支，保留了以下在当前版本中被精简的功能：
- **扩展角色**：支持 **老师** 和 **普通用户** 账户类型。
- **活动报名**：允许普通用户直接通过平台报名参与活动。
- **流程审核**：包含老师角色的审批流程。

> **说明**：由于学校实际业务需求调整，当前主分支已移除上述功能以保持精简。如果您需要完整的活动报名及老师审核功能，请检出并使用 `v1` 分支。

## 📋 项目简介

**CManager** 是一个基于 **Django** 框架开发的社团管理系统，由 **上海海洋大学社团管理服务中心** 开发，旨在为学校社团提供全面、高效的管理服务。该系统涵盖了社团注册、活动申请、房间借用、用户管理等核心功能，帮助学校更好地组织和管理丰富多彩的社团活动。

## ✨ 主要功能

- **👥 用户管理**：支持多种用户角色（社长、干事、管理员、老师、普通用户），提供注册、登录及个人信息管理功能。
- **🏢 社团管理**：全生命周期管理，包括社团注册申请、审核、成员管理及年审流程。
- **📅 活动管理**：在线活动申请、审批流程及活动记录归档。
- **🏟️ 房间借用**：专属 222 房间借用申请与管理，内置自动冲突检测，确保场地使用有序。
- **📢 通知系统**：公告发布及邮件通知集成，信息触达更及时。
- **📊 数据导出**：支持 Excel 格式的数据导出，便于线下存档与分析。
- **🔒 权限控制**：基于角色的访问控制 (RBAC)，保障系统数据安全。

## 🛠️ 技术栈

- **后端**：Django 3.1+ (Python)
- **数据库**：SQLite (开发环境) / PostgreSQL (推荐生产环境)
- **前端**：Django Templates + Material Design 3 (MD3) + Bootstrap
- **工具库**：openpyxl (Excel 导出), Pillow (图像处理)

## 🚀 安装与运行

### 环境要求

- Python 3.8+
- pip

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
    pip install -r requirements.txt
    ```

4.  **数据库迁移**
    ```bash
    python manage.py migrate
    ```

5.  **创建超级用户**
    ```bash
    python manage.py createsuperuser
    ```

6.  **运行开发服务器**
    ```bash
    python manage.py runserver
    ```

    访问 [http://127.0.0.1:8000](http://127.0.0.1:8000) 即可开始使用系统。

## 📖 使用说明

### 👤 用户注册与登录
- 普通用户可直接注册账号。
- 管理员可通过后台管理系统分配用户角色与权限。

### 🏢 社团管理
- 社团负责人提交注册申请。
- 管理员/干事审核通过后，社团正式成立。

### 📝 活动申请
- 社团可在线提交活动策划与详情。
- 干事对活动申请进行审核与批复。

### 🔑 房间借用
- 用户可申请借用 222 房间的时间段。
- 系统自动检查时间冲突，确保借用有效。

## 📦 部署

### 生产环境部署 (Gunicorn + Nginx)

1.  **安装 Gunicorn**
    ```bash
    pip install gunicorn
    ```

2.  **运行 Gunicorn**
    ```bash
    gunicorn CManager.wsgi:application --bind 0.0.0.0:8000
    ```

3.  **配置 Nginx** 进行反向代理。

## 📄 许可证

本项目采用 **GPLv2** 许可证。详见 [LICENSE](LICENSE) 文件。

## 📞 联系我们

**上海海洋大学社团管理服务中心**
如有问题或建议，欢迎联系我们。
📧 邮箱：whtrys@outlook.com
