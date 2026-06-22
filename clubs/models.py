from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import random
import string
from datetime import timedelta


class UserProfile(models.Model):
    """用户角色扩展模型"""
    ROLE_CHOICES = [
        ('president', '社长'),
        ('member', '社员'),
        ('staff', '干事'),
        ('admin', '管理员'),
    ]
    
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
        ('inactive', '不活跃'),
    ]

    ACCOUNT_STATUS_CHOICES = [
        ('active', '活跃'),
        ('inactive', '不活跃'),
    ]

    GENDER_CHOICES = [
        ('male', '男'),
        ('female', '女'),
        ('other', '其他'),
    ]
    
    STAFF_LEVEL_CHOICES = [
        ('member', '部员'),
        ('director', '部长'),
    ]
    
    POLITICAL_STATUS_CHOICES = [
        ('communist_party_member', '中共党员'),
        ('communist_party_probationary', '中共预备党员'),
        ('communist_youth_league', '共青团员'),
        ('revolutionary_committee', '民革党员'),
        ('china_democratic_league', '民盟盟员'),
        ('democratic_national_construction', '民建会员'),
        ('china_peasants_workers_democratic', '农工党党员'),
        ('china_council_for_promoting', '致公党党员'),
        ('jiusanshe', '九三学社社员'),
        ('taiwan_democratic_self_government', '台盟盟员'),
        ('non_party_personage', '无党派人士'),
        ('progressive', '入党积极分子'),
        ('non_member', '群众'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name='用户')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='president', verbose_name='角色')
    
    # 审核状态 - 只有干事需要审核
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='approved', verbose_name='状态')
    
    # 干事专属字段 - 部门和职级
    department = models.CharField(max_length=20, null=True, blank=True, verbose_name='部门')
    department_link = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='关联部门', related_name='staff_profiles')
    staff_level = models.CharField(max_length=20, choices=STAFF_LEVEL_CHOICES, default='member', verbose_name='部员/部长', help_text='仅对干事有效')
    
    # 实名信息字段
    real_name = models.CharField(max_length=100, verbose_name='真名', blank=True)
    student_id = models.CharField(max_length=50, verbose_name='学号', blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, verbose_name='性别')
    college = models.CharField(max_length=100, blank=True, verbose_name='学院')
    class_name = models.CharField(max_length=100, blank=True, verbose_name='班级')
    phone = models.CharField(max_length=20, verbose_name='电话', blank=True)
    qq = models.CharField(max_length=30, verbose_name='QQ', blank=True)
    wechat = models.CharField(max_length=100, verbose_name='微信', blank=True)
    political_status = models.CharField(
        max_length=40, 
        choices=POLITICAL_STATUS_CHOICES, 
        default='non_member', 
        verbose_name='政治面貌'
    )
    
    # 信息披露设置
    is_info_public = models.BooleanField(default=False, verbose_name='是否公开个人信息')

    # 首次登录强制改密
    must_change_password = models.BooleanField(default=False, verbose_name='是否需要修改密码')

    # 账号生命周期状态（与审核状态分离）
    account_status = models.CharField(
        max_length=20,
        choices=ACCOUNT_STATUS_CHOICES,
        default='active',
        verbose_name='账号活跃状态'
    )
    inactive_since = models.DateTimeField(null=True, blank=True, verbose_name='不活跃起始时间')
    active_until = models.DateTimeField(null=True, blank=True, verbose_name='活跃有效期至')
    
    # 头像
    avatar = models.ImageField(upload_to='avatars/%Y/%m/', null=True, blank=True, verbose_name='头像')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    def get_full_name(self):
        """
        获取用户的全名，优先使用real_name，其次是last_name+first_name，最后是用户名
        """
        if self.real_name:
            return self.real_name
        elif self.user.first_name or self.user.last_name:
            return f"{self.user.last_name}{self.user.first_name}"
        else:
            return self.user.username
    
    def __str__(self):
        return f"{self.user.username} ({self.get_full_name()}) - {self.get_role_display()}"
    
    class Meta:
        verbose_name = '用户角色'
        verbose_name_plural = '用户角色'
        indexes = [
            models.Index(fields=['role', 'status'], name='up_role_status_idx'),
            models.Index(fields=['role', 'staff_level'], name='up_role_staff_lvl_idx'),
            models.Index(fields=['account_status', 'inactive_since'], name='up_acc_inactive_idx'),
        ]


