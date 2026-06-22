from django.db import migrations, models


def set_channel_defaults(apps, schema_editor):
    FormChannel = apps.get_model('clubs', 'FormChannel')
    defaults = {
        'annual-review': {
            'show_unsubmitted_status': True,
            'allow_staff_toggle': True,
            'cycle_type': 'year',
            'submission_policy': 'once_per_cycle',
        },
        'registration': {
            'show_unsubmitted_status': True,
            'allow_staff_toggle': True,
            'cycle_type': 'count',
            'submission_policy': 'once_per_cycle',
        },
        'application': {
            'show_unsubmitted_status': False,
            'allow_staff_toggle': False,
            'cycle_type': 'none',
        },
        'reimbursement': {
            'show_unsubmitted_status': False,
            'allow_staff_toggle': False,
            'cycle_type': 'none',
        },
        'activity-application': {
            'show_unsubmitted_status': False,
            'allow_staff_toggle': False,
            'cycle_type': 'none',
        },
        'president-transition': {
            'show_unsubmitted_status': False,
            'allow_staff_toggle': False,
            'cycle_type': 'none',
        },
    }
    for slug, values in defaults.items():
        FormChannel.objects.filter(slug=slug).update(**values)


class Migration(migrations.Migration):

    dependencies = [
        ('clubs', '0006_alter_publishedactivity_activity_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='formchannel',
            name='allow_staff_toggle',
            field=models.BooleanField(default=False, verbose_name='allow staff toggle'),
        ),
        migrations.AddField(
            model_name='formchannel',
            name='cycle_type',
            field=models.CharField(choices=[('none', 'No cycle'), ('count', 'Round count'), ('year', 'Year'), ('month', 'Month'), ('day', 'Day')], default='none', max_length=20, verbose_name='cycle type'),
        ),
        migrations.AddField(
            model_name='formchannel',
            name='show_unsubmitted_status',
            field=models.BooleanField(default=False, verbose_name='show unsubmitted status'),
        ),
        migrations.RunPython(set_channel_defaults, migrations.RunPython.noop),
    ]
