# Generated manually for channel alert settings.

from django.db import migrations, models


def enable_alert_for_builtin_channels(apps, schema_editor):
    FormChannel = apps.get_model('clubs', 'FormChannel')
    FormChannel.objects.filter(builtin_action='annual_review').update(
        show_unsubmitted_alert=True,
        alert_color='#9a6700',
    )
    FormChannel.objects.filter(builtin_action='club_registration').update(
        show_unsubmitted_alert=True,
        alert_color='#b3261e',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('clubs', '0030_channelexamplefile'),
    ]

    operations = [
        migrations.AddField(
            model_name='formchannel',
            name='show_unsubmitted_alert',
            field=models.BooleanField(default=False, verbose_name='显示未提交告警'),
        ),
        migrations.AddField(
            model_name='formchannel',
            name='alert_color',
            field=models.CharField(default='#b3261e', max_length=20, verbose_name='告警颜色'),
        ),
        migrations.RunPython(enable_alert_for_builtin_channels, migrations.RunPython.noop),
    ]
