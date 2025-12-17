"""
邮箱发送工具 - 使用SMTP配置发送邮件
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_verification_email(to_email, code, username):
    """
    发送邮箱验证码
    
    Args:
        to_email: 目标邮箱
        code: 验证码
        username: 用户名
    
    Returns:
        (success, message)
    """
    from .models import SMTPConfig
    
    config = SMTPConfig.get_active_config()
    if not config:
        logger.error('没有激活的SMTP配置')
        return False, '邮箱服务未配置，请联系管理员'
    
    try:
        # 创建邮件
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'CManager - 邮箱验证码'
        msg['From'] = config.sender_email
        msg['To'] = to_email
        
        # 纯文本内容
        text = f"""
亲爱的 {username}，

感谢注册CManager系统。

您的邮箱验证码是：{code}

此验证码有效期为15分钟。

如果这不是您本人操作，请忽略此邮件。

CManager系统
"""
        
        # HTML内容
        html = f"""
        <html>
            <body>
                <p>亲爱的 {username}，</p>
                <p>感谢注册CManager系统。</p>
                <p>您的邮箱验证码是：<strong style="color: #ff6600; font-size: 24px;">{code}</strong></p>
                <p>此验证码有效期为15分钟。</p>
                <p>如果这不是您本人操作，请忽略此邮件。</p>
                <hr>
                <p>CManager系统</p>
            </body>
        </html>
        """
        
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # 连接SMTP服务器
        if config.use_tls:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=10)
        
        server.login(config.sender_email, config.sender_password)
        server.sendmail(config.sender_email, to_email, msg.as_string())
        server.quit()
        
        logger.info(f'验证码邮件已发送到 {to_email}')
        return True, '验证码已发送到邮箱，请查收'
    
    except smtplib.SMTPAuthenticationError:
        logger.error('SMTP认证失败')
        return False, 'SMTP认证失败，请检查邮箱配置'
    except smtplib.SMTPException as e:
        logger.error(f'SMTP错误: {str(e)}')
        return False, f'邮箱服务错误: {str(e)}'
    except Exception as e:
        logger.error(f'邮件发送错误: {str(e)}')
        return False, f'邮件发送失败: {str(e)}'
