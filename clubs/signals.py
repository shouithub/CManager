from django.db.models.signals import post_delete, post_save
from django.db.models import FileField
from django.core.cache import cache
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import (
    Announcement,
    CarouselImage,
    ChannelExampleFile,
    Department,
    FormField,
    FormSubmission,
    FormUploadedFile,
    StorageConfig,
    SiteSettings,
    Template,
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


@receiver([post_save, post_delete], sender=UserProfile)
def invalidate_oobe_admin_cache(sender, **kwargs):
    """管理员档案变化后立即清除首启引导缓存，避免刚创建/删除管理员后仍被旧缓存拦截。"""
    cache.delete('oobe:has_admin')


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
@receiver(post_delete, sender=ChannelExampleFile)
@receiver(post_delete, sender=Template)
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


@receiver(post_delete, sender=FormSubmission)
def release_attempt_history_files(sender, instance, **kwargs):
    """提交被删除（含通道/社团/用户级联删除）时，释放历史快照中的引用。

    历史快照对内容寻址文件只增加引用（不复制），普通路径的打回文件则归档为
    独立副本；两者都记录在 ``metadata['attempt_history']`` 中。若只在这两条
    手动删除视图里释放，级联删除路径会导致引用泄漏、物理文件永不清理。
    """
    try:
        from .views.core import _delete_attempt_history_files
        _delete_attempt_history_files(instance)
    except Exception:
        # 删除提交不应被历史文件清理失败阻断；失败仅意味着物理文件可能保留
        import logging
        logging.getLogger(__name__).exception('释放提交历史文件引用失败')
