from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clubs', '0017_formchannel_cycle_type_labels'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='avatar_default_domain',
            field=models.CharField(blank=True, default='', help_text='自动取自保存配置时访问本站所使用的域名。', max_length=255, verbose_name='匿名头像邮箱域名'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='avatar_provider',
            field=models.CharField(choices=[('local', '本站上传'), ('cravatar', 'Cravatar')], default='local', help_text='选择全站用户头像的显示来源。', max_length=20, verbose_name='头像服务'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='avatar_email',
            field=models.EmailField(blank=True, default='', help_text='仅用于 Cravatar 匹配；留空时使用站点生成的匿名邮箱。', max_length=254, verbose_name='头像服务邮箱'),
        ),
    ]
