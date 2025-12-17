from django.contrib import admin
from .models import Club, Officer, ReviewSubmission, UserProfile, Reimbursement, Template, Announcement, ClubRegistrationRequest, EmailVerificationCode, SMTPConfig, TeacherClubAssignment, ActivityParticipation


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'real_name', 'role', 'student_id', 'created_at')
    list_filter = ('role', 'political_status', 'created_at')
    search_fields = ('user__username', 'user__email', 'real_name', 'student_id')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('基本信息', {
            'fields': ('user', 'role', 'created_at', 'updated_at')
        }),
        ('实名信息', {
            'fields': ('real_name', 'student_id', 'phone', 'wechat', 'political_status')
        }),
    )


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'members_count', 'founded_date', 'president', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Officer)
class OfficerAdmin(admin.ModelAdmin):
    list_display = ('club', 'get_name', 'position', 'get_student_id', 'appointed_date', 'is_current')
    list_filter = ('position', 'is_current', 'club')
    search_fields = ('user_profile__real_name', 'user_profile__student_id', 'club__name')
    readonly_fields = ()
    
    def get_name(self, obj):
        return obj.user_profile.real_name
    get_name.short_description = '姓名'
    
    def get_student_id(self, obj):
        return obj.user_profile.student_id
    get_student_id.short_description = '学号'


@admin.register(ReviewSubmission)
class ReviewSubmissionAdmin(admin.ModelAdmin):
    list_display = ('club', 'submission_year', 'status', 'submitted_at')
    list_filter = ('status', 'submission_year', 'submitted_at')
    search_fields = ('club__name',)
    readonly_fields = ('submitted_at', 'reviewed_at')


@admin.register(Reimbursement)
class ReimbursementAdmin(admin.ModelAdmin):
    list_display = ('club', 'reimbursement_amount', 'status', 'submission_date', 'submitted_at')
    list_filter = ('status', 'submission_date', 'submitted_at')
    search_fields = ('club__name', 'description')
    readonly_fields = ('submitted_at', 'reviewed_at')


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'uploaded_by', 'is_active', 'created_at')
    list_filter = ('template_type', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'created_by', 'published_at', 'expires_at')
    list_filter = ('status', 'created_at', 'published_at')
    search_fields = ('title', 'content')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ClubRegistrationRequest)
class ClubRegistrationRequestAdmin(admin.ModelAdmin):
    list_display = ('club_name', 'president_name', 'status', 'submitted_at')
    list_filter = ('status', 'submitted_at')
    search_fields = ('club_name', 'president_name', 'president_id')
    readonly_fields = ('submitted_at', 'reviewed_at')


@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'is_verified', 'created_at', 'expires_at')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('user__username', 'email')
    readonly_fields = ('created_at',)


@admin.register(SMTPConfig)
class SMTPConfigAdmin(admin.ModelAdmin):
    list_display = ('provider', 'sender_email', 'is_active', 'created_at')
    list_filter = ('provider', 'is_active', 'created_at')
    search_fields = ('sender_email', 'smtp_host')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('基本信息', {
            'fields': ('provider', 'sender_email', 'is_active')
        }),
        ('SMTP设置', {
            'fields': ('smtp_host', 'smtp_port', 'use_tls')
        }),
        ('认证信息', {
            'fields': ('sender_password',)
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TeacherClubAssignment)
class TeacherClubAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'club', 'role', 'assigned_date', 'is_active')
    list_filter = ('role', 'is_active', 'assigned_date')
    search_fields = ('user__username', 'user__first_name', 'club__name')
    readonly_fields = ('assigned_date',)
    fieldsets = (
        ('分配信息', {
            'fields': ('user', 'club', 'role', 'is_active')
        }),
        ('时间戳', {
            'fields': ('assigned_date',)
        }),
    )


@admin.register(ActivityParticipation)
class ActivityParticipationAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_activity_name', 'status', 'applied_at')
    list_filter = ('status', 'applied_at')
    search_fields = ('user__username', 'activity__activity_name')
    readonly_fields = ('applied_at', 'approved_at')
    
    def get_activity_name(self, obj):
        return obj.activity.activity_name
    get_activity_name.short_description = '活动名称'
