# Generated migration to consolidate name fields

from django.db import migrations


def migrate_names(apps, schema_editor):
    """迁移现有数据：将first_name和last_name合并到real_name"""
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('clubs', 'UserProfile')
    
    for profile in UserProfile.objects.all():
        if not profile.real_name:
            # 如果real_name为空，则使用User的first_name和last_name
            full_name = f"{profile.user.last_name}{profile.user.first_name}".strip()
            if full_name:
                profile.real_name = full_name
                profile.save()


def reverse_migrate(apps, schema_editor):
    """反向迁移（不需要做任何事情）"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('clubs', '0012_alter_clubregistration_status'),
    ]

    operations = [
        migrations.RunPython(migrate_names, reverse_migrate),
    ]
