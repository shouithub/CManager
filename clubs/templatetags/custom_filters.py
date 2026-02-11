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
        from clubs.models import SubmissionReview, ClubApplicationReview, ClubRegistrationReview, MaterialRequirement
        
        # 1. 优先尝试从 MaterialRequirement 获取 (支持 req_ID 和 legacy_name)
        key_str = str(field_name)
        if key_str.startswith('req_'):
            try:
                req_id = int(key_str.split('_')[1])
                req = MaterialRequirement.objects.filter(id=req_id).first()
                if req:
                    return req.name
            except (ValueError, IndexError):
                pass
        
        # 尝试 legacy_name 查找
        req = MaterialRequirement.objects.filter(legacy_field_name=key_str).first()
        if req:
            return req.name
        
        # 2. 回退到模型定义的 choices
        # 收集所有审核模型中的材料选项
        choices = []
        choices.extend(SubmissionReview.REJECTED_MATERIALS_CHOICES)
        choices.extend(ClubApplicationReview.REJECTED_MATERIALS_CHOICES)
        choices.extend(ClubRegistrationReview.REJECTED_MATERIALS_CHOICES)
        
        # 转换为字典
        material_names = dict(choices)
        
        # 返回对应名称，如果未找到则返回原始字段名
        return material_names.get(field_name, field_name)
    except (ImportError, AttributeError, Exception):
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


@register.filter
def get_material_requirement(key):
    """
    根据键值（req_ID 或 legacy_field_name）获取 MaterialRequirement 对象
    """
    try:
        from clubs.models import MaterialRequirement
        key_str = str(key)
        
        # 1. 尝试通过 req_ID 获取
        if key_str.startswith('req_'):
            try:
                req_id = int(key_str.split('_')[1])
                return MaterialRequirement.objects.filter(id=req_id).first()
            except (ValueError, IndexError):
                pass
                
        # 2. 尝试通过 legacy_field_name 获取
        req = MaterialRequirement.objects.filter(legacy_field_name=key_str).first()
        if req:
            return req
            
        # 3. 如果没找到，返回 None
        return None
    except Exception:
        return None
