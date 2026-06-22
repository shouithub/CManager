from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Callable

from django.db.models import Max
from django.utils import timezone


class BusinessActionError(Exception):
    """Raised when a dynamic form cannot run its bound business action."""


@dataclass(frozen=True)
class BusinessField:
    key: str
    label: str
    field_type: str
    required: bool = True
    order: int = 0
    options: list[str] = field(default_factory=list)
    validation: dict = field(default_factory=dict)
    placeholder: str = ''
    help_text: str = ''


@dataclass(frozen=True)
class BusinessFormAction:
    key: str
    label: str
    default_slug: str
    default_icon: str
    default_order: int
    default_policy: str
    default_description: str
    fields: list[BusinessField]
    show_unsubmitted_status: bool = False
    allow_staff_toggle: bool = False
    default_cycle_type: str = 'none'
    required_fields: tuple[str, ...] = ()
    on_approved: Callable | None = None


BUSINESS_FORM_ACTIONS: dict[str, BusinessFormAction] = {}


def register_business_form_action(action: BusinessFormAction) -> BusinessFormAction:
    BUSINESS_FORM_ACTIONS[action.key] = action
    return action


def get_business_action(key: str) -> BusinessFormAction | None:
    return BUSINESS_FORM_ACTIONS.get(key)


def get_business_action_choices():
    return [(key, action.label) for key, action in BUSINESS_FORM_ACTIONS.items()]


def missing_required_field_keys(channel) -> list[str]:
    action = get_business_action(channel.builtin_action)
    if not action:
        return []
    existing = set(channel.fields.filter(is_active=True).values_list('field_key', flat=True))
    return [key for key in action.required_fields if key not in existing]


def _date_value(value):
    if not value:
        return timezone.localdate()
    if hasattr(value, 'year'):
        return value
    return datetime.strptime(str(value), '%Y-%m-%d').date()


def _time_value(value):
    if not value:
        return datetime.strptime('00:00', '%H:%M').time()
    if hasattr(value, 'hour'):
        return value
    return datetime.strptime(str(value), '%H:%M').time()


