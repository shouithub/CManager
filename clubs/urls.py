# type: ignore
from django.urls import path, re_path
from . import views
from . import auth_views
from . import api_views
from . import export_views

app_name = 'clubs'

urlpatterns = [
    # API endpoints
    path('api/staff/review-history/<str:review_type>/', api_views.api_staff_review_history, name='api_staff_review_history'),

    # 公共页面
    path('', views.index, name='index'),
    path('club/<int:club_id>/', views.club_detail, name='club_detail'),
    path('activities/', views.public_activities, name='public_activities'),  # 活动管理页面（仅管理员干事可见）
    path('admin-panel/departments/', views.manage_departments, name='manage_departments'),  # 部门管理
    path('admin-panel/departments/add/', views.add_department, name='add_department'),
    path('admin-panel/departments/edit/<int:dept_id>/', views.edit_department, name='edit_department'),
    path('admin-panel/departments/delete/<int:dept_id>/', views.delete_department, name='delete_department'),
    
    # 认证相关
    path('login/', auth_views.user_login, name='login'),
    path('register/', auth_views.register, name='register'),
    path('logout/', auth_views.user_logout, name='logout'),
    path('change-account-settings/', auth_views.change_account_settings, name='change_account_settings'),
    path('edit-profile/', auth_views.edit_profile, name='edit_profile'),
    path('user/<int:user_id>/', views.user_detail, name='user_detail'),
    path('delete-account/', auth_views.delete_account, name='delete_account'),
    
    # 用户/社长操作
    path('dashboard/', auth_views.user_dashboard, name='user_dashboard'),
    path('register-club/', views.register_club, name='register_club'),  # 社团申请
    path('club/<int:club_id>/submit-registration/', views.submit_club_registration, name='submit_club_registration'),  # 社团注册
    path('club/<int:club_id>/submit-review/', views.submit_review, name='submit_review'),
    # 统一修改材料页面的URL
    path('club/<int:club_id>/edit-rejected-review/', views.edit_rejected_review, name='edit_rejected_review'),

    path('club/<int:club_id>/submit-reimbursement/', views.submit_reimbursement, name='submit_reimbursement'),
    path('club/<int:club_id>/view-reimbursements/', views.view_reimbursements, name='view_reimbursements'),


    path('approval-center/<str:tab>/', views.approval_center_tabs, name='approval_center'),  # 审批中心
    path('approval-center-mobile/', views.approval_center_mobile, name='approval_center_mobile'),  # 审批中心移动端
    path('approval-center-history/<str:item_type>/', views.approval_history_by_type, name='approval_history_by_type'),  # 按类型显示审批历史
    path('approval-center-detail/<str:item_type>/<int:item_id>/', views.approval_detail, name='approval_detail'),  # 审批详情
    path('submission/<int:submission_id>/cancel/', views.cancel_submission, name='cancel_submission'),



    
    # 干事审核
    path('staff/audit-center/<str:tab>/', views.staff_audit_center, name='staff_audit_center'),  # 干事审核中心
    path('staff/audit-center-mobile/', views.staff_audit_center_mobile, name='staff_audit_center_mobile'),  # 获取社团列表API
    path('api/clubs/list/', views.get_clubs_list, name='get_clubs_list'),
    path('api/department/<int:department_id>/members/', views.get_department_members, name='get_department_members'),
    # path('staff/home/', auth_views.staff_dashboard_home, name='staff_dashboard_home'),
    # edit_department_intro has been replaced by manage_departments
    # path('staff/edit-department-intro/<str:department>/', auth_views.edit_department_intro, name='edit_department_intro'),
    
    path('staff/management/', auth_views.staff_management, name='staff_management'),
    path('staff/manage-department/', auth_views.manage_department_staff, name='manage_department_staff'),
    # 管理员 - 锁定账号管理
    path('admin/locked-accounts/', views.locked_accounts, name='locked_accounts'),
    path('admin/unlock-account/<str:username>/', views.unlock_account, name='unlock_account'),
    path('admin/favicon/', views.manage_favicon, name='manage_favicon'),

    # 强制重置密码路由已移除，使用管理员重置密码表单：admin-panel/reset-user-password/
    path('staff/manage-clubs/', auth_views.manage_staff_clubs, name='manage_staff_clubs'),
    path('staff/view-users/', views.staff_view_users, name='staff_view_users'),
    # path('staff/review-history/<str:review_type>/', views.staff_review_history, name='staff_review_history'),
    path('staff/review-detail/<str:item_type>/<int:item_id>/', views.staff_review_detail, name='staff_review_detail'),


    path('zip-review-docs/<int:submission_id>/', views.zip_review_docs, name='zip_review_docs'),

    # 按类型明确的压缩下载路由
    path('zip-club-registration-docs/<int:registration_id>/', views.zip_club_registration_docs, name='zip_club_registration_docs'),
    path('zip-registration-request-docs/<int:request_id>/', views.zip_registration_request_docs, name='zip_registration_request_docs'),

    path('zip-reimbursement-docs/<int:reimbursement_id>/', views.zip_reimbursement_docs, name='zip_reimbursement_docs'),

    path('zip-president-transition-docs/<int:transition_id>/', views.zip_president_transition_docs, name='zip_president_transition_docs'),
    
    path('zip-activity-application-docs/<int:application_id>/', views.zip_activity_application_docs, name='zip_activity_application_docs'),

    # 统一审核路由
    path('staff/review/<int:club_id>/', views.review_request, name='review'),
    
    # 具体审核路由
    path('staff/review-submission/<int:submission_id>/', views.review_submission, name='review_submission'),
    path('staff/review-reimbursement/<int:reimbursement_id>/', views.review_reimbursement, name='review_reimbursement'),
    path('staff/application/<int:registration_id>/', views.review_club_registration, name='review_club_registration'),
    path('staff/review-club-registration-submission/<int:registration_id>/', views.review_club_registration_submission, name='review_club_registration_submission'),
    
    path('club/<int:club_id>/update-description/', views.update_club_description, name='update_club_description'),
    path('staff/direct-edit-club-info/<int:club_id>/', views.direct_edit_club_info, name='direct_edit_club_info'),
    path('staff/toggle-review-enabled/<int:club_id>/', views.toggle_review_enabled, name='toggle_review_enabled'),
    path('staff/toggle-club-registration-enabled/<int:club_id>/', views.toggle_club_registration_enabled, name='toggle_club_registration_enabled'),
    path('staff/toggle-all-review-enabled/', views.toggle_all_review_enabled, name='toggle_all_review_enabled'),
    path('staff/toggle-registration-enabled/', views.toggle_registration_enabled, name='toggle_registration_enabled'),
    path('staff/change-club-status/<int:club_id>/', views.change_club_status, name='change_club_status'),
    path('staff/delete-club/<int:club_id>/', views.delete_club, name='delete_club'),
    path('staff/upload-template/', views.upload_template, name='upload_template'),
    
    # 社长换届申请路由
    path('club/<int:club_id>/submit-president-transition/', views.submit_president_transition, name='submit_president_transition'),
    path('club/<int:club_id>/view-president-transitions/', views.view_president_transitions, name='view_president_transitions'),
    path('staff/review-president-transition/<int:transition_id>/', views.review_president_transition, name='review_president_transition'),
    
    # 活动申请路由
    path('club/<int:club_id>/submit-activity-application/', views.submit_activity_application, name='submit_activity_application'),
    path('club/<int:club_id>/view-activity-applications/', views.view_activity_applications, name='view_activity_applications'),
    path('staff/review-activity-application/<int:activity_id>/', views.review_activity_application, name='review_activity_application'),
    path('activity/<int:activity_id>/edit/', views.edit_activity_application, name='edit_activity_application'),
    
    # 房间借用
    path('room/calendar/', views.room_calendar, name='room_calendar'),
    path('room/submit-booking/', views.submit_room_booking, name='submit_room_booking'),
    path('room/my-bookings/', views.my_room_bookings, name='my_room_bookings'),
    path('room/edit-booking/<int:booking_id>/', views.edit_room_booking, name='edit_room_booking'),
    path('room/delete-booking/<int:booking_id>/', views.delete_room_booking, name='delete_room_booking'),
    path('room/export-weekly/', export_views.export_room_bookings_weekly, name='export_room_bookings_weekly'),
    
    # 房间管理 (管理员)
    path('admin-panel/rooms/', views.admin_room_list, name='admin_room_list'),
    path('admin-panel/rooms/add/', views.admin_room_add, name='admin_room_add'),
    path('admin-panel/rooms/edit/<int:room_id>/', views.admin_room_edit, name='admin_room_edit'),
    path('admin-panel/rooms/delete/<int:room_id>/', views.admin_room_delete, name='admin_room_delete'),
    
    # 预约管理 (管理员)
    path('admin-panel/bookings/', views.admin_booking_management, name='admin_booking_management'),
    path('admin-panel/time-slots/', views.admin_time_slots, name='admin_time_slots'),
    path('admin-panel/time-slots/add/', views.admin_time_slot_add, name='admin_time_slot_add'),
    path('admin-panel/time-slots/edit/<int:slot_id>/', views.admin_time_slot_edit, name='admin_time_slot_edit'),
    path('admin-panel/time-slots/delete/<int:slot_id>/', views.admin_time_slot_delete, name='admin_time_slot_delete'),

    # 活动导出
    path('activities/export/', export_views.export_activities, name='export_activities'),
    
    # 审核中心导出
    path('staff/audit-center/<str:tab>/export/', export_views.export_audit_center_data, name='export_audit_center_data'),
    
    # 管理员功能
    path('admin-panel/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/carousel/', views.manage_carousel, name='manage_carousel'),
    path('admin-panel/carousel/add/', views.add_carousel, name='add_carousel'),
    path('admin-panel/carousel/edit/<int:carousel_id>/', views.edit_carousel, name='edit_carousel'),
    path('admin-panel/carousel/delete/<int:carousel_id>/', views.delete_carousel, name='delete_carousel'),
    
    # Material Requirement Management
    path('admin-panel/materials/', views.manage_material_requirements, name='manage_material_requirements'),
    path('admin-panel/materials/add/', views.add_material_requirement, name='add_material_requirement'),
    path('admin-panel/materials/edit/<int:req_id>/', views.edit_material_requirement, name='edit_material_requirement'),
    path('admin-panel/materials/delete/<int:req_id>/', views.delete_material_requirement, name='delete_material_requirement'),

    path('admin-panel/publish-announcement/', views.publish_announcement, name='publish_announcement'),
    path('admin-panel/delete-announcement/<int:announcement_id>/', views.delete_announcement, name='delete_announcement'),
    path('admin-panel/edit-announcement/<int:announcement_id>/', views.edit_announcement, name='edit_announcement'),
    path('admin-panel/manage-users/', views.manage_users, name='manage_users'),
    path('admin-panel/create-user/', views.create_user, name='create_user'),
    path('admin-panel/edit-user-account/<int:user_id>/', views.admin_edit_user_account, name='admin_edit_user_account'),
    path('admin-panel/change-user-role/<int:user_id>/', views.change_user_role, name='change_user_role'),
    path('admin-panel/change-staff-attributes/<int:user_id>/', views.change_staff_attributes, name='change_staff_attributes'),
    path('admin-panel/smtp-config/', views.manage_smtp_config, name='manage_smtp_config'),
    path('admin-panel/review/<int:club_id>/', views.review_request, name='admin_review'),
    
    # 自定义文件下载路由
    path('download/', views.download_file, name='download_file'),
]