class ClubMember(models.Model):
    """社团成员关系（支持一个账户加入多个社团）。"""

    STATUS_CHOICES = [
        ('active', '活跃'),
        ('inactive', '不活跃'),
    ]

    club = models.ForeignKey('Club', on_delete=models.CASCADE, related_name='memberships', verbose_name='社团')
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='club_memberships', verbose_name='成员')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='成员状态')
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name='加入时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '社团成员'
        verbose_name_plural = '社团成员'
        unique_together = [('club', 'user_profile')]
        indexes = [
            models.Index(fields=['club', 'status'], name='cm_club_status_idx'),
            models.Index(fields=['user_profile', 'status'], name='cm_user_status_idx'),
        ]

    def __str__(self):
        return f"{self.club.name} - {self.user_profile.get_full_name()}"


class RegistrationToken(models.Model):
    """社员扫码注册令牌，支持可配置有效期和使用次数。"""

    code = models.CharField(max_length=64, unique=True, verbose_name='一次性校验码')
    club = models.ForeignKey('Club', on_delete=models.CASCADE, related_name='registration_tokens', verbose_name='社团')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_registration_tokens', verbose_name='创建人')
    expires_at = models.DateTimeField(verbose_name='过期时间')
    max_uses = models.IntegerField(null=True, blank=True, verbose_name='最大使用次数（null表示不限次数）')
    used_count = models.IntegerField(default=0, verbose_name='已使用次数')
    is_used = models.BooleanField(default=False, verbose_name='是否已使用')
    used_at = models.DateTimeField(null=True, blank=True, verbose_name='使用时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '社员注册令牌'
        verbose_name_plural = '社员注册令牌'
        indexes = [
            models.Index(fields=['club', 'expires_at', 'is_used'], name='rt_club_exp_used_idx'),
        ]

    def __str__(self):
        return f"{self.club.name} - {self.code[:8]}..."

    @staticmethod
    def generate_code(length=32):
        alphabet = string.ascii_letters + string.digits
        return ''.join(random.choices(alphabet, k=length))

    @classmethod
    def create_for_club(cls, club, created_by, minutes=10, max_uses=1):
        """
        创建社团招新令牌。
        
        :param club: 社团对象
        :param created_by: 创建人（User对象）
        :param minutes: 有效时长（分钟），不限次数时最多1440分钟（1天）
        :param max_uses: 最大使用次数，None表示不限次数
        """
        # 业务规则：不限次数时，有效期最多1天
        if max_uses is None and minutes > 1440:
            raise ValueError('不限次数的令牌有效期不得超过1天（1440分钟）')

        for _ in range(5):
            code = cls.generate_code()
            if not cls.objects.filter(code=code).exists():
                return cls.objects.create(
                    code=code,
                    club=club,
                    created_by=created_by,
                    expires_at=timezone.now() + timedelta(minutes=minutes),
                    max_uses=max_uses,
                )
        # 极低概率碰撞时，退化为带时间戳的随机串
        return cls.objects.create(
            code=f"{timezone.now().strftime('%Y%m%d%H%M%S')}{cls.generate_code(12)}",
            club=club,
            created_by=created_by,
            expires_at=timezone.now() + timedelta(minutes=minutes),
            max_uses=max_uses,
        )

    def is_expired(self):
        return timezone.now() > self.expires_at

    def can_use(self):
        """检查令牌是否可用：未过期且未达到使用次数上限。"""
        if self.is_expired():
            return False
        if self.max_uses is None:
            # 不限次数
            return True
        return self.used_count < self.max_uses

    def mark_used(self):
        """标记令牌已使用，增加使用计数。"""
        self.used_count += 1
        if self.max_uses is not None and self.used_count >= self.max_uses:
            self.is_used = True
            self.used_at = timezone.now()
        self.save()


class InactiveExtensionHistory(models.Model):
    """不活跃账号延期记录。"""

    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='inactive_extensions', verbose_name='用户')
    extended_at = models.DateTimeField(auto_now_add=True, verbose_name='延期时间')
    previous_active_until = models.DateTimeField(null=True, blank=True, verbose_name='延期前有效期')
    new_active_until = models.DateTimeField(verbose_name='延期后有效期')
    reason = models.CharField(max_length=100, blank=True, verbose_name='延期原因')

    class Meta:
        verbose_name = '不活跃延期记录'
        verbose_name_plural = '不活跃延期记录'
        ordering = ['-extended_at']

    def __str__(self):
        return f"{self.user_profile.user.username} 延期至 {self.new_active_until.strftime('%Y-%m-%d')}"


