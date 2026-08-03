from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clubs', '0018_avatar_service'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sitesettings',
            name='avatar_default_domain',
        ),
        migrations.RemoveField(
            model_name='sitesettings',
            name='avatar_provider',
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='cravatar_enabled',
            field=models.BooleanField(default=False, help_text='开启后，用户可在本站上传头像与 Cravatar 之间自行选择。', verbose_name='允许使用 Cravatar'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='avatar_source',
            field=models.CharField(choices=[('local', '本站上传'), ('cravatar', 'Cravatar')], default='local', max_length=20, verbose_name='头像来源'),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='avatar_email',
            field=models.EmailField(blank=True, default='', help_text='仅在用户选择 Cravatar 头像时使用，不公开显示邮箱明文。', max_length=254, verbose_name='Cravatar 邮箱'),
        ),
    ]
