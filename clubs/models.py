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
        ('staff', '干事'),
        ('admin', '管理员'),
    ]
    
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
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
    phone = models.CharField(max_length=20, verbose_name='电话', blank=True)
    wechat = models.CharField(max_length=100, verbose_name='微信', blank=True)
    political_status = models.CharField(
        max_length=40, 
        choices=POLITICAL_STATUS_CHOICES, 
        default='non_member', 
        verbose_name='政治面貌'
    )
    
    # 信息披露设置
    is_info_public = models.BooleanField(default=False, verbose_name='是否公开个人信息')
    
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
    president = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='clubs_as_president', verbose_name='社长账户')
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
    
    def __str__(self):
        real_name = self.user_profile.real_name if self.user_profile else "未知"
        return f"{self.club.name} - {real_name} ({self.get_position_display()})"


class SubmissionReview(models.Model):
    """年审材料审核记录模型"""
    STATUS_CHOICES = [
        ('approved', '已批准'),
        ('rejected', '被拒绝'),
    ]
    
    # 定义可能的拒绝材料类型
    REJECTED_MATERIALS_CHOICES = [
        ('self_assessment_form', '自查表'),
        ('club_constitution', '社团章程'),
        ('leader_learning_work_report', '负责人学习及工作情况表'),
        ('annual_activity_list', '社团年度活动清单'),
        ('advisor_performance_report', '指导教师履职情况表'),
        ('financial_report', '年度财务情况表'),
        ('member_composition_list', '社团成员构成表'),
        ('new_media_account_report', '新媒体账号及运维情况表'),
        ('other_materials', '其他材料'),
    ]
    
    submission = models.ForeignKey('ReviewSubmission', on_delete=models.CASCADE, related_name='reviews', verbose_name='年审材料')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submission_reviews', verbose_name='审核人')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name='审核结果')
    comment = models.TextField(blank=True, verbose_name='审核意见')
    reviewed_at = models.DateTimeField(auto_now_add=True, verbose_name='审核时间')
    submission_attempt = models.IntegerField(default=1, verbose_name='提交次数')
    
    # 添加被拒绝的材料字段，使用JSONField存储被拒绝的材料列表
    rejected_materials = models.JSONField(default=list, blank=True, verbose_name='被拒绝的材料')
    
    class Meta:
        verbose_name = '审核记录'
        verbose_name_plural = '审核记录'
        ordering = ['-reviewed_at']
        unique_together = ['submission', 'reviewer', 'submission_attempt']  # 防止同一干事多次审核同一材料
    
    def __str__(self):
        return f"{self.reviewer.profile.real_name} 审核 {self.submission} - {self.get_status_display()}"


class ReviewSubmission(models.Model):
    """年审材料提交模型"""
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已批准'),
        ('rejected', '被拒绝'),
    ]
    
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='review_submissions', verbose_name='社团')
    submission_year = models.IntegerField(verbose_name='提交年份')
    # 按照要求的顺序重新定义材料字段（暂时允许null以确保迁移成功）
    self_assessment_form = models.FileField(upload_to='reviews/%Y/%m/', null=True, blank=True, verbose_name='自查表')
    club_constitution = models.FileField(upload_to='reviews/%Y/%m/', null=True, blank=True, verbose_name='社团章程')
    leader_learning_work_report = models.FileField(upload_to='reviews/%Y/%m/', null=True, blank=True, verbose_name='负责人学习及工作情况表')
    annual_activity_list = models.FileField(upload_to='reviews/%Y/%m/', null=True, blank=True, verbose_name='社团年度活动清单')
    advisor_performance_report = models.FileField(upload_to='reviews/%Y/%m/', null=True, blank=True, verbose_name='指导教师履职情况表')
    financial_report = models.FileField(upload_to='reviews/%Y/%m/', null=True, blank=True, verbose_name='年度财务情况表')
    member_composition_list = models.FileField(upload_to='reviews/%Y/%m/', null=True, blank=True, verbose_name='社团成员构成表')
    new_media_account_report = models.FileField(upload_to='reviews/%Y/%m/', null=True, blank=True, verbose_name='新媒体账号及运维情况表')
    other_materials = models.FileField(upload_to='reviews/%Y/%m/', verbose_name='其他材料', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='最后审核时间')
    
    # 添加新字段
    review_count = models.IntegerField(default=0, verbose_name='审核次数')
    is_read_by_president = models.BooleanField(default=False, verbose_name='社长是否已读')
    # 重新提交追踪 - 表示这是第几次提交（1为初始提交，2+ 为重新提交）
    resubmission_attempt = models.IntegerField(default=1, verbose_name='提交次数')
    
    class Meta:
        verbose_name = '年审材料'
        verbose_name_plural = '年审材料'
        ordering = ['-submitted_at']
        unique_together = ('club', 'submission_year')
    
    def __str__(self):
        return f"{self.club.name} - 注册申请"

    def get_final_reviewer(self):
        """获取最终审核通过的审核人"""
        if self.status == 'approved':
            last_approved_review = self.reviews.filter(status='approved').last()
            if last_approved_review:
                return last_approved_review.reviewer
        return None



