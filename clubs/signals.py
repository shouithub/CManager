from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """当User创建时，自动创建UserProfile"""
    if created:
        # 如果是superuser，设置为admin角色，并提供默认值
        if instance.is_superuser:
            role = 'admin'
            student_id = f"ADMIN_{instance.username}"
            real_name = instance.username
            phone = '00000000000'
            wechat = instance.username
            political_status = 'non_member'
            status = 'approved'
        else:
            role = 'president'
            # 对于普通用户，不在这里创建，因为注册时会创建
            return
        
        UserProfile.objects.create(
            user=instance,
            role=role,
            status=status,
            real_name=real_name,
            student_id=student_id,
            phone=phone,
            wechat=wechat,
            political_status=political_status
        )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """当User保存时，保存UserProfile"""
    # 只处理超级用户，且仅当profile存在时保存
    if instance.is_superuser:
        try:
            instance.profile.save()
        except UserProfile.DoesNotExist:
            # 为超级用户创建profile
            UserProfile.objects.create(
                user=instance,
                role='admin',
                status='approved',
                real_name=instance.username,
                student_id=f"ADMIN_{instance.username}",
                phone='00000000000',
                wechat=instance.username,
                political_status='non_member'
            )