class Club(models.Model):
    """社团模型"""
    STATUS_CHOICES = [
        ('active', '活跃'),
        ('inactive', '不活跃'),
        ('suspended', '停止'),
    ]
    
    name = models.CharField(max_length=100, unique=True, verbose_name='社团名称')
    description = models.TextField(blank=True, verbose_name='社团介绍')
    founded_date = models.DateField(verbose_name='成立日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='状态')
    members_count = models.IntegerField(default=0, verbose_name='成员数')
    review_enabled = models.BooleanField(default=False, verbose_name='是否开启年审')
    registration_enabled = models.BooleanField(default=False, verbose_name='是否开启注册')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '社团'
        verbose_name_plural = '社团'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name

    @property
    def president(self):
        """返回当前社长 User 对象（从 Officer 表查询）。
        若已通过 prefetch_related(..., to_attr='_president_list') 预取，则直接使用缓存。
        """
        if hasattr(self, '_president_list'):
            officer = self._president_list[0] if self._president_list else None
            return officer.user_profile.user if officer and officer.user_profile else None
        officer = self.officers.filter(
            position='president', is_current=True
        ).select_related('user_profile__user').first()
        return officer.user_profile.user if officer and officer.user_profile else None

    @property
    def president_id(self):
        """返回当前社长 User 的 id（从 Officer 表查询）。"""
        user = self.president
        return user.id if user else None


class Officer(models.Model):
    """社团干部模型"""
    POSITION_CHOICES = [
        ('president', '社长'),
    ]
    
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='officers', verbose_name='社团')
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, null=True, blank=True, verbose_name='用户信息')
    position = models.CharField(max_length=20, choices=POSITION_CHOICES, verbose_name='职位')
    appointed_date = models.DateField(verbose_name='任命日期')
    end_date = models.DateField(null=True, blank=True, verbose_name='结束日期')
    is_current = models.BooleanField(default=True, verbose_name='是否现任')
    
    class Meta:
        verbose_name = '社团干部'
        verbose_name_plural = '社团干部'
        unique_together = ['club', 'user_profile', 'position']
        ordering = ['-appointed_date']
        indexes = [
            models.Index(fields=['user_profile', 'position', 'is_current'], name='officer_user_pos_cur_idx'),
            models.Index(fields=['club', 'position', 'is_current'], name='officer_club_pos_cur_idx'),
        ]
    
    def __str__(self):
        real_name = self.user_profile.real_name if self.user_profile else "未知"
        return f"{self.club.name} - {real_name} ({self.get_position_display()})"


class FormChannel(models.Model):
    """动态表单提交通道。"""

    BUILTIN_ACTION_CHOICES = [
        ('none', '无'),
        ('annual_review', '社团年审'),
        ('club_registration', '社团注册'),
        ('club_application', '社团申请'),
        ('reimbursement', '报销申请'),
        ('activity_application', '活动申请'),
        ('president_transition', '社长换届'),
    ]

    name = models.CharField(max_length=100, verbose_name='通道名称')
    slug = models.SlugField(max_length=80, unique=True, verbose_name='通道标识')
    icon = models.CharField(max_length=50, default='description', verbose_name='图标')
    description = models.TextField(blank=True, verbose_name='说明')
    order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='启用')
    is_builtin = models.BooleanField(default=False, verbose_name='内置通道')
    builtin_action = models.CharField(max_length=50, choices=BUILTIN_ACTION_CHOICES, default='none', verbose_name='内置动作')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '提交通道'
        verbose_name_plural = '提交通道'
        ordering = ['order', 'id']

    def __str__(self):
        return self.name


