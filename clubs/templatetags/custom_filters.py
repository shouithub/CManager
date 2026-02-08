from django import template
import os

register = template.Library()

@register.filter
def material_name(field_name):
    """
    将材料字段名转换为友好的显示名称
    动态从模型定义中获取字段名称，避免硬编码
    """
    try:
        from clubs.models import SubmissionReview, ClubApplicationReview, ClubRegistrationReview
        
        # 收集所有审核模型中的材料选项
        choices = []
        choices.extend(SubmissionReview.REJECTED_MATERIALS_CHOICES)
        choices.extend(ClubApplicationReview.REJECTED_MATERIALS_CHOICES)
        choices.extend(ClubRegistrationReview.REJECTED_MATERIALS_CHOICES)
        
        # 转换为字典
        material_names = dict(choices)
        
        # 返回对应名称，如果未找到则返回原始字段名
        return material_names.get(field_name, field_name)
    except (ImportError, AttributeError):
        # 如果导入失败或模型没有该属性，返回原始字段名
        return field_name


@register.filter
def is_office_file(file_url):
    """检查文件是否支持Office Online 预览"""
    if not file_url:
        return False
    # 支持 Office Online 预览的文件扩展名
    office_extensions = {
        '.doc', '.docx',  # Word
        '.xls', '.xlsx',  # Excel
        '.ppt', '.pptx',  # PowerPoint
        '.pdf',           # PDF
    }
    ext = os.path.splitext(str(file_url))[1].lower()
    return ext in office_extensions


@register.filter
def get_file_name_with_ext(file_field):
    """获取带扩展名的文件名"""
    if not file_field:
        return ''
    try:
        return os.path.basename(str(file_field.name))
    except:
        return str(file_field)
    
    # 如果以上方法都失败，返回原始路径
    return file_field


@register.filter
def concat_str(value, arg):
    """字符串拼接"""
    return str(value) + str(arg)