class Reimbursement(models.Model):
    """报销材料提交模型"""
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已批准'),
        ('rejected', '被拒绝'),
    ]
    
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='reimbursements', verbose_name='社团')
    submission_date = models.DateField(verbose_name='报销日期')
    reimbursement_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='报销金额')
    description = models.TextField(verbose_name='报销说明')
    receipt_file = models.FileField(upload_to='reimbursements/%Y/%m/', verbose_name='报销凭证')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_reimbursements', verbose_name='审核人')
    reviewer_comment = models.TextField(blank=True, verbose_name='审核意见')
    # 社长是否已读审核结果
    is_read = models.BooleanField(default=False, verbose_name='社长是否已读')
    # 重新提交追踪 - 表示这是第几次提交（1为初始提交，2+ 为重新提交）
    resubmission_attempt = models.IntegerField(default=1, verbose_name='提交次数')
    
    class Meta:
        verbose_name = '报销材料'
        verbose_name_plural = '报销材料'
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"{self.club.name} - {self.submission_date} - ¥{self.reimbursement_amount}"

    def get_final_reviewer(self):
        """获取最终审核通过的审核人"""
        if self.status == 'approved':
            return self.reviewer
        return None


class ReimbursementHistory(models.Model):
    """报销审核历史"""
    reimbursement = models.ForeignKey(Reimbursement, on_delete=models.CASCADE, related_name='history', verbose_name='关联报销')
    attempt_number = models.IntegerField(verbose_name='提交次数')
    
    submission_date = models.DateField(verbose_name='报销日期')
    reimbursement_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='报销金额')
    description = models.TextField(verbose_name='报销说明')
    
    submitted_at = models.DateTimeField(verbose_name='提交时间')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reimbursement_history_reviews', verbose_name='审核人')
    status = models.CharField(max_length=20, choices=Reimbursement.STATUS_CHOICES, verbose_name='状态')
    reviewer_comment = models.TextField(blank=True, verbose_name='审核意见')
    
    class Meta:
        verbose_name = '报销审核历史'
        verbose_name_plural = '报销审核历史'
        ordering = ['-attempt_number']


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
    
    def __str__(self):
        return f"{self.staff.real_name} - {self.club.name}"


