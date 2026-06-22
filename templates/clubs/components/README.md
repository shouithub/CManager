# 组件说明

当前动态表单系统只保留运行中使用的统一组件。

## `_dynamic_submission_fields.html`

用于渲染动态表单提交详情中的字段和值，包括文件字段。

使用方式：

```django
<div class="field-list">
    {% include 'clubs/components/_dynamic_submission_fields.html' with rows=rows %}
</div>
```

参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `rows` | list | 是 | 由 `_submission_context(submission)` 生成的字段行列表 |

`rows` 中每一项应包含：

| 字段 | 说明 |
| --- | --- |
| `field` | `FormField` 实例 |
| `value` | 非文件字段展示值 |
| `files` | 文件字段对应的 `FormUploadedFile` 列表 |

文件字段会统一渲染为下载链接；非文件字段显示 `value`，空值显示 `-`。
