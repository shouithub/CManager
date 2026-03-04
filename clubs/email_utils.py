"""
邮箱发送工具 - 使用SMTP配置发送邮件
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)


def send_email_with_config(config, to_email, subject, text_body, html_body=None, success_message='邮件发送成功'):
    """使用指定SMTP配置发送邮件。"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = config.sender_email
        msg['To'] = to_email

        msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        if html_body:
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        if config.smtp_port in [465, 994]:
            server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=15)
            server.ehlo()
        elif config.use_tls:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
            server.ehlo()

        server.login(config.sender_email, config.sender_password)
        server.sendmail(config.sender_email, [to_email], msg.as_string())
        server.quit()

        logger.info('邮件已发送到 %s', to_email)
        return True, success_message
    except smtplib.SMTPAuthenticationError:
        logger.error('SMTP认证失败')
        return False, 'SMTP认证失败，请检查邮箱配置'
    except smtplib.SMTPException as exc:
        logger.error('SMTP错误: %s', str(exc))
        return False, f'SMTP错误: {str(exc)}'
    except Exception as exc:
        logger.error('邮件发送错误: %s', str(exc))
        return False, f'邮件发送失败: {str(exc)}'


def send_test_email_with_config(config, to_email):
    """发送SMTP测试邮件。"""
    text = f'''您好！

这是一封来自 CManager 系统的测试邮件。

如果您收到了这封邮件，说明 SMTP 配置成功！

配置信息：
- 服务商：{config.get_provider_display() if hasattr(config, 'get_provider_display') else getattr(config, 'provider', '')}
- SMTP服务器：{config.smtp_host}:{config.smtp_port}
- 发送邮箱：{config.sender_email}
- TLS加密：{'已启用' if config.use_tls else '未启用'}

此邮件为系统自动发送，请勿回复。'''

    html = f'''<p>您好！</p>
<p>这是一封来自 <strong>CManager</strong> 系统的测试邮件。</p>
<p>如果您收到了这封邮件，说明 SMTP 配置成功。</p>
<hr>
<p>服务商：{config.get_provider_display() if hasattr(config, 'get_provider_display') else getattr(config, 'provider', '')}</p>
<p>SMTP服务器：{config.smtp_host}:{config.smtp_port}</p>
<p>发送邮箱：{config.sender_email}</p>
<p>TLS加密：{'已启用' if config.use_tls else '未启用'}</p>'''

    return send_email_with_config(
        config=config,
        to_email=to_email,
        subject='CManager SMTP配置测试邮件',
        text_body=text,
        html_body=html,
        success_message=f'测试邮件已成功发送到 {to_email}'
    )


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

    return send_email_with_config(
        config=config,
        to_email=to_email,
        subject='CManager - 邮箱验证码',
        text_body=text,
        html_body=html,
        success_message='验证码已发送到邮箱，请查收'
    )