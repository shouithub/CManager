from django.db.models.signals import post_delete, post_save
from django.db.models import FileField
from django.core.cache import cache
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import (
    Announcement,
    CarouselImage,
    Department,
    FormField,
    FormUploadedFile,
    StorageConfig,
    SiteSettings,
    UserProfile,
)


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


@receiver(post_save, sender=StorageConfig)
def invalidate_storage_config_cache(sender, **kwargs):
    from .storage_backends import clear_storage_config_cache
    clear_storage_config_cache()


@receiver([post_save, post_delete], sender=Announcement)
def invalidate_announcement_cache(sender, **kwargs):
    cache.delete('index:announcements:v1')


@receiver([post_save, post_delete], sender=CarouselImage)
def invalidate_carousel_cache(sender, **kwargs):
    cache.delete('index:carousel_images:v1')


@receiver([post_save, post_delete], sender=Department)
def invalidate_department_cache(sender, **kwargs):
    cache.delete('index:departments:v1')


@receiver([post_save, post_delete], sender=SiteSettings)
def invalidate_site_presentation_cache(sender, **kwargs):
    cache.delete('site:presentation:v1')


@receiver(post_delete, sender=UserProfile)
@receiver(post_delete, sender=FormUploadedFile)
@receiver(post_delete, sender=FormField)
@receiver(post_delete, sender=Announcement)
@receiver(post_delete, sender=CarouselImage)
def delete_file_fields_after_model_delete(sender, instance, **kwargs):
    """Remove storage objects when their owning database row is deleted."""
    for field in instance._meta.fields:
        if not isinstance(field, FileField):
            continue
        file_value = getattr(instance, field.name, None)
        if hasattr(file_value, 'delete') and getattr(file_value, 'name', ''):
            file_value.delete(save=False)
