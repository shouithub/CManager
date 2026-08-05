# Generated manually for low-member alert threshold setting.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clubs', '0031_formchannel_alert_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='low_member_alert_threshold',
            field=models.PositiveSmallIntegerField(
                default=20,
                help_text='成员数低于该值的社团会在干事社团管理页触发“社团成员数量预警”。',
                verbose_name='成员数量告警阈值',
            ),
        ),
    ]
