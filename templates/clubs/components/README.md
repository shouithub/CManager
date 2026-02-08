# 审核组件使用指南

## 概述

本项目提供了三个可复用的审核相关组件：

1. **`_materials_display.html`** - 附件材料展示组件
2. **`_review_history.html`** - 审核记录时间轴组件
3. **`_staff_review_form.html`** - 干事审核表单组件

所有组件位于 `templates/clubs/components/` 目录下。

---

## 1. 附件材料展示组件 (`_materials_display.html`)

### 使用方式

```django
{% include 'clubs/components/_materials_display.html' with materials=materials_list title="附件材料" show_zip=True zip_url=zip_download_url %}
```

### 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `materials` | List | 是 | - | 材料列表 |
| `title` | String | 否 | "附件材料" | 标题 |
| `show_zip` | Boolean | 否 | False | 是否显示打包下载按钮 |
| `zip_url` | String | 否 | - | 打包下载链接 |

### materials 数据结构

```python
materials = [
    {
        'name': '显示名称',           # 必填
        'file': file_field对象,       # 必填，Django FileField
        'icon': 'material-icon名称'   # 可选，默认 "description"
    },
    # ...
]
```

### View 示例

```python
def review_xxx(request, id):
    obj = get_object_or_404(Model, pk=id)
    
    # 构建材料列表
    materials = []
    if obj.document1:
        materials.append({
            'name': '文档1名称',
            'file': obj.document1,
            'icon': 'description'
        })
    if obj.document2:
        materials.append({
            'name': '文档2名称', 
            'file': obj.document2,
            'icon': 'receipt'
        })
    
    context = {
        'obj': obj,
        'materials': materials,
        'zip_url': reverse('clubs:zip_xxx_docs', args=[obj.id]) if materials else None,
    }
    return render(request, 'xxx.html', context)
```

---

## 2. 审核记录时间轴组件 (`_review_history.html`)

### 使用方式

```django
{% include 'clubs/components/_review_history.html' with reviews=existing_reviews approved_count=approved_count rejected_count=rejected_count %}
```

### 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `reviews` | QuerySet/List | 是 | - | 审核记录列表 |
| `approved_count` | Integer | 否 | - | 已批准数量 |
| `rejected_count` | Integer | 否 | - | 已拒绝数量 |
| `show_stats` | Boolean | 否 | True | 是否显示统计信息 |
| `title` | String | 否 | "审核记录" | 标题 |

### reviews 数据结构要求

每个 review 对象需要有以下字段：
- `status`: 审核状态 ('approved', 'rejected', 'pending')
- `reviewed_at`: 审核时间 (datetime)
- `reviewer`: 审核人 (User 对象，需有 `profile.get_full_name` 或 `username`)
- `comment`: 审核意见 (可选)

### View 示例

```python
def review_xxx(request, id):
    obj = get_object_or_404(Model, pk=id)
    existing_reviews = obj.reviews.all().order_by('-reviewed_at')
    approved_count = existing_reviews.filter(status='approved').count()
    rejected_count = existing_reviews.filter(status='rejected').count()
    
    context = {
        'obj': obj,
        'existing_reviews': existing_reviews,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    }
    return render(request, 'xxx.html', context)
```

---

## 3. 干事审核表单组件 (`_staff_review_form.html`)

### 使用方式

```django
{% include 'clubs/components/_staff_review_form.html' with show_rejected_materials=True materials_list=materials cancel_url='clubs:staff_audit_center' cancel_url_args='club_registration' %}
```

### 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `show_rejected_materials` | Boolean | 否 | False | 是否显示被拒绝材料选择面板 |
| `materials_list` | List | 否 | - | 可选择的材料列表 |
| `cancel_url` | String | 是 | - | 取消按钮返回的URL名称 |
| `cancel_url_args` | String | 否 | - | URL参数 |
| `approve_text` | String | 否 | "通过申请" | 批准按钮文字 |
| `reject_text` | String | 否 | "拒绝申请" | 拒绝按钮文字 |
| `title` | String | 否 | "干事审核" | 标题 |

### materials_list 数据结构

```python
materials_list = [
    {'field': 'field_name', 'name': '显示名称'},
    {'field': 'document1', 'name': '文档1'},
    # ...
]
```

### 表单提交的字段

组件提交的表单包含以下字段：
- `review_status`: 审核状态 ('approved' 或 'rejected')
- `decision`: 兼容字段，值为 'approve' 或 'reject'
- `review_comment`: 审核意见
- `review_comments`: 兼容字段，同 review_comment
- `comment`: 兼容字段，同 review_comment
- `rejected_materials[]`: 被拒绝的材料字段名（多选）

### View 示例

```python
def review_xxx(request, id):
    obj = get_object_or_404(Model, pk=id)
    
    if request.method == 'POST':
        status = request.POST.get('review_status', '')
        comment = request.POST.get('review_comment', '').strip()
        rejected_materials = request.POST.getlist('rejected_materials')
        
        if status == 'approved':
            # 处理批准逻辑
            pass
        elif status == 'rejected':
            # 处理拒绝逻辑
            pass
        
        return redirect('clubs:staff_dashboard')
    
    # 构建可选择的被拒绝材料列表
    materials_list = [
        {'field': 'document1', 'name': '文档1'},
        {'field': 'document2', 'name': '文档2'},
    ]
    
    context = {
        'obj': obj,
        'materials_list': materials_list,
    }
    return render(request, 'xxx.html', context)
```

---

## 完整页面示例

```django
{% extends 'clubs/base.html' %}
{% load custom_filters %}

{% block title %}审核XXX{% endblock %}

{% block content %}
<div class="review-container">
    <!-- 基本信息区域 -->
    <div class="info-card">
        <!-- ... -->
    </div>

    <!-- 附件材料组件 -->
    {% include 'clubs/components/_materials_display.html' with materials=materials title="附件材料" show_zip=True zip_url=zip_url %}

    <!-- 审核记录组件 -->
    {% include 'clubs/components/_review_history.html' with reviews=existing_reviews approved_count=approved_count rejected_count=rejected_count %}

    <!-- 审核表单组件 (仅在待审核且当前用户未审核时显示) -->
    {% if obj.status == 'pending' and not has_reviewed %}
    {% include 'clubs/components/_staff_review_form.html' with show_rejected_materials=True materials_list=rejected_materials_options cancel_url='clubs:staff_audit_center' cancel_url_args='xxx' %}
    {% endif %}
</div>
{% endblock %}
```

---

## 需要更新的页面列表

以下页面需要使用新组件重构：

### 审核中心页面 (staff/)
1. `review_activity_application.html` - 活动申请审核
2. `review_reimbursement.html` - 报销申请审核
3. `review_submission.html` - 年度审核提交
4. `review_club_registration.html` - 社团申请审核
5. `review_club_registration_submission.html` - 社团注册审核
6. `review_request.html` - 通用请求审核
7. `review_detail.html` - 审核详情
8. `review_president_transition.html` ✅ 已完成

### 审批中心页面 (user/)
需要检查是否有类似结构的页面需要更新。

---

## 注意事项

1. 组件已包含完整的 CSS 样式，无需在父页面重复定义
2. 组件使用了 `custom_filters` 模板标签库，需要在页面顶部加载
3. `_materials_display.html` 组件自带文件预览功能
4. 表单组件会自动验证必填项（拒绝时必须填写意见和选择被拒绝材料）
