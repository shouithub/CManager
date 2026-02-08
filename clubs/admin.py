from django.contrib import admin
from .models import Club, Officer, ReviewSubmission, UserProfile, Reimbursement, Template, Announcement, ClubRegistrationRequest, EmailVerificationCode, SMTPConfig, CarouselImage, Department, Room, TimeSlot, RoomBooking


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'capacity', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('label', 'start_time', 'end_time', 'is_active')
    list_filter = ('is_active',)
    ordering = ('start_time',)


@admin.register(RoomBooking)
class RoomBookingAdmin(admin.ModelAdmin):
    list_display = ('room', 'user', 'club', 'booking_date', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'booking_date', 'room')
    search_fields = ('user__username', 'club__name', 'purpose')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'real_name', 'role', 'department_link', 'staff_level', 'student_id', 'created_at')
    list_filter = ('role', 'department_link', 'staff_level', 'political_status', 'created_at')
    search_fields = ('user__username', 'user__email', 'real_name', 'student_id')
    readonly_fields = ('created_at', 'updated_at', 'department')
    fieldsets = (
        ('基本信息', {
            'fields': ('user', 'role', 'created_at', 'updated_at')
        }),
        ('干事信息', {
            'fields': ('department_link', 'department', 'staff_level'),
            'classes': ('collapse',),
            'description': '仅对干事角色有效。部门关联为主要字段，部门文本字段为兼容保留。'
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
    get_name.short_description = '姓名'  # type: ignore
    
    def get_student_id(self, obj):
        return obj.user_profile.student_id
    get_student_id.short_description = '学号'  # type: ignore


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


@admin.register(CarouselImage)
class CarouselImageAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploaded_by', 'uploaded_at', 'is_active')
    list_filter = ('is_active', 'uploaded_at')
    search_fields = ('title', 'description')
    readonly_fields = ('uploaded_at',)
    fieldsets = (
        ('基本信息', {
            'fields': ('image', 'title', 'description', 'is_active')
        }),
        ('上传信息', {
            'fields': ('uploaded_by', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'updated_at', 'updated_by')
    list_filter = ('updated_at',)
    search_fields = ('name', 'description', 'highlights')
    readonly_fields = ('updated_at',)
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'description', 'highlights', 'icon', 'order')
        }),
        ('更新信息', {
            'fields': ('updated_by', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
