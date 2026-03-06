# CManager 国际化 (i18n) 配置指南

## 已完成的配置

### 1. Django 设置 (settings.py)
- ✅ 添加了 `LANGUAGES` 配置，支持中文简体和英语
- ✅ 添加了 `LOCALE_PATHS` 配置
- ✅ 添加了 `LocaleMiddleware` 中间件

### 2. URL 配置 (urls.py)
- ✅ 使用 `i18n_patterns` 包装需要国际化的 URL
- ✅ 添加了语言切换 URL (`/i18n/`)

### 3. 代码适配
- ✅ models.py 部分模型已使用 `gettext_lazy` 标记
- ✅ auth_views.py 部分视图消息已使用 `gettext` 标记
- ✅ base.html 模板已添加 i18n 支持

### 4. 语言切换组件
- ✅ 创建了语言切换组件 (`templates/clubs/components/language_switcher.html`)
- ✅ 已集成到 base.html 侧边栏

## 需要完成的步骤

### 步骤 1: 安装 gettext 工具

#### Windows:
1. 下载 gettext for Windows:
   - 访问: https://mlocati.github.io/articles/gettext-iconv-windows.html
   - 下载并安装 64位版本

2. 或使用 Chocolatey (推荐):
   ```powershell
   choco install gettext
   ```

3. 验证安装:
   ```powershell
   msgfmt --version
   ```

#### macOS:
```bash
brew install gettext
brew link gettext --force
```

#### Linux (Ubuntu/Debian):
```bash
sudo apt-get install gettext
```

### 步骤 2: 生成翻译文件

安装 gettext 后，运行以下命令生成翻译文件:

```powershell
# 生成英语翻译文件
python manage.py makemessages -l en --ignore=venv --ignore=env

# 生成中文简体翻译文件 (如果需要)
python manage.py makemessages -l zh_Hans --ignore=venv --ignore=env
```

### 步骤 3: 编辑翻译文件

翻译文件位于: `locale/<language>/LC_MESSAGES/django.po`

编辑 `.po` 文件，将 `msgstr` 填入对应的翻译。

例如，在 `locale/en/LC_MESSAGES/django.po` 中:
```
msgid "社长"
msgstr "President"

msgid "干事"
msgstr "Staff"

msgid "管理员"
msgstr "Administrator"
```

### 步骤 4: 编译翻译文件

```powershell
python manage.py compilemessages
```

这会生成 `.mo` 文件，Django 使用这些文件来提供翻译。

### 步骤 5: 继续适配剩余代码

需要继续国际化的文件:
1. **Python 文件**: 所有视图文件 (views.py, api_views.py, export_views.py, etc.)
2. **模板文件**: 所有 HTML 模板
3. **模型文件**: 剩余的模型字段和选项

#### Python 代码国际化示例:

```python
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

# 视图中的消息
messages.success(request, _('操作成功'))

# 模型字段
class MyModel(models.Model):
    name = models.CharField(verbose_name=gettext_lazy('名称'))
```

#### 模板国际化示例:

```django
{% load i18n %}

<h1>{% trans "欢迎" %}</h1>

<p>{% blocktrans %}这是一个包含变量的文本: {{ username }}{% endblocktrans %}</p>

{% trans "社团管理系统" as title %}
<title>{{ title }}</title>
```

### 步骤 6: 重新生成和编译

每次添加新的翻译字符串后:

```powershell
# 更新翻译文件
python manage.py makemessages -l en -a

# 编译翻译
python manage.py compilemessages
```

## 常用翻译术语对照表

| 中文 | English |
|------|---------|
| 社长 | President |
| 干事 | Staff |
| 管理员 | Administrator |
| 部员 | Member |
| 部长 | Director |
| 社团 | Club |
| 年审 | Annual Review |
| 注册 | Registration |
| 审核 | Review/Approval |
| 待审核 | Pending |
| 已批准 | Approved |
| 已拒绝 | Rejected |
| 活跃 | Active |
| 不活跃 | Inactive |
| 停止 | Suspended |
| 成员数 | Member Count |
| 创建时间 | Created At |
| 更新时间 | Updated At |
| 真名 | Real Name |
| 学号 | Student ID |
| 电话 | Phone |
| 微信 | WeChat |
| 政治面貌 | Political Status |
| 用户名 | Username |
| 密码 | Password |
| 邮箱 | Email |
| 登录 | Login |
| 登出 | Logout |
| 注册 | Register |
| 首页 | Home |
| 个人中心 | Profile |
| 设置 | Settings |
| 切换主题 | Toggle Theme |
| 切换语言 | Change Language |

## 自动化脚本

为了帮助快速完成国际化，可以创建以下脚本:

### make_translations.ps1
```powershell
# 生成翻译文件
Write-Host "Generating translation files..." -ForegroundColor Green
python manage.py makemessages -l en --ignore=venv --ignore=env
python manage.py makemessages -l zh_Hans --ignore=venv --ignore=env

Write-Host "Translation files generated in locale/ directory" -ForegroundColor Green
Write-Host "Please edit the .po files and run compile_translations.ps1" -ForegroundColor Yellow
```

### compile_translations.ps1
```powershell
# 编译翻译文件
Write-Host "Compiling translation files..." -ForegroundColor Green
python manage.py compilemessages

Write-Host "Translation files compiled successfully!" -ForegroundColor Green
Write-Host "Restart the Django server to see changes" -ForegroundColor Yellow
```

## 测试国际化

1. 启动开发服务器:
   ```powershell
   python manage.py runserver
   ```

2. 访问应用，使用语言切换器切换语言

3. 检查翻译是否正确显示

## 注意事项

1. **不要编辑 .mo 文件**: 这些是编译后的二进制文件，由 .po 文件生成
2. **使用 gettext_lazy**: 在类级别（如模型字段）使用 `gettext_lazy`，在函数中可以使用 `gettext`
3. **保持格式**: 翻译时保持 HTML 标签和格式化字符 (`%s`, `{}` 等)
4. **测试所有语言**: 确保每种语言都正确显示
5. **重启服务器**: 修改翻译后需要重启 Django 开发服务器

## 故障排除

### 翻译不显示
- 检查 .mo 文件是否已生成
- 重启 Django 服务器
- 清除浏览器缓存

### gettext 工具找不到
- 确保 gettext 已安装并在 PATH 中
- Windows 用户可能需要重启终端

### 翻译文件格式错误
- 使用 POEdit 等工具编辑 .po 文件
- 确保 msgid 和 msgstr 格式正确

## 下一步

1. 安装 gettext 工具
2. 运行 `python manage.py makemessages -l en`
3. 编辑生成的翻译文件
4. 运行 `python manage.py compilemessages`
5. 重启服务器并测试