class ClubRegistrationRequest(models.Model):
    """社团注册申请模型（实际为社团申请功能）"""
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已批准'),
        ('rejected', '被拒绝'),
    ]
    
    club_name = models.CharField(max_length=100, verbose_name='社团名称')
    description = models.TextField(verbose_name='社团介绍')
    founded_date = models.DateField(verbose_name='成立日期')
    members_count = models.IntegerField(verbose_name='成员数')  # 强制填写，移除default
    president_name = models.CharField(max_length=100, verbose_name='社长名字')
    president_id = models.CharField(max_length=20, verbose_name='社长学号')
    president_email = models.EmailField(verbose_name='社长邮箱')
    
    # 社团申请所需材料
    establishment_application = models.FileField(
        upload_to='club_application/%Y/%m/', 
        verbose_name='社团成立申请书',
        help_text='支持上传Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    constitution_draft = models.FileField(
        upload_to='club_application/%Y/%m/', 
        verbose_name='社团章程草案',
        help_text='支持上传Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    three_year_plan = models.FileField(
        upload_to='club_application/%Y/%m/', 
        verbose_name='社团三年发展规划',
        help_text='支持上传Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    leaders_resumes = models.FileField(
        upload_to='club_application/%Y/%m/', 
        verbose_name='社团拟任负责人和指导老师的详细简历和身份证复印件',
        help_text='支持上传压缩包(.zip, .rar)或Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    one_month_activity_plan = models.FileField(
        upload_to='club_application/%Y/%m/', 
        verbose_name='社团组建一个月后的活动计划',
        help_text='支持上传Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    advisor_certificates = models.FileField(
        upload_to='club_application/%Y/%m/', 
        verbose_name='社团老师的相关专业证书',
        help_text='支持上传压缩包(.zip, .rar)或图片文件(.jpg, .png)',
        null=True, 
        blank=True
    )
    
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='申请用户')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_club_registrations', verbose_name='审核人')
    reviewer_comment = models.TextField(blank=True, verbose_name='审核意见')
    # 社长是否已读审核结果
    is_read = models.BooleanField(default=False, verbose_name='社长是否已读')
    # 重新提交追踪 - 表示这是第几次提交（1为初始提交，2+ 为重新提交）
    resubmission_attempt = models.IntegerField(default=1, verbose_name='提交次数')
    
    class Meta:
        verbose_name = '社团注册申请'
        verbose_name_plural = '社团注册申请'
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"{self.club_name} - {self.get_status_display()}"

    def get_final_reviewer(self):
        """获取最终审核通过的审核人"""
        if self.status == 'approved':
            last_approved_review = self.reviews.filter(status='approved').last()
            if last_approved_review:
                return last_approved_review.reviewer
        return None


class ClubApplicationReview(models.Model):
    """社团申请审核记录模型"""
    STATUS_CHOICES = [
        ('approved', '已批准'),
        ('rejected', '被拒绝'),
    ]
    
    # 定义可能的拒绝材料类型
    REJECTED_MATERIALS_CHOICES = [
        ('establishment_application', '社团成立申请书'),
        ('constitution_draft', '社团章程草案'),
        ('three_year_plan', '社团三年发展规划'),
        ('leaders_resumes', '社团拟任负责人和指导老师的详细简历和身份证复印件'),
        ('one_month_activity_plan', '社团组建一个月后的活动计划'),
        ('advisor_certificates', '社团老师的相关专业证书'),
    ]
    
    application = models.ForeignKey(ClubRegistrationRequest, on_delete=models.CASCADE, related_name='reviews', verbose_name='社团申请')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='application_reviews', verbose_name='审核人')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name='审核结果')
    comment = models.TextField(blank=True, verbose_name='审核意见')
    reviewed_at = models.DateTimeField(auto_now_add=True, verbose_name='审核时间')
    submission_attempt = models.IntegerField(default=1, verbose_name='提交次数')
    
    # 存储被拒绝的材料列表
    rejected_materials = models.JSONField(default=list, verbose_name='被拒绝的材料', blank=True)
    
    class Meta:
        verbose_name = '社团申请审核记录'
        verbose_name_plural = '社团申请审核记录'
        unique_together = ['application', 'reviewer', 'submission_attempt']  # 防止同一干事多次审核同一申请


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


