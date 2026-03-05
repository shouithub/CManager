from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clubs', '0002_initial_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='club',
            name='president',
        ),
    ]
