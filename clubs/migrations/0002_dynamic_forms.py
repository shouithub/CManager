from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


DEFAULT_CHANNELS = [
    ('社团年审', 'annual-review', 'assignment', 'annual_review', 10, [
        ('submission_year', '提交年份', 'number', True, 10, {}, {'min': 2000, 'max': 2100}),
        ('self_assessment_form', '自查表', 'file', True, 20, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        ('club_constitution', '社团章程', 'file', True, 30, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        ('leader_learning_work_report', '负责人学习及工作情况表', 'file', True, 40, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        ('annual_activity_list', '年度活动清单', 'file', True, 50, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf', '.xls', '.xlsx'], 'max_size_mb': 10}),
        ('advisor_performance_report', '指导教师履职情况表', 'file', True, 60, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        ('financial_report', '年度财务情况表', 'file', True, 70, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf', '.xls', '.xlsx'], 'max_size_mb': 10}),
        ('member_composition_list', '成员构成表', 'file', True, 80, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf', '.xls', '.xlsx'], 'max_size_mb': 10}),
        ('new_media_account_report', '新媒体账号及运维情况表', 'file', True, 90, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        ('other_materials', '其他材料', 'file', False, 100, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf', '.jpg', '.png', '.zip'], 'max_size_mb': 20}),
    ]),
    ('社团注册', 'registration', 'add_circle', 'club_registration', 20, [
        ('registration_form', '社团注册申请表', 'file', True, 10, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        ('basic_info_form', '社团基础信息表', 'file', True, 20, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf', '.xls', '.xlsx'], 'max_size_mb': 10}),
        ('fee_form', '会费表或免收会费说明', 'file', False, 30, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf', '.xls', '.xlsx'], 'max_size_mb': 10}),
        ('meeting_minutes', '社团大会会议记录', 'file', False, 40, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        ('other_materials', '其他补充材料', 'file', False, 50, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf', '.zip'], 'max_size_mb': 20}),
    ]),
    ('社团申请', 'application', 'create', 'club_application', 30, [
        ('club_name', '拟成立社团名称', 'text', True, 10, {}, {'max_length': 100}),
        ('club_description', '社团简介', 'textarea', True, 20, {}, {}),
        ('president_name', '负责人姓名', 'text', True, 30, {}, {'max_length': 100}),
        ('president_student_id', '负责人学号', 'text', True, 40, {}, {'max_length': 50}),
        ('contact_phone', '联系电话', 'text', True, 50, {}, {'max_length': 30}),
        ('establishment_application', '社团成立申请书', 'file', True, 60, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        ('constitution_draft', '社团章程草案', 'file', True, 70, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        ('three_year_plan', '三年发展规划', 'file', True, 80, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
    ]),
    ('报销申请', 'reimbursement', 'receipt', 'reimbursement', 40, [
        ('submission_date', '报销日期', 'date', True, 10, {}, {}),
        ('reimbursement_amount', '报销金额', 'number', True, 20, {}, {'min': 0, 'step': '0.01'}),
        ('description', '报销说明', 'textarea', True, 30, {}, {}),
        ('receipt_file', '报销凭证', 'file', True, 40, {}, {'allowed_extensions': ['.pdf', '.jpg', '.jpeg', '.png', '.zip'], 'max_size_mb': 20}),
    ]),
    ('社长换届', 'president-transition', 'swap_horiz', 'president_transition', 60, [
        ('new_president_name', '新社长姓名', 'text', True, 10, {}, {'max_length': 100}),
        ('new_president_student_id', '新社长学号', 'text', True, 20, {}, {'max_length': 50}),
        ('new_president_phone', '新社长电话', 'text', False, 30, {}, {'max_length': 30}),
        ('transition_date', '换届日期', 'date', True, 40, {}, {}),
        ('reason', '换届说明', 'textarea', True, 50, {}, {}),
        ('transition_file', '换届材料', 'file', False, 60, {}, {'allowed_extensions': ['.doc', '.docx', '.pdf', '.zip'], 'max_size_mb': 20}),
    ]),
]


def seed_channels(apps, schema_editor):
    FormChannel = apps.get_model('clubs', 'FormChannel')
    FormField = apps.get_model('clubs', 'FormField')
    for name, slug, icon, action, order, fields in DEFAULT_CHANNELS:
        channel, _ = FormChannel.objects.update_or_create(
            slug=slug,
            defaults={
                'name': name,
                'icon': icon,
                'description': f'{name}默认动态提交通道',
                'order': order,
                'is_active': True,
                'is_builtin': True,
                'builtin_action': action,
            },
        )
        for key, label, field_type, required, field_order, options, validation in fields:
            FormField.objects.update_or_create(
                channel=channel,
                field_key=key,
                defaults={
                    'label': label,
                    'field_type': field_type,
                    'required': required,
                    'order': field_order,
                    'options': options if isinstance(options, list) else [],
                    'validation': validation,
                    'is_active': True,
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ('clubs', '0001_init'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FormChannel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='通道名称')),
                ('slug', models.SlugField(max_length=80, unique=True, verbose_name='通道标识')),
                ('icon', models.CharField(default='description', max_length=50, verbose_name='图标')),
                ('description', models.TextField(blank=True, verbose_name='说明')),
                ('order', models.IntegerField(default=0, verbose_name='排序')),
                ('is_active', models.BooleanField(default=True, verbose_name='启用')),
                ('is_builtin', models.BooleanField(default=False, verbose_name='内置通道')),
                ('builtin_action', models.CharField(choices=[('none', '无'), ('annual_review', '社团年审'), ('club_registration', '社团注册'), ('club_application', '社团申请'), ('reimbursement', '报销申请'), ('president_transition', '社长换届')], default='none', max_length=50, verbose_name='内置动作')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={'verbose_name': '提交通道', 'verbose_name_plural': '提交通道', 'ordering': ['order', 'id']},
        ),
        migrations.CreateModel(
            name='FormField',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=120, verbose_name='字段名称')),
                ('field_key', models.SlugField(max_length=80, verbose_name='字段标识')),
                ('field_type', models.CharField(choices=[('text', '单行文本'), ('textarea', '多行文本'), ('number', '数字'), ('date', '日期'), ('time', '时间'), ('select', '下拉选择'), ('radio', '单选'), ('checkbox', '多选'), ('file', '文件')], max_length=20, verbose_name='字段类型')),
                ('required', models.BooleanField(default=True, verbose_name='必填')),
                ('order', models.IntegerField(default=0, verbose_name='排序')),
                ('help_text', models.TextField(blank=True, verbose_name='提示')),
                ('placeholder', models.CharField(blank=True, max_length=200, verbose_name='占位提示')),
                ('options', models.JSONField(blank=True, default=list, verbose_name='选项')),
                ('validation', models.JSONField(blank=True, default=dict, verbose_name='校验规则')),
                ('example_file', models.FileField(blank=True, null=True, upload_to='form_examples/%Y/%m/', verbose_name='示例文件')),
                ('is_active', models.BooleanField(default=True, verbose_name='启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('channel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fields', to='clubs.formchannel', verbose_name='所属通道')),
            ],
            options={'verbose_name': '表单字段', 'verbose_name_plural': '表单字段', 'ordering': ['channel', 'order', 'id'], 'unique_together': {('channel', 'field_key')}},
        ),
        migrations.CreateModel(
            name='FormSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', '待审核'), ('approved', '已通过'), ('rejected', '已拒绝')], default='pending', max_length=20, verbose_name='状态')),
                ('review_comment', models.TextField(blank=True, verbose_name='审核意见')),
                ('submitted_at', models.DateTimeField(auto_now_add=True, verbose_name='提交时间')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='审核时间')),
                ('resubmission_count', models.IntegerField(default=1, verbose_name='提交次数')),
                ('is_read', models.BooleanField(default=False, verbose_name='已读')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='扩展信息')),
                ('channel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='clubs.formchannel', verbose_name='通道')),
                ('club', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='form_submissions', to='clubs.club', verbose_name='社团')),
                ('reviewer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_form_submissions', to=settings.AUTH_USER_MODEL, verbose_name='审核人')),
                ('submitter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='form_submissions', to=settings.AUTH_USER_MODEL, verbose_name='提交人')),
            ],
            options={'verbose_name': '动态表单提交', 'verbose_name_plural': '动态表单提交', 'ordering': ['-submitted_at']},
        ),
        migrations.CreateModel(
            name='FormFieldValue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value_text', models.TextField(blank=True, verbose_name='文本值')),
                ('value_json', models.JSONField(blank=True, default=dict, verbose_name='结构化值')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('field', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='values', to='clubs.formfield', verbose_name='字段')),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='values', to='clubs.formsubmission', verbose_name='提交')),
            ],
            options={'verbose_name': '表单字段值', 'verbose_name_plural': '表单字段值', 'unique_together': {('submission', 'field')}},
        ),
        migrations.CreateModel(
            name='FormUploadedFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='form_submissions/%Y/%m/', verbose_name='文件')),
                ('original_name', models.CharField(blank=True, max_length=255, verbose_name='原始文件名')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='上传时间')),
                ('field', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='uploaded_files', to='clubs.formfield', verbose_name='字段')),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='uploaded_files', to='clubs.formsubmission', verbose_name='提交')),
            ],
            options={'verbose_name': '表单上传文件', 'verbose_name_plural': '表单上传文件', 'ordering': ['uploaded_at']},
        ),
        migrations.DeleteModel(name='ActivityApplicationHistory'),
        migrations.DeleteModel(name='ActivityRegistration'),
        migrations.DeleteModel(name='ClubApplicationReview'),
        migrations.DeleteModel(name='ClubRegistrationReview'),
        migrations.DeleteModel(name='SubmittedFile'),
        migrations.DeleteModel(name='SubmissionReview'),
        migrations.DeleteModel(name='PresidentTransition'),
        migrations.DeleteModel(name='ActivityApplication'),
        migrations.DeleteModel(name='ClubRegistration'),
        migrations.DeleteModel(name='ClubRegistrationRequest'),
        migrations.DeleteModel(name='ReimbursementHistory'),
        migrations.DeleteModel(name='Reimbursement'),
        migrations.DeleteModel(name='ReviewSubmission'),
        migrations.DeleteModel(name='MaterialRequirement'),
        migrations.CreateModel(
            name='ActivityRegistration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('registered_at', models.DateTimeField(auto_now_add=True, verbose_name='报名时间')),
                ('activity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='registrations', to='clubs.formsubmission', verbose_name='活动')),
                ('user_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_registrations', to='clubs.userprofile', verbose_name='报名用户')),
            ],
            options={'verbose_name': '活动报名', 'verbose_name_plural': '活动报名', 'unique_together': {('activity', 'user_profile')}},
        ),
        migrations.AddIndex(model_name='formsubmission', index=models.Index(fields=['channel', 'status', '-submitted_at'], name='fs_channel_status_idx')),
        migrations.AddIndex(model_name='formsubmission', index=models.Index(fields=['club', 'status', '-submitted_at'], name='fs_club_status_idx')),
        migrations.RunPython(seed_channels, migrations.RunPython.noop),
    ]
