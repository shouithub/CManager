# CManager - 社团管理系统

[![License](https://img.shields.io/badge/license-GPLv2-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.0%2B-green)](https://www.djangoproject.com/)

[中文](README.md) | [English](README_EN.md)

## 📋 项目简介

**CManager** 是一个基于 **Django** 框架开发的现代化社团管理系统，由 **上海海洋大学社团管理服务中心** 开发。该系统旨在为高校社团提供全生命周期的数字化管理解决方案，涵盖社团注册、年审、换届、活动申请、报销管理及场地预约等核心业务流程。

系统采用 **Material Design 3 (MD3)** 设计语言，提供美观、统一且响应式的用户界面，完美适配桌面端与移动端访问。

## ✨ 核心功能

### 👥 用户与权限体系
- **多角色支持**：社长、干事、管理员、老师（v1分支）、普通用户（v1分支）。
- **精细化权限**：基于 RBAC 的权限控制，不同角色拥有专属工作台。
- **个人中心**：支持头像上传（自动裁剪）、个人信息管理、政治面貌登记。
- **隐私保护**：用户可设置联系方式公开状态；支持“干事-社长”关联可见性逻辑（即社长可查看其负责社团对应干事的联系方式）。

### 🏢 社团全生命周期管理
- **社团申请**：新社团成立的全流程申请与材料提交。
- **社团注册**：每学期的社团注册流程，支持自定义注册周期。
- **社团年审**：年度审核流程，支持多种材料（自查表、章程、财务表等）的在线提交与驳回修改。
- **社团换届**：社长换届申请与审核流程，自动更新社团负责人信息。
- **部门管理**：动态配置社团管理中心的部门结构与职能。

### 📅 活动与报销
- **活动申请**：社团在线提交活动策划，支持多级审核。
- **报销管理**：经费报销申请、凭证上传及审批流，支持金额统计与历史记录。

### 🏟️ 场地预约系统
- **智能预约**：专属活动室（如 222 房间）在线预约。
- **冲突检测**：内置时间段冲突检测算法，防止预约撞车。
- **固定时段**：支持配置固定的开放时间段，规范场地使用。
- **移动端适配**：优化的移动端日历视图，方便随时随地查看与预约。

### 🔍 审核中心
- **统一审核台**：干事与管理员的统一工作台，集中处理各类申请（活动、报销、注册、年审等）。
- **历史记录**：完整的审核历史归档，支持按类型筛选与查看详情。
- **审核反馈**：支持针对特定材料的驳回意见与修改建议。

### 📱 移动端适配
- **响应式设计**：全站页面适配手机屏幕。
- **底部导航**：移动端专属的底部导航栏，操作更便捷。
- **触控优化**：针对触摸屏优化的交互体验（如弹窗、滑动列表）。

## 🛠️ 技术栈

- **后端**：Django 5.x (Python 3.13+)
- **数据库**：SQLite (开发环境) / PostgreSQL (生产环境)
- **前端**：Django Templates + Material Design 3 (MD3) + Bootstrap 5 (部分组件)
- **静态资源**：Google Material Icons
- **工具库**：Pillow (图片处理), openpyxl (Excel 导出)

## 🚀 安装与运行

### 环境要求

- Python 3.13+
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

4.  **配置环境变量**
    本项目提供了 `.env.example` 示例文件。请将其复制为 `.env` 并填入你的配置：
    ```bash
    # Linux / macOS
    cp .env.example .env
    
    # Windows
    copy .env.example .env
    ```
    
    请务必修改 `.env` 文件中的 `SECRET_KEY` 为一个随机的安全字符串。
    
    示例 `.env` 配置：
    ```ini
    # 核心安全配置
    SECRET_KEY=your-long-random-secret-key
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

    # 生产环境安全增强 (建议生产环境开启)
    SECURE_BROWSER_XSS_FILTER=True
    SECURE_CONTENT_TYPE_NOSNIFF=True
    SESSION_COOKIE_SECURE=False
    CSRF_COOKIE_SECURE=False
    X_FRAME_OPTIONS=DENY
    ```

5.  **数据库迁移**
    ```bash
    python manage.py migrate
    ```

6.  **创建超级用户**
    ```bash
    python manage.py createsuperuser
    ```

7.  **运行开发服务器**
    ```bash
    python manage.py runserver
    ```

    访问 [http://127.0.0.1:8000](http://127.0.0.1:8000) 即可开始使用系统。

## 📖 角色使用指南

### 👤 社长
- **工作台**：查看所属社团状态、通知公告。
- **业务办理**：提交活动申请、报销申请、年审材料、换届申请。
- **场地预约**：查看可用时间段并预约活动室。
- **信息管理**：更新社团简介、查看负责干事联系方式。

### 🛡️ 干事
- **审核中心**：审批负责社团的各类申请。
- **社团管理**：查看并管理负责的社团信息。
- **数据统计**：查看社团活跃度、财务状况等。

### ⚙️ 管理员
- **系统配置**：管理轮播图、部门设置、SMTP邮件服务。
- **用户管理**：创建用户、分配角色、重置密码。
- **全局管控**：开启/关闭注册周期、年审通道等。

## 🌿 分支说明 (v1)

本项目包含一个 `v1` 分支，保留了以下在当前主分支（main）中被精简的功能：
- **扩展角色**：支持 **老师** 和 **普通用户** 账户类型。
- **活动报名**：允许普通用户直接通过平台报名参与活动。
- **流程审核**：包含老师角色的审批流程。

> **说明**：当前主分支专注于社团内部管理与中心审核流程。如需面向全校学生的活动报名功能，请检出 `v1` 分支。

## 📄 开源协议

本项目采用 [GPLv2](LICENSE) 开源协议。