class ClubRegistration(models.Model):
    """社团注册模型（已有社团的注册功能）"""
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已批准'),
        ('rejected', '被拒绝'),
    ]
    
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='registrations', verbose_name='社团')
    registration_period = models.ForeignKey(RegistrationPeriod, on_delete=models.CASCADE, related_name='registrations', verbose_name='注册周期', null=True, blank=True)
    
    # 社团注册所需材料
    registration_form = models.FileField(
        upload_to='club_registration/%Y/%m/', 
        verbose_name='社团注册申请表',
        help_text='支持上传Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    basic_info_form = models.FileField(
        upload_to='club_registration/%Y/%m/', 
        verbose_name='学生社团基础信息表',
        help_text='支持上传Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    membership_fee_form = models.FileField(
        upload_to='club_registration/%Y/%m/', 
        verbose_name='会费表或免收会费说明书',
        help_text='支持上传Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    leader_change_application = models.FileField(
        upload_to='club_registration/%Y/%m/', 
        verbose_name='社团主要负责人变动申请',
        help_text='支持上传Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    meeting_minutes = models.FileField(
        upload_to='club_registration/%Y/%m/', 
        verbose_name='社团大会会议记录',
        help_text='支持上传Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    name_change_application = models.FileField(
        upload_to='club_registration/%Y/%m/', 
        verbose_name='社团名称变更申请表',
        help_text='支持上传Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    advisor_change_application = models.FileField(
        upload_to='club_registration/%Y/%m/', 
        verbose_name='社团指导老师变动申请表',
        help_text='支持上传Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    business_advisor_change_application = models.FileField(
        upload_to='club_registration/%Y/%m/', 
        verbose_name='社团业务指导单位变动申请表',
        help_text='支持上传Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    new_media_application = models.FileField(
        upload_to='club_registration/%Y/%m/', 
        verbose_name='新媒体平台建立申请表',
        help_text='支持上传Word文档(.docx)',
        null=True, 
        blank=True
    )
    
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='申请用户')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    reviewer_comment = models.TextField(blank=True, verbose_name='审核意见')
    # 社长是否已读审核结果
    is_read = models.BooleanField(default=False, verbose_name='社长是否已读')
    # 重新提交追踪 - 表示这是第几次提交（1为初始提交，2+ 为重新提交）
    resubmission_attempt = models.IntegerField(default=1, verbose_name='提交次数')
    
    class Meta:
        verbose_name = '社团注册'
        verbose_name_plural = '社团注册'

    def __str__(self):
        return f"{self.club.name} - 注册申请"

    def get_final_reviewer(self):
        """获取最终审核通过的审核人"""
        if self.status == 'approved':
            last_approved_review = self.reviews.filter(status='approved').last()
            if last_approved_review:
                return last_approved_review.reviewer
        return None


class ClubRegistrationReview(models.Model):
    """社团注册审核记录模型"""
    STATUS_CHOICES = [
        ('approved', '已批准'),
        ('rejected', '被拒绝'),
    ]
    
    # 定义可能的拒绝材料类型
    REJECTED_MATERIALS_CHOICES = [
        ('registration_form', '社团注册申请表'),
        ('basic_info_form', '学生社团基础信息表'),
        ('fee_form', '三会费表或免收会费说明书'),
        ('leader_change_form', '社团主要负责人变动申请'),
        ('meeting_minutes', '社团大会会议记录'),
        ('name_change_form', '社团名称变更申请表'),
        ('advisor_change_form', '社团指导老师变动申请表'),
        ('business_unit_change_form', '社团业务指导单位变动申请表'),
        ('new_media_form', '新媒体平台建立申请表'),
    ]
    
    registration = models.ForeignKey(ClubRegistration, on_delete=models.CASCADE, related_name='reviews', verbose_name='社团注册')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='registration_reviews', verbose_name='审核人')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name='审核结果')
    comment = models.TextField(blank=True, verbose_name='审核意见')
    reviewed_at = models.DateTimeField(auto_now_add=True, verbose_name='审核时间')
    submission_attempt = models.IntegerField(default=1, verbose_name='提交次数')
    
    # 存储被拒绝的材料列表
    rejected_materials = models.JSONField(default=list, verbose_name='被拒绝的材料', blank=True)
    
    class Meta:
        verbose_name = '社团注册审核记录'
        verbose_name_plural = '社团注册审核记录'
        ordering = ['-reviewed_at']
        unique_together = ['registration', 'reviewer', 'submission_attempt']  # 防止同一干事多次审核同一注册
    
    def __str__(self):
        reviewer_name = self.reviewer.profile.real_name if hasattr(self.reviewer, 'profile') else self.reviewer.username
        return f"{reviewer_name} 审核 {self.registration} - {self.get_status_display()}"