class FormField(models.Model):
    """动态表单字段配置。"""

    FIELD_TYPE_CHOICES = [
        ('text', '单行文本'),
        ('textarea', '多行文本'),
        ('number', '数字'),
        ('date', '日期'),
        ('time', '时间'),
        ('select', '下拉选择'),
        ('radio', '单选'),
        ('checkbox', '多选'),
        ('file', '文件'),
    ]

    channel = models.ForeignKey(FormChannel, on_delete=models.CASCADE, related_name='fields', verbose_name='所属通道')
    label = models.CharField(max_length=120, verbose_name='字段名称')
    field_key = models.SlugField(max_length=80, verbose_name='字段标识')
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, verbose_name='字段类型')
    required = models.BooleanField(default=True, verbose_name='必填')
    order = models.IntegerField(default=0, verbose_name='排序')
    help_text = models.TextField(blank=True, verbose_name='提示')
    placeholder = models.CharField(max_length=200, blank=True, verbose_name='占位提示')
    options = models.JSONField(default=list, blank=True, verbose_name='选项')
    validation = models.JSONField(default=dict, blank=True, verbose_name='校验规则')
    example_file = models.FileField(upload_to='form_examples/%Y/%m/', blank=True, null=True, verbose_name='示例文件')
    is_active = models.BooleanField(default=True, verbose_name='启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '表单字段'
        verbose_name_plural = '表单字段'
        ordering = ['channel', 'order', 'id']
        unique_together = [('channel', 'field_key')]

    def __str__(self):
        return f'{self.channel.name} - {self.label}'

    def option_lines(self):
        if isinstance(self.options, list):
            return '\n'.join(str(item) for item in self.options)
        return ''

    def allowed_extensions(self):
        values = self.validation.get('allowed_extensions', ['.doc', '.docx', '.pdf', '.jpg', '.jpeg', '.png', '.zip'])
        if isinstance(values, str):
            values = [item.strip() for item in values.split(',') if item.strip()]
        return [item if str(item).startswith('.') else f'.{item}' for item in values]

    def max_size_mb(self):
        try:
            return int(self.validation.get('max_size_mb', 10))
        except (TypeError, ValueError):
            return 10


class FormSubmission(models.Model):
    """动态表单提交记录。"""

    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
    ]

    channel = models.ForeignKey(FormChannel, on_delete=models.CASCADE, related_name='submissions', verbose_name='通道')
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='form_submissions', verbose_name='社团')
    submitter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='form_submissions', verbose_name='提交人')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_form_submissions', verbose_name='审核人')
    review_comment = models.TextField(blank=True, verbose_name='审核意见')
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    resubmission_count = models.IntegerField(default=1, verbose_name='提交次数')
    is_read = models.BooleanField(default=False, verbose_name='已读')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='扩展信息')

    class Meta:
        verbose_name = '动态表单提交'
        verbose_name_plural = '动态表单提交'
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['channel', 'status', '-submitted_at'], name='fs_channel_status_idx'),
            models.Index(fields=['club', 'status', '-submitted_at'], name='fs_club_status_idx'),
        ]

    def __str__(self):
        return f'{self.channel.name} - {self.club.name} - {self.get_status_display()}'

    def field_value(self, key, default=''):
        value = self.values.filter(field__field_key=key).first()
        if not value:
            return default
        if value.value_json not in (None, {}, []):
            return value.value_json
        return value.value_text or default

    @property
    def display_title(self):
        for key in ['activity_name', 'club_name', 'title', 'name']:
            value = self.field_value(key)
            if value:
                return value
        return self.club.name

    @property
    def activity_date(self):
        return self.field_value('activity_date')

    @property
    def activity_time_start(self):
        return self.field_value('activity_time_start')

    @property
    def activity_time_end(self):
        return self.field_value('activity_time_end')

    @property
    def is_public_activity(self):
        value = self.field_value('is_public')
        if isinstance(value, str):
            return value in ['是', 'true', 'True', '1', 'yes']
        return bool(value)


