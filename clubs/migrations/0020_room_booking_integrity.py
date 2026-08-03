from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clubs', '0019_user_avatar_choice'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='roombooking',
            name='rb_room_date_idx',
        ),
        migrations.AddIndex(
            model_name='roombooking',
            index=models.Index(fields=['room', 'booking_date', 'status', 'start_time'], name='rb_conflict_idx'),
        ),
        migrations.AddConstraint(
            model_name='roombooking',
            constraint=models.CheckConstraint(condition=models.Q(participant_count__gt=0), name='room_booking_participants_positive'),
        ),
    ]