class PresidentTransition(models.Model):
    """社长换届申请模型"""
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已批准'),
        ('rejected', '被拒绝'),
    ]
    
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='president_transitions', verbose_name='社团')
    old_president = models.ForeignKey(User, on_delete=models.CASCADE, related_name='outgoing_transitions', verbose_name='原社长')
    # 新社长由现有成员选择，存储为Officer记录而非手填信息
    new_president_officer = models.ForeignKey(Officer, on_delete=models.PROTECT, related_name='incoming_transitions', verbose_name='新社长干部记录', null=True, blank=True)
    transition_date = models.DateField(verbose_name='换届日期')
    transition_reason = models.TextField(verbose_name='换届原因')
    
    # 换届表文件
    transition_form = models.FileField(
        upload_to='president_transition/%Y/%m/', 
        verbose_name='社团主要负责人变动申请表',
        help_text='支持上传Word文档(.docx)或PDF文件(.pdf)'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_transitions', verbose_name='审核人')
    reviewer_comment = models.TextField(blank=True, verbose_name='审核意见')
    
    # 社长是否已读审核结果
    is_read = models.BooleanField(default=False, verbose_name='社长是否已读')
    # 重新提交追踪 - 表示这是第几次提交（1为初始提交，2+ 为重新提交）
    resubmission_attempt = models.IntegerField(default=1, verbose_name='提交次数')
    
    class Meta:
        verbose_name = '社长换届申请'
        verbose_name_plural = '社长换届申请'
        ordering = ['-submitted_at']
    
    def __str__(self):
        new_pres_name = self.new_president_officer.user_profile.real_name if self.new_president_officer and self.new_president_officer.user_profile else '未知'
        return f"{self.club.name} - 换届申请 ({self.old_president.username} -> {new_pres_name})"

    def get_final_reviewer(self):
        """获取最终审核通过的审核人"""
        if self.status == 'approved':
            return self.reviewer
        return None


class ActivityApplication(models.Model):
    """活动申请模型"""
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('staff_approved', '干事已批准'),
        ('approved', '已批准'),
        ('rejected', '被拒绝'),
    ]
    
    ACTIVITY_TYPE_CHOICES = [
        ('academic', '学术类'),
        ('cultural', '文化类'),
        ('sports', '体育类'),
        ('volunteer', '志愿类'),
        ('entertainment', '娱乐类'),
        ('other', '其他'),
    ]
    
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='activity_applications', verbose_name='社团')
    activity_name = models.CharField(max_length=200, verbose_name='活动名称')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPE_CHOICES, default='other', verbose_name='活动类型')
    activity_description = models.TextField(verbose_name='活动描述')
    activity_date = models.DateField(verbose_name='活动日期')
    activity_time_start = models.TimeField(verbose_name='活动开始时间')
    activity_time_end = models.TimeField(verbose_name='活动结束时间')
    activity_location = models.CharField(max_length=200, verbose_name='活动地点')
    expected_participants = models.IntegerField(verbose_name='预计参与人数')
    budget = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='活动预算', default=0)
    
    # 活动申请表文件
    application_form = models.FileField(
        upload_to='activity_application/%Y/%m/', 
        verbose_name='活动申请表',
        help_text='支持上传Word文档(.docx)或PDF文件(.pdf)'
    )
    
    contact_person = models.CharField(max_length=100, verbose_name='联系人')
    contact_phone = models.CharField(max_length=20, verbose_name='联系电话')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')
    
    # 干事审核
    staff_reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='干事审核时间')
    staff_reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_reviewed_activities', verbose_name='干事审核人')
    staff_comment = models.TextField(blank=True, verbose_name='干事审核意见')
    staff_approved = models.BooleanField(null=True, blank=True, verbose_name='干事是否批准')
    
    # 保留旧字段以兼容
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_activities', verbose_name='审核人')
    reviewer_comment = models.TextField(blank=True, verbose_name='审核意见')
    
    # 社长是否已读审核结果
    is_read = models.BooleanField(default=False, verbose_name='社长是否已读')
    # 重新提交追踪 - 表示这是第几次提交（1为初始提交，2+ 为重新提交）
    resubmission_attempt = models.IntegerField(default=1, verbose_name='提交次数')
    
    class Meta:
        verbose_name = '活动申请'
        verbose_name_plural = '活动申请'
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"{self.club.name} - {self.activity_name} ({self.activity_date})"

    def get_final_reviewer(self):
        """获取最终审核通过的审核人"""
        if self.status == 'approved':
            return self.staff_reviewer
        return None
    
    def update_status(self):
        """根据审核结果更新状态"""
        if self.staff_approved is False:
            self.status = 'rejected'
        elif self.staff_approved is True:
            self.status = 'approved'
        else:
            self.status = 'pending'
        
        # 更新reviewed_at为最后一次审核的时间
        if self.staff_reviewed_at:
            self.reviewed_at = self.staff_reviewed_at
        
        self.save()


