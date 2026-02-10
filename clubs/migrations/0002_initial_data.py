from django.db import migrations


def populate_departments(apps, schema_editor):
    Department = apps.get_model('clubs', 'Department')

    dept_mapping = {
        'office': {'name': '办公室', 'description': '负责社团日常事务管理', 'icon': 'business', 'order': 1},
        'review': {'name': '评审部', 'description': '负责社团活动评审', 'icon': 'rate_review', 'order': 2},
        'activity': {'name': '活动部', 'description': '负责社团活动策划与执行', 'icon': 'event', 'order': 3},
        'organization': {'name': '组织部', 'description': '负责社团组织建设', 'icon': 'group', 'order': 4},
        'propaganda': {'name': '宣传部', 'description': '负责社团对外宣传', 'icon': 'campaign', 'order': 5},
    }

    for code, info in dept_mapping.items():
        Department.objects.get_or_create(
            name=info['name'],
            defaults={
                'description': info['description'],
                'icon': info['icon'],
                'order': info['order'],
            },
        )


def populate_requirements(apps, schema_editor):
    MaterialRequirement = apps.get_model('clubs', 'MaterialRequirement')

    requirements = [
        {
            'request_type': 'annual_review',
            'name': '自查表',
            'is_required': True,
            'legacy_field_name': 'self_assessment_form',
            'order': 10,
        },
        {
            'request_type': 'annual_review',
            'name': '社团章程',
            'is_required': True,
            'legacy_field_name': 'club_constitution',
            'order': 20,
        },
        {
            'request_type': 'annual_review',
            'name': '负责人学习及工作情况表',
            'is_required': True,
            'legacy_field_name': 'leader_learning_work_report',
            'order': 30,
        },
        {
            'request_type': 'annual_review',
            'name': '社团年度活动清单',
            'is_required': True,
            'legacy_field_name': 'annual_activity_list',
            'order': 40,
        },
        {
            'request_type': 'annual_review',
            'name': '指导教师履职情况表',
            'is_required': True,
            'legacy_field_name': 'advisor_performance_report',
            'order': 50,
        },
        {
            'request_type': 'annual_review',
            'name': '年度财务情况表',
            'is_required': True,
            'legacy_field_name': 'financial_report',
            'order': 60,
        },
        {
            'request_type': 'annual_review',
            'name': '社团成员构成表',
            'is_required': True,
            'legacy_field_name': 'member_composition_list',
            'order': 70,
        },
        {
            'request_type': 'annual_review',
            'name': '新媒体账号及运维情况表',
            'is_required': True,
            'legacy_field_name': 'new_media_account_report',
            'order': 80,
        },
        {
            'request_type': 'annual_review',
            'name': '其他材料',
            'is_required': False,
            'legacy_field_name': 'other_materials',
            'order': 90,
        },
        {
            'request_type': 'club_registration',
            'name': '社团注册申请表',
            'is_required': True,
            'legacy_field_name': 'registration_form',
            'order': 10,
        },
        {
            'request_type': 'club_registration',
            'name': '学生社团基础信息表',
            'is_required': True,
            'legacy_field_name': 'basic_info_form',
            'order': 20,
        },
        {
            'request_type': 'club_registration',
            'name': '会费表或免收会费说明书',
            'is_required': True,
            'legacy_field_name': 'membership_fee_form',
            'order': 30,
        },
        {
            'request_type': 'club_registration',
            'name': '社团主要负责人变动申请',
            'is_required': False,
            'legacy_field_name': 'leader_change_application',
            'order': 40,
        },
        {
            'request_type': 'club_registration',
            'name': '社团大会会议记录',
            'is_required': False,
            'legacy_field_name': 'meeting_minutes',
            'order': 50,
        },
        {
            'request_type': 'club_registration',
            'name': '社团名称变更申请表',
            'is_required': False,
            'legacy_field_name': 'name_change_application',
            'order': 60,
        },
        {
            'request_type': 'club_registration',
            'name': '社团指导老师变动申请表',
            'is_required': False,
            'legacy_field_name': 'advisor_change_application',
            'order': 70,
        },
        {
            'request_type': 'club_registration',
            'name': '社团业务指导单位变动申请表',
            'is_required': False,
            'legacy_field_name': 'business_advisor_change_application',
            'order': 80,
        },
        {
            'request_type': 'club_registration',
            'name': '新媒体平台建立申请表',
            'is_required': False,
            'legacy_field_name': 'new_media_application',
            'order': 90,
        },
        {
            'request_type': 'club_application',
            'name': '社团成立申请书',
            'is_required': True,
            'legacy_field_name': 'establishment_application',
            'order': 10,
        },
        {
            'request_type': 'club_application',
            'name': '社团章程草案',
            'is_required': True,
            'legacy_field_name': 'constitution_draft',
            'order': 20,
        },
        {
            'request_type': 'club_application',
            'name': '社团三年发展规划',
            'is_required': True,
            'legacy_field_name': 'three_year_plan',
            'order': 30,
        },
        {
            'request_type': 'club_application',
            'name': '社团拟任负责人和指导老师的详细简历和身份证复印件',
            'is_required': True,
            'legacy_field_name': 'leaders_resumes',
            'allowed_extensions': '.zip,.rar,.docx',
            'order': 40,
        },
        {
            'request_type': 'club_application',
            'name': '社团组建一个月后的活动计划',
            'is_required': True,
            'legacy_field_name': 'one_month_activity_plan',
            'order': 50,
        },
        {
            'request_type': 'club_application',
            'name': '社团老师的相关专业证书',
            'is_required': True,
            'legacy_field_name': 'advisor_certificates',
            'allowed_extensions': '.zip,.rar,.jpg,.png',
            'order': 60,
        },
        {
            'request_type': 'info_change',
            'name': '支持文件',
            'is_required': False,
            'legacy_field_name': 'supporting_document',
            'order': 10,
        },
        {
            'request_type': 'president_transition',
            'name': '社团主要负责人变动申请表',
            'is_required': True,
            'legacy_field_name': 'transition_form',
            'allowed_extensions': '.docx,.pdf',
            'order': 10,
        },
        {
            'request_type': 'reimbursement',
            'name': '报销凭证',
            'is_required': True,
            'legacy_field_name': 'receipt_file',
            'order': 10,
        },
        {
            'request_type': 'activity_application',
            'name': '活动申请表',
            'is_required': True,
            'legacy_field_name': 'application_form',
            'allowed_extensions': '.docx,.pdf',
            'order': 10,
        },
    ]

    for req in requirements:
        MaterialRequirement.objects.get_or_create(
            request_type=req['request_type'],
            name=req['name'],
            defaults={
                'is_required': req['is_required'],
                'legacy_field_name': req.get('legacy_field_name'),
                'order': req['order'],
                'allowed_extensions': req.get('allowed_extensions', '.docx,.pdf,.jpg,.png,.zip'),
            },
        )


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('clubs', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(populate_departments, reverse_func),
        migrations.RunPython(populate_requirements, reverse_func),
    ]