class FormFieldValue(models.Model):
    """动态表单非文件字段值。"""

    submission = models.ForeignKey(FormSubmission, on_delete=models.CASCADE, related_name='values', verbose_name='提交')
    field = models.ForeignKey(FormField, on_delete=models.CASCADE, related_name='values', verbose_name='字段')
    value_text = models.TextField(blank=True, verbose_name='文本值')
    value_json = models.JSONField(default=dict, blank=True, verbose_name='结构化值')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '表单字段值'
        verbose_name_plural = '表单字段值'
        unique_together = [('submission', 'field')]

    def __str__(self):
        return f'{self.submission_id} - {self.field.label}'


class FormUploadedFile(models.Model):
    """动态表单文件上传结果。"""

    submission = models.ForeignKey(FormSubmission, on_delete=models.CASCADE, related_name='uploaded_files', verbose_name='提交')
    field = models.ForeignKey(FormField, on_delete=models.CASCADE, related_name='uploaded_files', verbose_name='字段')
    file = models.FileField(upload_to='form_submissions/%Y/%m/', verbose_name='文件')
    original_name = models.CharField(max_length=255, blank=True, verbose_name='原始文件名')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')

    class Meta:
        verbose_name = '表单上传文件'
        verbose_name_plural = '表单上传文件'
        ordering = ['uploaded_at']

    def __str__(self):
        return self.original_name or self.file.name


class Template(models.Model):
    """材料模板模型 - 干事可以上传各类模板"""
    TEMPLATE_TYPES = [
        # 年审模板 - 根据实际上传材料细分
        ('review_financial', '年审 - 财务报告'),
        ('review_activity', '年审 - 活动报告'),
        ('review_member_list', '年审 - 成员名单'),
        ('review_self_assessment', '年审 - 自查表'),
        ('review_club_constitution', '年审 - 社团章程'),
        ('review_leader_report', '年审 - 负责人学习及工作情况表'),
        ('review_annual_activity', '年审 - 社团年度活动清单'),
        ('review_advisor_report', '年审 - 指导教师履职情况表'),
        ('review_member_composition', '年审 - 社团成员构成表'),
        ('review_media_account', '年审 - 新媒体账号及运维情况表'),
        # 报销模板
        ('reimbursement', '报销模板'),
        # 社团申请模板
        ('application_establishment', '社团申请 - 社团成立申请书'),
        ('application_constitution', '社团申请 - 社团章程草案'),
        ('application_three_year_plan', '社团申请 - 社团三年发展规划'),
        ('application_leader_resume', '社团申请 - 负责人简历'),
        ('application_advisor_resume', '社团申请 - 指导老师简历'),
        ('application_id_copies', '社团申请 - 身份证复印件'),
        ('application_monthly_plan', '社团申请 - 一个月活动计划'),
        ('application_teacher_certificates', '社团申请 - 指导老师专业证书'),
        # 社团注册模板
        ('registration_form', '社团注册 - 社团注册申请表'),
        ('registration_basic_info', '社团注册 - 学生社团基础信息表'),
        ('registration_fee_form', '社团注册 - 会费表'),
        ('registration_fee_exemption', '社团注册 - 免收会费说明书'),
        ('registration_leader_change', '社团注册 - 负责人变动申请'),
        ('registration_meeting_minutes', '社团注册 - 社团大会会议记录'),
        ('registration_name_change', '社团注册 - 社团名称变更申请表'),
        ('registration_advisor_change', '社团注册 - 指导老师变动申请表'),
        ('registration_business_unit_change', '社团注册 - 业务指导单位变动申请表'),
        ('registration_social_media', '社团注册 - 新媒体平台建立申请表'),
        # 社团创建
        ('club_creation', '社团创建文件'),
        # 社长变更模板
        ('leader_change', '社长变更申请'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='模板名称')
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPES, verbose_name='模板类型')
    description = models.TextField(blank=True, verbose_name='模板描述')
    file = models.FileField(upload_to='templates/%Y/%m/', verbose_name='模板文件')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='上传者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        verbose_name = '模板'
        verbose_name_plural = '模板'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class Announcement(models.Model):
    """公告模型 - 管理员发布，所有人可见"""
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('published', '已发布'),
        ('archived', '已归档'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='公告标题')
    content = models.TextField(verbose_name='公告内容')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='状态')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='发布者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='过期时间')
    attachment = models.FileField(upload_to='announcements/%Y/%m/', blank=True, null=True, verbose_name='附件')
    
    class Meta:
        verbose_name = '公告'
        verbose_name_plural = '公告'
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', '-published_at'], name='ann_status_pub_idx'),
        ]
    
    def __str__(self):
        return self.title





