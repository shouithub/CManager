from django.db import migrations

import clubs.crypto_fields


def encrypt_existing_credentials(apps, schema_editor):
    SMTPConfig = apps.get_model('clubs', 'SMTPConfig')
    StorageConfig = apps.get_model('clubs', 'StorageConfig')
    for config in SMTPConfig.objects.exclude(sender_password=''):
        SMTPConfig.objects.filter(pk=config.pk).update(sender_password=config.sender_password)
    for config in StorageConfig.objects.exclude(s3_secret_access_key=''):
        StorageConfig.objects.filter(pk=config.pk).update(s3_secret_access_key=config.s3_secret_access_key)


class Migration(migrations.Migration):

    dependencies = [
        ('clubs', '0020_room_booking_integrity'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smtpconfig',
            name='sender_password',
            field=clubs.crypto_fields.EncryptedCharField(help_text='在数据库中加密存储；留空表示保持原值', max_length=500, verbose_name='邮箱密码/授权码'),
        ),
        migrations.AlterField(
            model_name='storageconfig',
            name='s3_secret_access_key',
            field=clubs.crypto_fields.EncryptedCharField(blank=True, default='', help_text='在数据库中加密存储；管理页面不会回显原值', max_length=500, verbose_name='Secret Access Key'),
        ),
        migrations.RunPython(encrypt_existing_credentials, migrations.RunPython.noop),
    ]
