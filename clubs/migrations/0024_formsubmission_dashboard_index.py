from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clubs', '0023_explicit_unique_constraints'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='formsubmission',
            index=models.Index(
                fields=['submitter', 'club', 'channel', '-submitted_at'],
                name='fs_submit_club_chan_date',
            ),
        ),
    ]
