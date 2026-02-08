"""
邮箱验证和SMTP配置相关模型
"""
import random
import string
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class EmailVerificationCode(models.Model):
    """邮箱验证码模型"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_verification', verbose_name='用户')
    email = models.EmailField(verbose_name='待验证邮箱')
    code = models.CharField(max_length=6, verbose_name='验证码')
    is_verified = models.BooleanField(default=False, verbose_name='是否已验证')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    expires_at = models.DateTimeField(verbose_name='过期时间')
    
    class Meta:
        verbose_name = '邮箱验证记录'
        verbose_name_plural = '邮箱验证记录'
    
    def __str__(self):
        return f"{self.user.username} - {self.email}"
    
    @staticmethod
    def generate_code():
        """生成6位随机验证码"""
        return ''.join(random.choices(string.digits, k=6))
    
    def is_expired(self):
        """检查验证码是否过期"""
        return timezone.now() > self.expires_at
    
    def verify(self, code):
        """验证码验证"""
        if self.is_verified:
            return False, "验证码已使用"
        if self.is_expired():
            return False, "验证码已过期"
        if code != self.code:
            return False, "验证码不正确"
        return True, "验证成功"


class SMTPConfig(models.Model):
    """SMTP邮箱配置"""
    PROVIDER_CHOICES = [
        ('qq', 'QQ邮箱'),
        ('163', '163邮箱'),
        ('outlook', 'Outlook'),
        ('gmail', 'Gmail'),
        ('custom', '自定义'),
    ]
    
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, verbose_name='邮箱服务商')
    smtp_host = models.CharField(max_length=100, verbose_name='SMTP服务器地址')
    smtp_port = models.IntegerField(verbose_name='SMTP端口')
    sender_email = models.EmailField(verbose_name='发送邮箱地址')
    sender_password = models.CharField(max_length=255, verbose_name='邮箱密码/授权码', help_text='某些邮箱需要使用授权码而非密码')
    use_tls = models.BooleanField(default=True, verbose_name='是否使用TLS加密')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'SMTP配置'
        verbose_name_plural = 'SMTP配置'
    
    def __str__(self) -> str:
        return f"{self.get_provider_display()} - {self.sender_email}"  # type: ignore[attr-defined]
    
    @classmethod
    def get_active_config(cls):
        """获取激活的SMTP配置"""
        return cls.objects.filter(is_active=True).first()