class StaffClubRelation(models.Model):
    """干事与社团的关联模型"""
    staff = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='managed_clubs', verbose_name='干事')
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='responsible_staff', verbose_name='社团')
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name='分配时间')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    
    class Meta:
        verbose_name = '干事负责社团'
        verbose_name_plural = '干事负责社团'
        unique_together = ['staff', 'club']
        indexes = [
            models.Index(fields=['staff', 'is_active'], name='scr_staff_active_idx'),
            models.Index(fields=['club', 'is_active'], name='scr_club_active_idx'),
        ]
    
    def __str__(self):
        return f"{self.staff.real_name} - {self.club.name}"


class RegistrationPeriod(models.Model):
    """社团注册周期模型 - 用于跟踪每次开启社团注册功能的周期"""
    period_number = models.AutoField(primary_key=True, verbose_name='周期编号')
    is_active = models.BooleanField(default=True, verbose_name='是否活跃')
    start_date = models.DateTimeField(auto_now_add=True, verbose_name='开始时间')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='创建人')
    
    class Meta:
        verbose_name = '社团注册周期'
        verbose_name_plural = '社团注册周期'
        ordering = ['-period_number']
    
    def __str__(self):
        return f"第{self.period_number}次社团注册周期 ({'活跃' if self.is_active else '已结束'})"


class ActivityRegistration(models.Model):
    """活动报名记录。活动本身来自通过审核的动态活动申请提交。"""
    activity = models.ForeignKey('FormSubmission', on_delete=models.CASCADE, related_name='registrations', verbose_name='活动')
    user_profile = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='activity_registrations', verbose_name='报名用户')
    registered_at = models.DateTimeField(auto_now_add=True, verbose_name='报名时间')

    class Meta:
        verbose_name = '活动报名'
        verbose_name_plural = '活动报名'
        unique_together = [('activity', 'user_profile')]

    def __str__(self):
        return f"{self.user_profile} 报名 {self.activity.display_title}"