def _int_value(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _decimal_value(value, default='0'):
    try:
        return Decimal(str(value or default))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _bool_value(value):
    if isinstance(value, list):
        value = value[0] if value else ''
    return str(value).strip() in {'公开', '是', 'true', 'True', '1', 'yes', 'on'}


def _ensure_required_values(submission, keys):
    missing = [key for key in keys if submission.field_value(key, '') in ('', [], {}, None)]
    if missing:
        raise BusinessActionError(f'业务动作缺少必填字段值：{", ".join(missing)}')


def approve_club_application(submission):
    from .models import Club, Officer

    _ensure_required_values(submission, ('club_name', 'club_description'))
    club_name = submission.field_value('club_name')
    if Club.objects.filter(name=club_name).exists():
        raise BusinessActionError('社团名称已存在，无法创建社团')
    club = Club.objects.create(
        name=club_name,
        description=submission.field_value('club_description', ''),
        founded_date=timezone.localdate(),
        status='active',
    )
    Officer.objects.create(
        club=club,
        user_profile=submission.submitter.profile,
        position='president',
        appointed_date=timezone.localdate(),
        is_current=True,
    )


def approve_president_transition(submission):
    from .models import Officer, UserProfile

    _ensure_required_values(submission, ('new_president_student_id',))
    student_id = submission.field_value('new_president_student_id')
    new_profile = UserProfile.objects.filter(student_id=student_id).first()
    if not new_profile:
        raise BusinessActionError('未找到新社长学号对应的用户')
    Officer.objects.filter(club=submission.club, position='president', is_current=True).update(
        is_current=False,
        end_date=timezone.localdate(),
    )
    Officer.objects.update_or_create(
        club=submission.club,
        user_profile=new_profile,
        position='president',
        defaults={'appointed_date': timezone.localdate(), 'end_date': None, 'is_current': True},
    )


def approve_activity_application(submission):
    from .models import PublishedActivity

    _ensure_required_values(
        submission,
        (
            'activity_name',
            'activity_type',
            'activity_description',
            'activity_date',
            'activity_time_start',
            'activity_time_end',
            'activity_location',
            'contact_person',
        ),
    )
    PublishedActivity.objects.update_or_create(
        source_submission=submission,
        defaults={
            'club': submission.club,
            'activity_name': submission.field_value('activity_name'),
            'activity_type': submission.field_value('activity_type', '其他'),
            'activity_description': submission.field_value('activity_description', ''),
            'activity_date': _date_value(submission.field_value('activity_date')),
            'activity_time_start': _time_value(submission.field_value('activity_time_start')),
            'activity_time_end': _time_value(submission.field_value('activity_time_end')),
            'activity_location': submission.field_value('activity_location', ''),
            'expected_participants': _int_value(submission.field_value('expected_participants')),
            'budget': _decimal_value(submission.field_value('budget')),
            'contact_person': submission.field_value('contact_person', ''),
            'contact_phone': submission.field_value('contact_phone', ''),
            'is_public': _bool_value(submission.field_value('is_public', '')),
        },
    )


def apply_business_action(submission):
    action = get_business_action(submission.channel.builtin_action)
    if not action:
        return
    missing = missing_required_field_keys(submission.channel)
    if missing:
        raise BusinessActionError(f'业务动作缺少字段配置：{", ".join(missing)}')
    if action.on_approved:
        action.on_approved(submission)


def create_form_cycle(channel, name='', user=None, starts_at=None):
    from .models import FormCycle

    FormCycle.objects.filter(channel=channel, is_active=True).update(is_active=False, ends_at=timezone.now())
    next_sequence = (FormCycle.objects.filter(channel=channel).aggregate(Max('sequence'))['sequence__max'] or 0) + 1
    return FormCycle.objects.create(
        channel=channel,
        name=name or f'第{next_sequence}期',
        sequence=next_sequence,
        is_active=True,
        starts_at=starts_at or timezone.now(),
        created_by=user,
    )


def seed_business_form_channels(user=None):
    from .models import FormChannel, FormField

    for action in BUSINESS_FORM_ACTIONS.values():
        channel, _ = FormChannel.objects.update_or_create(
            slug=action.default_slug,
            defaults={
                'name': action.label,
                'icon': action.default_icon,
                'description': action.default_description,
                'order': action.default_order,
                'is_active': True,
                'is_builtin': True,
                'builtin_action': action.key,
                'submission_policy': action.default_policy,
                'show_unsubmitted_status': action.show_unsubmitted_status,
                'allow_staff_toggle': action.allow_staff_toggle,
                'cycle_type': action.default_cycle_type,
            },
        )
        for field_spec in action.fields:
            FormField.objects.update_or_create(
                channel=channel,
                field_key=field_spec.key,
                defaults={
                    'label': field_spec.label,
                    'field_type': field_spec.field_type,
                    'required': field_spec.required,
                    'order': field_spec.order,
                    'options': field_spec.options,
                    'validation': field_spec.validation,
                    'placeholder': field_spec.placeholder,
                    'help_text': field_spec.help_text,
                    'is_active': True,
                },
            )
        if action.default_policy == 'once_per_cycle' and not channel.cycles.filter(is_active=True).exists():
            create_form_cycle(channel, user=user)


register_business_form_action(BusinessFormAction(
    key='annual_review',
    label='社团年审',
    default_slug='annual-review',
    default_icon='assignment',
    default_order=10,
    default_policy='once_per_cycle',
    default_description='社团年审默认动态提交通道',
    show_unsubmitted_status=True,
    allow_staff_toggle=True,
    default_cycle_type='year',
    required_fields=('submission_year',),
    fields=[
        BusinessField('submission_year', '提交年度', 'number', True, 10, validation={'min': 2000, 'max': 2100}),
        BusinessField('self_assessment_form', '自查表', 'file', True, 20, validation={'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        BusinessField('club_constitution', '社团章程', 'file', True, 30, validation={'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        BusinessField('annual_activity_list', '社团年度活动清单', 'file', True, 40, validation={'allowed_extensions': ['.doc', '.docx', '.pdf', '.xls', '.xlsx'], 'max_size_mb': 10}),
        BusinessField('financial_report', '年度财务情况表', 'file', True, 50, validation={'allowed_extensions': ['.doc', '.docx', '.pdf', '.xls', '.xlsx'], 'max_size_mb': 10}),
        BusinessField('other_materials', '其他材料', 'file', False, 60, validation={'allowed_extensions': ['.doc', '.docx', '.pdf', '.jpg', '.png', '.zip'], 'max_size_mb': 20}),
    ],
))

register_business_form_action(BusinessFormAction(
    key='club_registration',
    label='社团注册',
    default_slug='registration',
    default_icon='add_circle',
    default_order=20,
    default_policy='once_per_cycle',
    default_description='社团注册默认动态提交通道',
    show_unsubmitted_status=True,
    allow_staff_toggle=True,
    default_cycle_type='count',
    required_fields=('registration_form',),
    fields=[
        BusinessField('registration_form', '社团注册申请表', 'file', True, 10, validation={'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        BusinessField('basic_info_form', '学生社团基础信息表', 'file', True, 20, validation={'allowed_extensions': ['.doc', '.docx', '.pdf', '.xls', '.xlsx'], 'max_size_mb': 10}),
        BusinessField('fee_form', '会费表或免收会费说明书', 'file', False, 30, validation={'allowed_extensions': ['.doc', '.docx', '.pdf', '.xls', '.xlsx'], 'max_size_mb': 10}),
        BusinessField('meeting_minutes', '社团大会会议记录', 'file', False, 40, validation={'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        BusinessField('other_materials', '其他注册材料', 'file', False, 50, validation={'allowed_extensions': ['.doc', '.docx', '.pdf', '.zip'], 'max_size_mb': 20}),
    ],
))

register_business_form_action(BusinessFormAction(
    key='club_application',
    label='社团申请',
    default_slug='application',
    default_icon='create',
    default_order=30,
    default_policy='repeatable',
    default_description='社团成立申请默认动态提交通道',
    required_fields=('club_name', 'club_description'),
    on_approved=approve_club_application,
    fields=[
        BusinessField('club_name', '拟成立社团名称', 'text', True, 10, validation={'max_length': 100}),
        BusinessField('club_description', '社团简介', 'textarea', True, 20),
        BusinessField('president_name', '负责人姓名', 'text', True, 30, validation={'max_length': 100}),
        BusinessField('president_student_id', '负责人学号', 'text', True, 40, validation={'max_length': 50}),
        BusinessField('contact_phone', '联系电话', 'text', True, 50, validation={'max_length': 30}),
        BusinessField('establishment_application', '社团成立申请书', 'file', True, 60, validation={'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        BusinessField('constitution_draft', '社团章程草案', 'file', True, 70, validation={'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
        BusinessField('three_year_plan', '三年发展规划', 'file', True, 80, validation={'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
    ],
))

register_business_form_action(BusinessFormAction(
    key='reimbursement',
    label='报销申请',
    default_slug='reimbursement',
    default_icon='receipt',
    default_order=40,
    default_policy='repeatable',
    default_description='报销申请默认动态提交通道',
    required_fields=('reimbursement_amount', 'description'),
    fields=[
        BusinessField('submission_date', '申请日期', 'date', True, 10),
        BusinessField('reimbursement_amount', '报销金额', 'number', True, 20, validation={'min': 0, 'step': '0.01'}),
        BusinessField('description', '报销说明', 'textarea', True, 30),
        BusinessField('receipt_file', '报销凭证', 'file', True, 40, validation={'allowed_extensions': ['.pdf', '.jpg', '.jpeg', '.png', '.zip'], 'max_size_mb': 20}),
    ],
))

register_business_form_action(BusinessFormAction(
    key='activity_application',
    label='活动申请',
    default_slug='activity-application',
    default_icon='event',
    default_order=50,
    default_policy='repeatable',
    default_description='活动申请默认动态提交通道，审核通过后进入活动展示与报名页面',
    required_fields=('activity_name', 'activity_type', 'activity_description', 'activity_date', 'activity_time_start', 'activity_time_end', 'activity_location', 'contact_person'),
    on_approved=approve_activity_application,
    fields=[
        BusinessField('activity_name', '活动名称', 'text', True, 10, validation={'max_length': 200}),
        BusinessField('activity_type', '活动类型', 'select', True, 20, options=['讲座', '比赛', '演出', '培训', '志愿服务', '其他']),
        BusinessField('activity_description', '活动描述', 'textarea', True, 30),
        BusinessField('activity_date', '活动日期', 'date', True, 40),
        BusinessField('activity_time_start', '开始时间', 'time', True, 50),
        BusinessField('activity_time_end', '结束时间', 'time', True, 60),
        BusinessField('activity_location', '活动地点', 'text', True, 70, validation={'max_length': 200}),
        BusinessField('expected_participants', '预计参与人数', 'number', False, 80, validation={'min': 0, 'step': 1}),
        BusinessField('budget', '活动预算', 'number', False, 90, validation={'min': 0, 'step': '0.01'}),
        BusinessField('contact_person', '联系人', 'text', True, 100, validation={'max_length': 100}),
        BusinessField('contact_phone', '联系电话', 'text', False, 110, validation={'max_length': 30}),
        BusinessField('is_public', '是否公开报名', 'select', False, 120, options=['公开', '仅社团成员']),
        BusinessField('application_form', '活动申请材料', 'file', False, 130, validation={'allowed_extensions': ['.doc', '.docx', '.pdf'], 'max_size_mb': 10}),
    ],
))

register_business_form_action(BusinessFormAction(
    key='president_transition',
    label='社长换届',
    default_slug='president-transition',
    default_icon='swap_horiz',
    default_order=60,
    default_policy='repeatable',
    default_description='社长换届默认动态提交通道',
    required_fields=('new_president_student_id',),
    on_approved=approve_president_transition,
    fields=[
        BusinessField('new_president_name', '新社长姓名', 'text', True, 10, validation={'max_length': 100}),
        BusinessField('new_president_student_id', '新社长学号', 'text', True, 20, validation={'max_length': 50}),
        BusinessField('new_president_phone', '新社长电话', 'text', False, 30, validation={'max_length': 30}),
        BusinessField('transition_date', '换届日期', 'date', True, 40),
        BusinessField('reason', '换届说明', 'textarea', True, 50),
        BusinessField('transition_file', '换届材料', 'file', False, 60, validation={'allowed_extensions': ['.doc', '.docx', '.pdf', '.zip'], 'max_size_mb': 20}),
    ],
))
