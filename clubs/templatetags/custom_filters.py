from django import template
from django.conf import settings
import os
import builtins

register = template.Library()

@register.filter
def getattr(obj, attr):
    """
    获取对象的属性，如果属性不存在返回None
    """
    return builtins.getattr(obj, attr, None)

@register.filter

def get_file_path(file_url):
    """从完整的文件URL中提取相对路径（相对于MEDIA_ROOT）"""
    if not file_url:
        return ''
    # 移除MEDIA_URL前缀，得到相对路径
    media_url = settings.MEDIA_URL
    if file_url.startswith(media_url):
        return file_url[len(media_url):]
    return file_url

@register.filter

def get_file_extension(file_url):
    """从文件URL中提取扩展名"""
    if not file_url:
        return ''
    return os.path.splitext(file_url)[1]

@register.filter

def extract_file_path(file_url):
    """从完整的文件URL中提取相对路径（兼容不同的URL格式）"""
    if not file_url:
        return ''
    
    # 首先尝试直接使用get_file_path
    path = get_file_path(file_url)
    if path != file_url:
        return path
    
    # 如果get_file_path没有改变，可能是因为MEDIA_URL不匹配
    # 尝试使用split('/media/')来提取
    parts = file_url.split('/media/')
    if len(parts) > 1:
        return parts[1]

@register.filter
def material_name(field_name):
    """将材料字段名转换为友好的显示名称"""
    material_names = {
        'self_assessment_form': '社团自查表',
        'club_constitution': '社团章程',
        'leader_learning_work_report': '负责人学习及工作情况表',
        'annual_activity_list': '社团年度活动清单',
        'advisor_performance_report': '指导教师履职情况表',
        'financial_report': '年度财务情况表',
        'member_composition_list': '社团成员构成表',
        'new_media_account_report': '新媒体账号及运维情况表',
        'other_materials': '其他材料',
        # 新社团申请材料
        'establishment_application': '社团成立申请表',
        'constitution_draft': '社团章程草案',
        'three_year_plan': '社团三年发展规划',
        'leaders_resumes': '负责人和指导老师简历',
        'one_month_activity_plan': '一个月活动计划',
        'advisor_certificates': '指导老师专业证书',
        # 社团注册材料
        'registration_form': '社团注册申请表',
        'basic_info_form': '学生社团基础信息表',
        'membership_fee_form': '会费表或免收会费说明表',
        'fee_form': '会费表或免收会费说明表',
        'leader_change_application': '社团主要负责人变动申请表',
        'leader_change_form': '社团主要负责人变动申请表',
        'meeting_minutes': '社团大会会议记录',
        'name_change_application': '社团名称变更申请表',
        'name_change_form': '社团名称变更申请表',
        'advisor_change_application': '社团指导老师变动申请表',
        'advisor_change_form': '社团指导老师变动申请表',
        'business_advisor_change_application': '社团业务指导单位变动申请表',
        'business_unit_change_form': '社团业务指导单位变动申请表',
        'new_media_application': '新媒体平台建立申请表',
        'new_media_form': '新媒体平台建立申请表',
    }
    return material_names.get(field_name, field_name)


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
    return file_url

# Emoji到Material Design图标的映射
EMOJI_TO_ICON = {
    '📋': 'assignment',
    '📚': 'book',
    '👥': 'group',
    '💰': 'attach_money',
    '🎯': 'flag',
    '📝': 'edit',
    '⚠️': 'warning',
    '🚨': 'error',
    '🔒': 'lock',
    '🔓': 'lock_open',
    '🏠': 'home',
    '⚙️': 'settings',
    '✅': 'check_circle',
    '🔧': 'build',
    '📊': 'bar_chart',
    '📁': 'folder',
    '🗑️': 'delete',
}

@register.filter(name='emoji_to_icon')
def emoji_to_icon(text):
    """
    将文本中的emoji转换为Material Design图标
    """
    if not text:
        return text
    
    result = str(text)
    for emoji, icon_name in EMOJI_TO_ICON.items():
        if emoji in result:
            icon_html = f'<span class="material-icons" style="font-size: inherit; vertical-align: middle;">{icon_name}</span>'
            result = result.replace(emoji, icon_html)
    
    return result


@register.filter(name='safe_emoji_to_icon')
def safe_emoji_to_icon(text):
    """
    将文本中的emoji转换为Material Design图标，并标记为安全
    """
    from django.utils.safestring import mark_safe
    return mark_safe(emoji_to_icon(text))

@register.filter
def concat_str(value, arg):
    """字符串拼接"""
    return str(value) + str(arg)
