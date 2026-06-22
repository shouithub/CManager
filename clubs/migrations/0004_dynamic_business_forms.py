from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def reset_and_seed_channels(apps, schema_editor):
    FormChannel = apps.get_model('clubs', 'FormChannel')
    FormField = apps.get_model('clubs', 'FormField')
    FormCycle = apps.get_model('clubs', 'FormCycle')
    FormSubmission = apps.get_model('clubs', 'FormSubmission')

    FormSubmission.objects.all().delete()
    FormChannel.objects.all().delete()

    default_channels = [
        ('社团年审', 'annual-review', 'assignment', 'annual_review', 'once_per_cycle', 10, [
            ('submission_year', '提交年度', 'number', True, 10, [], {'min': 2000, 'max': 2100}),
            ('self_assessment_form', '自查表', 'file', True, 20, [], {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
            ('club_constitution', '社团章程', 'file', True, 30, [], {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
            ('annual_activity_list', '社团年度活动清单', 'file', True, 40, [], {'allowed_extensions': ['.doc', '.docx', '.pdf', '.xls', '.xlsx'], 'max_size_mb': 10}),
            ('financial_report', '年度财务情况表', 'file', True, 50, [], {'allowed_extensions': ['.doc', '.docx', '.pdf', '.xls', '.xlsx'], 'max_size_mb': 10}),
            ('other_materials', '其他材料', 'file', False, 60, [], {'allowed_extensions': ['.doc', '.docx', '.pdf', '.jpg', '.png', '.zip'], 'max_size_mb': 20}),
        ]),
        ('社团注册', 'registration', 'add_circle', 'club_registration', 'once_per_cycle', 20, [
            ('registration_form', '社团注册申请表', 'file', True, 10, [], {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
            ('basic_info_form', '学生社团基础信息表', 'file', True, 20, [], {'allowed_extensions': ['.doc', '.docx', '.pdf', '.xls', '.xlsx'], 'max_size_mb': 10}),
            ('fee_form', '会费表或免收会费说明书', 'file', False, 30, [], {'allowed_extensions': ['.doc', '.docx', '.pdf', '.xls', '.xlsx'], 'max_size_mb': 10}),
            ('meeting_minutes', '社团大会会议记录', 'file', False, 40, [], {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
            ('other_materials', '其他注册材料', 'file', False, 50, [], {'allowed_extensions': ['.doc', '.docx', '.pdf', '.zip'], 'max_size_mb': 20}),
        ]),
        ('社团申请', 'application', 'create', 'club_application', 'repeatable', 30, [
            ('club_name', '拟成立社团名称', 'text', True, 10, [], {'max_length': 100}),
            ('club_description', '社团简介', 'textarea', True, 20, [], {}),
            ('president_name', '负责人姓名', 'text', True, 30, [], {'max_length': 100}),
            ('president_student_id', '负责人学号', 'text', True, 40, [], {'max_length': 50}),
            ('contact_phone', '联系电话', 'text', True, 50, [], {'max_length': 30}),
            ('establishment_application', '社团成立申请书', 'file', True, 60, [], {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
            ('constitution_draft', '社团章程草案', 'file', True, 70, [], {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
            ('three_year_plan', '三年发展规划', 'file', True, 80, [], {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        ]),
        ('报销申请', 'reimbursement', 'receipt', 'reimbursement', 'repeatable', 40, [
            ('submission_date', '申请日期', 'date', True, 10, [], {}),
            ('reimbursement_amount', '报销金额', 'number', True, 20, [], {'min': 0, 'step': '0.01'}),
            ('description', '报销说明', 'textarea', True, 30, [], {}),
            ('receipt_file', '报销凭证', 'file', True, 40, [], {'allowed_extensions': ['.pdf', '.jpg', '.jpeg', '.png', '.zip'], 'max_size_mb': 20}),
        ]),
        ('活动申请', 'activity-application', 'event', 'activity_application', 'repeatable', 50, [
            ('activity_name', '活动名称', 'text', True, 10, [], {'max_length': 200}),
            ('activity_type', '活动类型', 'select', True, 20, ['讲座', '比赛', '演出', '培训', '志愿服务', '其他'], {}),
            ('activity_description', '活动描述', 'textarea', True, 30, [], {}),
            ('activity_date', '活动日期', 'date', True, 40, [], {}),
            ('activity_time_start', '开始时间', 'time', True, 50, [], {}),
            ('activity_time_end', '结束时间', 'time', True, 60, [], {}),
            ('activity_location', '活动地点', 'text', True, 70, [], {'max_length': 200}),
            ('expected_participants', '预计参与人数', 'number', False, 80, [], {'min': 0, 'step': 1}),
            ('budget', '活动预算', 'number', False, 90, [], {'min': 0, 'step': '0.01'}),
            ('contact_person', '联系人', 'text', True, 100, [], {'max_length': 100}),
            ('contact_phone', '联系电话', 'text', False, 110, [], {'max_length': 30}),
            ('is_public', '是否公开报名', 'select', False, 120, ['公开', '仅社团成员'], {}),
            ('application_form', '活动申请材料', 'file', False, 130, [], {'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        ]),
        ('社长换届', 'president-transition', 'swap_horiz', 'president_transition', 'repeatable', 60, [
            ('new_president_name', '新社长姓名', 'text', True, 10, [], {'max_length': 100}),
            ('new_president_student_id', '新社长学号', 'text', True, 20, [], {'max_length': 50}),
            ('new_president_phone', '新社长电话', 'text', False, 30, [], {'max_length': 30}),
            ('transition_date', '换届日期', 'date', True, 40, [], {}),
            ('reason', '换届说明', 'textarea', True, 50, [], {}),
            ('transition_file', '换届材料', 'file', False, 60, [], {'allowed_extensions': ['.doc', '.docx', '.pdf', '.zip'], 'max_size_mb': 20}),
        ]),
    ]

    for name, slug, icon, action, policy, order, fields in default_channels:
        channel = FormChannel.objects.create(
            name=name,
            slug=slug,
            icon=icon,
            description=f'{name}默认动态提交通道',
            order=order,
            is_active=True,
            is_builtin=True,
            builtin_action=action,
            submission_policy=policy,
        )
        for key, label, field_type, required, field_order, options, validation in fields:
            FormField.objects.create(
                channel=channel,
                field_key=key,
                label=label,
                field_type=field_type,
                required=required,
                order=field_order,
                options=options,
                validation=validation,
                is_active=True,
            )
        if policy == 'once_per_cycle':
            FormCycle.objects.create(channel=channel, name=f'{name}默认周期', sequence=1, is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ('clubs', '0003_restore_activity_applications'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='formchannel',
            name='submission_policy',
            field=models.CharField(choices=[('repeatable', '可重复提交'), ('once_total', '仅提交一次'), ('once_per_cycle', '每周期提交一次')], default='repeatable', max_length=20, verbose_name='提交策略'),
        ),
        migrations.AlterField(
            model_name='formchannel',
            name='builtin_action',
            field=models.CharField(choices=[('none', '无'), ('annual_review', '社团年审'), ('club_registration', '社团注册'), ('club_application', '社团申请'), ('reimbursement', '报销申请'), ('activity_application', '活动申请'), ('president_transition', '社长换届')], default='none', max_length=50, verbose_name='内置动作'),
        ),
        migrations.CreateModel(
            name='FormCycle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='周期名称')),
                ('sequence', models.PositiveIntegerField(default=1, verbose_name='周期序号')),
                ('is_active', models.BooleanField(default=True, verbose_name='启用')),
                ('starts_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='开始时间')),
                ('ends_at', models.DateTimeField(blank=True, null=True, verbose_name='结束时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('channel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cycles', to='clubs.formchannel', verbose_name='通道')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_form_cycles', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
            ],
            options={
                'verbose_name': '表单周期',
                'verbose_name_plural': '表单周期',
                'ordering': ['channel', '-sequence', '-starts_at'],
                'unique_together': {('channel', 'sequence')},
            },
        ),
        migrations.AddField(
            model_name='formsubmission',
            name='cycle',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='submissions', to='clubs.formcycle', verbose_name='周期'),
        ),
        migrations.CreateModel(
            name='FormChannelClubState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_enabled', models.BooleanField(default=True, verbose_name='启用')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('channel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='club_states', to='clubs.formchannel', verbose_name='通道')),
                ('club', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='form_channel_states', to='clubs.club', verbose_name='社团')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_form_channel_states', to=settings.AUTH_USER_MODEL, verbose_name='更新人')),
            ],
            options={
                'verbose_name': '社团通道状态',
                'verbose_name_plural': '社团通道状态',
                'unique_together': {('channel', 'club')},
            },
        ),
        migrations.CreateModel(
            name='PublishedActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity_name', models.CharField(max_length=200, verbose_name='活动名称')),
                ('activity_type', models.CharField(choices=[('讲座', '讲座'), ('比赛', '比赛'), ('演出', '演出'), ('培训', '培训'), ('志愿服务', '志愿服务'), ('other', '其他')], default='other', max_length=40, verbose_name='活动类型')),
                ('activity_description', models.TextField(verbose_name='活动描述')),
                ('activity_date', models.DateField(verbose_name='活动日期')),
                ('activity_time_start', models.TimeField(verbose_name='活动开始时间')),
                ('activity_time_end', models.TimeField(verbose_name='活动结束时间')),
                ('activity_location', models.CharField(max_length=200, verbose_name='活动地点')),
                ('expected_participants', models.IntegerField(default=0, verbose_name='预计参与人数')),
                ('budget', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='活动预算')),
                ('contact_person', models.CharField(max_length=100, verbose_name='联系人')),
                ('contact_phone', models.CharField(blank=True, max_length=20, verbose_name='联系电话')),
                ('is_public', models.BooleanField(default=False, verbose_name='是否公开报名')),
                ('published_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='发布时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('club', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='published_activities', to='clubs.club', verbose_name='社团')),
                ('source_submission', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='published_activity', to='clubs.formsubmission', verbose_name='来源提交')),
            ],
            options={
                'verbose_name': '已发布活动',
                'verbose_name_plural': '已发布活动',
                'ordering': ['-activity_date', '-published_at'],
            },
        ),
        migrations.DeleteModel(name='ActivityRegistration'),
        migrations.DeleteModel(name='ActivityApplication'),
        migrations.DeleteModel(name='RegistrationPeriod'),
        migrations.CreateModel(
            name='ActivityRegistration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('registered_at', models.DateTimeField(auto_now_add=True, verbose_name='报名时间')),
                ('activity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='registrations', to='clubs.publishedactivity', verbose_name='活动')),
                ('user_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_registrations', to='clubs.userprofile', verbose_name='报名用户')),
            ],
            options={
                'verbose_name': '活动报名',
                'verbose_name_plural': '活动报名',
                'unique_together': {('activity', 'user_profile')},
            },
        ),
        migrations.AddIndex(
            model_name='formsubmission',
            index=models.Index(fields=['channel', 'club', 'cycle', 'status'], name='fs_policy_scope_idx'),
        ),
        migrations.RunPython(reset_and_seed_channels, migrations.RunPython.noop),
    ]