class EmailVerificationCode(models.Model):
    """邮箱验证码模型"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_verification', verbose_name='用户')
    email = models.EmailField(verbose_name='待验证邮箱')
    code = models.CharField(max_length=6, verbose_name='验证码')
    is_verified = models.BooleanField(default=False, verbose_name='是否已验证')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    expires_at = models.DateTimeField(verbose_name='过期时间')
    
    class Meta:
        verbose_name = '邮箱验证码'
        verbose_name_plural = '邮箱验证码'
    
    def __str__(self):
        return f"{self.user.username} - {self.email}"
    
    @staticmethod
    def generate_code():
        """生成6位随机验证码"""
        return ''.join(random.choices(string.digits, k=6))
    
    def is_expired(self):
        """检查验证码是否过期"""
        return timezone.now() > self.expires_at
    
    def verify(self, code):
        """验证码验证"""
        if self.is_verified:
            return False, "验证码已使用"
        if self.is_expired():
            return False, "验证码已过期"
        if code != self.code:
            return False, "验证码不正确"
        return True, "验证成功"


class SMTPConfig(models.Model):
    """SMTP邮箱配置"""
    PROVIDER_CHOICES = [
        ('qq', 'QQ邮箱'),
        ('163', '163邮箱'),
        ('outlook', 'Outlook'),
        ('gmail', 'Gmail'),
        ('custom', '自定义'),
    ]
    
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, verbose_name='邮箱服务商')
    smtp_host = models.CharField(max_length=100, verbose_name='SMTP服务器地址')
    smtp_port = models.IntegerField(verbose_name='SMTP端口')
    sender_email = models.EmailField(verbose_name='发送邮箱地址')
    sender_password = models.CharField(max_length=255, verbose_name='邮箱密码/授权码', help_text='某些邮箱需要使用授权码而非密码')
    use_tls = models.BooleanField(default=True, verbose_name='是否使用TLS加密')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'SMTP配置'
        verbose_name_plural = 'SMTP配置'
    
    def __str__(self):
        return f"{self.get_provider_display()} - {self.sender_email}"
    
    @classmethod
    def get_active_config(cls):
        """获取激活的SMTP配置"""
        return cls.objects.filter(is_active=True).first()


class CarouselImage(models.Model):
    """首页轮播图片模型"""
    image = models.ImageField(upload_to='carousel/', verbose_name='轮播图片')
    title = models.CharField(max_length=200, blank=True, verbose_name='标题')
    description = models.TextField(blank=True, verbose_name='描述')
    link = models.URLField(blank=True, verbose_name='跳转链接', help_text='点击轮播图跳转的地址')
    order = models.IntegerField(default=0, verbose_name='排序', help_text='数字越小越靠前')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='上传者')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    
    class Meta:
        verbose_name = '轮播图片'
        verbose_name_plural = '轮播图片'
        ordering = ['order', '-uploaded_at']
        indexes = [
            models.Index(fields=['is_active', 'order', '-uploaded_at'], name='carousel_active_ord_idx'),
        ]
    
    def __str__(self):
        return self.title or f"轮播图片 {self.id}"


class Department(models.Model):
    """部门模型"""
    name = models.CharField(max_length=50, unique=True, verbose_name='部门名称')
    description = models.TextField(verbose_name='职责描述')
    highlights = models.TextField(blank=True, help_text='多个重点工作用换行分隔', verbose_name='重点工作')
    icon = models.CharField(max_length=50, default='work', help_text='Material Icons图标名称', verbose_name='图标名称')
    order = models.IntegerField(default=0, verbose_name='排序')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name='更新者'
    )
    
    class Meta:
        verbose_name = '部门'
        verbose_name_plural = '部门'
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name
    
    def get_highlights_list(self):
        """将highlights转换为列表"""
        if self.highlights:
            return [h.strip() for h in self.highlights.split('\n') if h.strip()]
        return []


class TimeSlot(models.Model):
    """时间段配置"""
    start_time = models.TimeField(verbose_name='开始时间')
    end_time = models.TimeField(verbose_name='结束时间')
    label = models.CharField(max_length=50, verbose_name='显示名称')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        verbose_name = '时间段'
        verbose_name_plural = '时间段'
        ordering = ['start_time']
        
    def __str__(self):
        return f"{self.label} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"


class Room(models.Model):
    STATUS_CHOICES = [
        ('available', '可用'),
        ('maintenance', '维护中'),
        ('closed', '关闭'),
    ]
    
    name = models.CharField(max_length=100, unique=True, verbose_name='房间名称')
    capacity = models.IntegerField(default=50, verbose_name='容纳人数')
    location = models.CharField(max_length=200, blank=True, verbose_name='位置')
    description = models.TextField(blank=True, verbose_name='描述')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', verbose_name='状态')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '房间'
        verbose_name_plural = '房间'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class RoomBooking(models.Model):
    """房间借用模型"""
    STATUS_CHOICES = [
        ('active', '有效'),
        ('cancelled', '已取消'),
    ]
    
    # 关联房间
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings', verbose_name='房间')
    
    # 借用人信息（可以是社团或个人）
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='room_bookings', verbose_name='借用人')
    club = models.ForeignKey(Club, on_delete=models.SET_NULL, null=True, blank=True, related_name='room_bookings', verbose_name='所属社团')
    
    # 借用时间
    booking_date = models.DateField(verbose_name='借用日期')
    start_time = models.TimeField(verbose_name='开始时间')
    end_time = models.TimeField(verbose_name='结束时间')
    
    # 借用信息
    purpose = models.TextField(verbose_name='借用目的')
    participant_count = models.IntegerField(verbose_name='预计使用人数')
    contact_phone = models.CharField(max_length=20, verbose_name='联系电话')
    
    # 特殊需求
    special_requirements = models.TextField(blank=True, verbose_name='特殊需求', help_text='如需要投影仪、音响等设备')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='状态')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '房间借用'
        verbose_name_plural = '房间借用'
        ordering = ['booking_date', 'start_time']
        # 防止同一房间同一时间段重复预订
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F('start_time')),
                name='room_end_time_after_start_time'
            )
        ]
        indexes = [
            models.Index(fields=['room', 'booking_date', 'status'], name='rb_room_date_idx'),
            models.Index(fields=['user', 'booking_date'], name='rb_user_date_idx'),
            models.Index(fields=['club', 'booking_date'], name='rb_club_date_idx'),
        ]
    
    def __str__(self) -> str:
        return f"{self.room.name} - {self.user.profile.get_full_name()} - {self.booking_date} {self.start_time}-{self.end_time}"  # type: ignore[attr-defined]
    
    def has_conflict(self):
        """检查是否与已有效的预订有时间冲突"""
        # 排除自己和已取消的，查找同一房间同一天内有效的预订
        conflicting_bookings = RoomBooking.objects.filter(
            room=self.room,
            booking_date=self.booking_date,
            status='active'
        ).exclude(pk=self.pk)
        
        for booking in conflicting_bookings:
            # 检查时间是否重叠
            if (self.start_time < booking.end_time and self.end_time > booking.start_time):
                return True
        return False

    def can_delete(self, user):
        """检查用户是否有权限删除此预约"""
        # 管理员和干事可以删除任何预约
        if hasattr(user, 'profile') and user.profile.role in ['admin', 'staff']:
            return True
        # 借用人本人可以删除
        if self.user == user:
            return True
        # 社团社长可以删除本社团的预约
        if self.club and self.club.president == user:
            return True
        return False

    def can_edit(self, user):
        """检查用户是否有权限编辑此预约"""
        # 管理员和干事可以编辑任何预约
        if hasattr(user, 'profile') and user.profile.role in ['admin', 'staff']:
            return True
        # 借用人本人可以编辑
        if self.user == user:
            return True
        # 社团社长可以编辑本社团的预约
        if self.club and self.club.president == user:
            return True
        return False


class SiteSettings(models.Model):
    """站点全局外观设置（单例，pk=1）"""
    font_icon_url = models.CharField(
        max_length=500,
        default='https://fonts.font.im/icon?family=Material+Icons',
        verbose_name='图标字体 CSS 地址',
        help_text='Material Icons CSS 的完整 URL，修改后刷新页面生效',
    )
    body_font_url = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name='正文 Web 字体 CSS 地址',
        help_text='Google Fonts / 镜像字体的 CSS URL（留空则不加载额外字体）',
    )
    body_font_family = models.CharField(
        max_length=300, blank=True, default='',
        verbose_name='正文字体族',
        help_text='CSS font-family 值，例如：\'Noto Sans SC\', sans-serif（留空则使用系统字体）',
    )

    class Meta:
        verbose_name = '站点设置'
        verbose_name_plural = '站点设置'

    def __str__(self):
        return '站点全局设置'

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class DailyStat(models.Model):
    """每日访问统计"""
    date = models.DateField(unique=True, verbose_name='日期')
    visits = models.PositiveIntegerField(default=0, verbose_name='访问次数')

    class Meta:
        verbose_name = '每日统计'
        verbose_name_plural = '每日统计'
        ordering = ['-date']

    def __str__(self):
        return f"{self.date} — {self.visits} 次访问"
