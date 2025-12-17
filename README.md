# CManager

## 项目简介

CManager是一个基于Django开发的社团管理系统，由上海海洋大学社团管理服务中心开发，旨在为学校社团提供全面的管理服务。该系统支持社团注册、活动申请、房间借用、用户管理等功能，帮助学校更好地组织和管理社团活动。

## 主要功能

- **用户管理**：支持多种用户角色（社长、干事、管理员、老师、普通用户），用户注册和登录。
- **社团管理**：社团注册申请、审核、成员管理。
- **活动管理**：活动申请、审核、参与记录。
- **房间借用**：222房间借用申请和管理，防止时间冲突。
- **通知系统**：公告发布、邮件通知。
- **数据导出**：支持Excel格式的数据导出。
- **权限控制**：基于角色的访问控制。

## 技术栈

- **后端**：Django 3.1+
- **数据库**：SQLite（开发环境），可配置为PostgreSQL等
- **前端**：Django Templates + Bootstrap
- **其他**：openpyxl（Excel导出）

## 安装和运行

### 环境要求

- Python 3.8+
- pip

### 安装步骤

1. 克隆项目：
   ```bash
   git clone https://github.com/CommunityManageSystem/CManager.git
   cd CManager
   ```

2. 创建虚拟环境：
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

4. 数据库迁移：
   ```bash
   python manage.py migrate
   ```

5. 创建超级用户：
   ```bash
   python manage.py createsuperuser
   ```

6. 运行开发服务器：
   ```bash
   python manage.py runserver
   ```

访问 http://127.0.0.1:8000 即可使用系统。

## 使用说明

### 用户注册和登录

- 普通用户可注册账号。
- 管理员可通过后台管理系统用户角色。

### 社团管理

- 社团负责人提交注册申请。
- 管理员审核通过后，社团正式成立。

### 活动申请

- 社团可申请举办活动。
- 需填写活动详情，经管理员审核。

### 房间借用

- 用户可申请借用222房间。
- 系统自动检查时间冲突，确保借用有效。

### 通知管理

- 管理员可发布公告。
- 系统支持邮件通知功能。

## 部署

### 生产环境部署

使用Gunicorn和Nginx进行部署：

1. 安装Gunicorn：
   ```bash
   pip install gunicorn
   ```

2. 运行Gunicorn：
   ```bash
   gunicorn CManager.wsgi:application --bind 0.0.0.0:8000
   ```

3. 配置Nginx反向代理。

### Docker部署

（可选）项目可配置Docker容器化部署。

## 测试

运行测试：
```bash
python manage.py test
```

## 贡献

欢迎贡献代码！请遵循以下步骤：

1. Fork项目。
2. 创建功能分支。
3. 提交更改。
4. 发起Pull Request。

## 许可证

本项目采用GPLv2许可证。详见LICENSE文件。

## 联系我们

如有问题或建议，请联系上海海洋大学社团管理服务中心。