class ActivityApplicationHistory(models.Model):
    """活动申请审核历史"""
    activity_application = models.ForeignKey(ActivityApplication, on_delete=models.CASCADE, related_name='history', verbose_name='关联活动申请')
    attempt_number = models.IntegerField(verbose_name='提交次数')
    
    activity_name = models.CharField(max_length=200, verbose_name='活动名称')
    activity_date = models.DateField(verbose_name='活动日期')
    
    submitted_at = models.DateTimeField(verbose_name='提交时间')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_history_reviews', verbose_name='审核人')
    
    status = models.CharField(max_length=20, choices=ActivityApplication.STATUS_CHOICES, verbose_name='状态')
    reviewer_comment = models.TextField(blank=True, verbose_name='审核意见')
    
    class Meta:
        verbose_name = '活动申请审核历史'
        verbose_name_plural = '活动申请审核历史'
        ordering = ['-attempt_number']


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


class MaterialRequirement(models.Model):
    """材料上传要求配置"""
    REQUEST_TYPE_CHOICES = [
        ('annual_review', '社团年审'),
        ('club_registration', '社团注册'),
        ('club_application', '社团申请'),
        ('president_transition', '社长换届'),
        ('reimbursement', '报销申请'),
        ('activity_application', '活动申请'),
    ]

    request_type = models.CharField(max_length=50, choices=REQUEST_TYPE_CHOICES, verbose_name='申请类型')
    name = models.CharField(max_length=200, verbose_name='材料名称')
    description = models.TextField(blank=True, verbose_name='材料描述')
    is_required = models.BooleanField(default=True, verbose_name='是否必填')
    allowed_extensions = models.CharField(max_length=200, default='.docx,.pdf,.jpg,.png,.zip', verbose_name='允许的文件扩展名')
    max_size_mb = models.IntegerField(default=10, verbose_name='最大文件大小(MB)')
    order = models.IntegerField(default=0, verbose_name='排序权重')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    
    # 映射到旧字段名 (用于兼容性)
    legacy_field_name = models.CharField(max_length=100, blank=True, null=True, verbose_name='旧字段名')
    
    # 模板文件
    template_file = models.FileField(upload_to='templates/', blank=True, null=True, verbose_name='模板文件', help_text='供用户下载的模板文件')
    
    # Material Icon
    icon = models.CharField(max_length=50, default='cloud_upload', verbose_name='图标', help_text='Material Icons 图标名称')

    class Meta:
        verbose_name = '材料要求'
        verbose_name_plural = '材料要求'
        ordering = ['request_type', 'order']
        
    def __str__(self):
        return f"{self.get_request_type_display()} - {self.name}"


class SubmittedFile(models.Model):
    """通用的提交文件模型"""
    requirement = models.ForeignKey(MaterialRequirement, on_delete=models.CASCADE, verbose_name='对应材料要求', null=True, blank=True)
    file = models.FileField(upload_to='submissions/%Y/%m/', verbose_name='文件')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')
    
    # 使用GenericForeignKey关联到各种申请模型
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    class Meta:
        verbose_name = '提交文件'
        verbose_name_plural = '提交文件'
        ordering = ['uploaded_at']
