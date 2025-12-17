from django import template

register = template.Library()

@register.inclusion_tag('clubs/staff/_submitted_files.html')
def render_submitted_files(zip_download_url=None, files_format='cards', submission=None, registration=None, club_registration=None):
    """
    渲染提交的文件列表
    
    参数:
    - zip_download_url: 打包下载的URL
    - files_format: 展示格式，可选 'cards' 或 'list'
    - submission: 年审提交对象
    - registration: 注册申请对象
    - club_registration: 新注册申请对象
    """
    return {
        'zip_download_url': zip_download_url,
        'files_format': files_format,
        'submission': submission,
        'registration': registration,
        'club_registration': club_registration
    }
