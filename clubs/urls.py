# type: ignore
from django.urls import path, re_path
from . import views
from . import oobe_views
from . import auth_views
from . import export_views

app_name = 'clubs'

urlpatterns = [
    path('oobe/', oobe_views.oobe_setup, name='oobe_setup'),
    path('oobe/test-email/', oobe_views.oobe_test_email, name='oobe_test_email'),
    # API endpoints
    path('api/notification-counts/', views.notification_counts, name='notification_counts'),

    # 公共页面
    path('', views.index, name='index'),
    path('club/<int:club_id>/', views.club_detail, name='club_detail'),
    path('club/<int:club_id>/member-token/', views.generate_member_join_token, name='generate_member_join_token'),
    path('club/<int:club_id>/member-tokens/', views.list_member_tokens, name='list_member_tokens'),
    path('club/<int:club_id>/member-token/<int:token_id>/delete/', views.delete_member_token, name='delete_member_token'),
    path('member/join/<str:token_code>/', views.member_join_by_token, name='member_join_by_token'),
    path('activities/', views.public_activities, name='public_activities'),  # 活动管理页面（仅管理员干事可见）
    path('activities/<int:activity_id>/register/', views.register_activity, name='register_activity'),
    path('activities/<int:activity_id>/unregister/', views.unregister_activity, name='unregister_activity'),
    path('admin-panel/departments/', views.manage_departments, name='manage_departments'),  # 部门管理
    path('admin-panel/departments/add/', views.add_department, name='add_department'),
    path('admin-panel/departments/edit/<int:dept_id>/', views.edit_department, name='edit_department'),
    path('admin-panel/departments/delete/<int:dept_id>/', views.delete_department, name='delete_department'),
    
    # 认证相关
    path('login/', auth_views.user_login, name='login'),
    path('register/', auth_views.register, name='register'),
    path('logout/', auth_views.user_logout, name='logout'),
    path('change-account-settings/', auth_views.change_account_settings, name='change_account_settings'),
    path('extend-inactive-period/', auth_views.extend_inactive_period, name='extend_inactive_period'),
    path('edit-profile/', auth_views.edit_profile, name='edit_profile'),
    path('user/<int:user_id>/', views.user_detail, name='user_detail'),
    path('delete-account/', auth_views.delete_account, name='delete_account'),
    
    # 用户/社长操作
    path('dashboard/', auth_views.user_dashboard, name='user_dashboard'),
    path('president/members/', views.president_member_management, name='president_member_management'),
    path('forms/<slug:channel_slug>/<int:club_id>/submit/', views.submit_dynamic_form, name='submit_dynamic_form'),
    path('forms/submissions/<str:submission_key>/revise/', views.revise_dynamic_submission, name='revise_dynamic_submission'),
    # 统一修改材料页面的URL



    path('approval-center/<str:tab>/', views.approval_center_tabs, name='approval_center'),  # 审批中心
    path('approval-center-detail/<str:item_type>/<str:submission_key>/', views.approval_detail, name='approval_detail'),  # 审批详情
    path('submission/<str:submission_key>/cancel/', views.cancel_submission, name='cancel_submission'),



    
    # 干事审核
    path('staff/audit-center/<str:tab>/', views.staff_audit_center, name='staff_audit_center'),  # 干事审核中心
    path('staff/audit-center/<str:tab>/<str:item_key>/delete/', views.delete_audit_request, name='delete_audit_request'),
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
    path('staff/form-submission/<str:submission_key>/review/', views.staff_review_form_submission, name='staff_review_form_submission'),

    # 统一压缩下载路由：/zip-download/?type=<type>&id=<id>
    path('zip-download/', views.zip_download, name='zip_download'),

    # 统一审核路由
    
    # 具体审核路由
    
    path('club/<int:club_id>/update-description/', views.update_club_description, name='update_club_description'),
    path('staff/direct-edit-club-info/<int:club_id>/', views.direct_edit_club_info, name='direct_edit_club_info'),
    path('staff/form-channels/<int:channel_id>/toggle/', views.toggle_form_channel_cycle, name='toggle_form_channel_cycle'),
    path('staff/form-channels/<int:channel_id>/club/<int:club_id>/toggle/', views.toggle_club_form_channel, name='toggle_club_form_channel'),
    path('staff/change-club-status/<int:club_id>/', views.change_club_status, name='change_club_status'),
    path('staff/delete-club/<int:club_id>/', views.delete_club, name='delete_club'),
    
    # 社长换届申请路由
    
    # 活动申请路由
    
    # 房间借用
    path('room/calendar/', views.room_calendar, name='room_calendar'),
    path('room/submit-booking/', views.submit_room_booking, name='submit_room_booking'),
    path('room/my-bookings/', views.my_room_bookings, name='my_room_bookings'),
    path('room/edit-booking/<int:booking_id>/', views.edit_room_booking, name='edit_room_booking'),
    path('room/delete-booking/<int:booking_id>/', views.delete_room_booking, name='delete_room_booking'),
    path('room/export-weekly/', export_views.export_room_bookings_weekly, name='export_room_bookings_weekly'),
    
    # 预约管理 (管理员)
    path('admin-panel/bookings/', views.admin_booking_management, name='admin_booking_management'),
    path('admin-panel/bookings/rooms/add/', views.admin_room_add, name='admin_room_add'),
    path('admin-panel/bookings/rooms/edit/<int:room_id>/', views.admin_room_edit, name='admin_room_edit'),
    path('admin-panel/bookings/rooms/delete/<int:room_id>/', views.admin_room_delete, name='admin_room_delete'),
    path('admin-panel/bookings/time-slots/add/', views.admin_time_slot_add, name='admin_time_slot_add'),
    path('admin-panel/bookings/time-slots/edit/<int:slot_id>/', views.admin_time_slot_edit, name='admin_time_slot_edit'),
    path('admin-panel/bookings/time-slots/delete/<int:slot_id>/', views.admin_time_slot_delete, name='admin_time_slot_delete'),

    # 活动导出
    path('activities/export/', export_views.export_activities, name='export_activities'),
    
    # 审核中心导出
    path('staff/audit-center/<str:tab>/export/', export_views.export_audit_center_data, name='export_audit_center_data'),
    
    # 管理员功能
    path('admin-panel/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/site-settings/', views.admin_site_settings, name='admin_site_settings'),
    path('admin-panel/carousel/', views.manage_carousel, name='manage_carousel'),
    path('admin-panel/carousel/add/', views.add_carousel, name='add_carousel'),
    path('admin-panel/carousel/edit/<int:carousel_id>/', views.edit_carousel, name='edit_carousel'),
    path('admin-panel/carousel/delete/<int:carousel_id>/', views.delete_carousel, name='delete_carousel'),
    
    # Dynamic form channel management
    path('admin-panel/form-channels/', views.manage_form_channels, name='manage_form_channels'),
    path('admin-panel/form-channels/<int:channel_id>/', views.manage_form_channels, name='manage_form_channels_detail'),
    path('admin-panel/form-channels/save/', views.save_form_channel, name='add_form_channel'),
    path('admin-panel/form-channels/<int:channel_id>/save/', views.save_form_channel, name='edit_form_channel'),
    path('admin-panel/form-channels/<int:channel_id>/delete/', views.delete_form_channel, name='delete_form_channel'),
    path('admin-panel/form-channels/<int:channel_id>/fields/save/', views.save_form_field, name='add_form_field'),
    path('admin-panel/form-channels/<int:channel_id>/fields/<int:field_id>/save/', views.save_form_field, name='edit_form_field'),
    path('admin-panel/form-channels/<int:channel_id>/fields/<int:field_id>/delete/', views.delete_form_field, name='delete_form_field'),
    path('admin-panel/form-channels/<int:channel_id>/cycles/create/', views.create_form_channel_cycle, name='create_form_channel_cycle'),
    path('admin-panel/form-channels/<int:channel_id>/cycles/<int:cycle_id>/close/', views.close_form_channel_cycle, name='close_form_channel_cycle'),

    path('admin-panel/publish-announcement/', views.publish_announcement, name='publish_announcement'),
    path('admin-panel/delete-announcement/<int:announcement_id>/', views.delete_announcement, name='delete_announcement'),
    path('admin-panel/edit-announcement/<int:announcement_id>/', views.edit_announcement, name='edit_announcement'),
    path('admin-panel/assign-presidents/', views.admin_assign_presidents, name='admin_assign_presidents'),
    path('admin-panel/manage-users/', views.manage_users, name='manage_users'),
    path('admin-panel/review-staff-registration/<int:user_id>/', views.review_staff_registration, name='review_staff_registration'),
    path('admin-panel/manage-users/import-csv/', views.import_users_csv, name='import_users_csv'),
    path('admin-panel/manage-users/import-template/', views.download_user_import_template, name='download_user_import_template'),
    path('staff/management/import-clubs-csv/', views.import_clubs_csv, name='import_clubs_csv'),
    path('staff/management/import-clubs-template/', views.download_club_import_template, name='download_club_import_template'),
    path('data/export-all-users-clubs/', views.export_all_users_and_clubs_csv, name='export_all_users_and_clubs_csv'),
    path('admin-panel/create-user/', views.create_user, name='create_user'),
    path('admin-panel/edit-user-account/<int:user_id>/', views.admin_edit_user_account, name='admin_edit_user_account'),
    path('admin-panel/change-user-role/<int:user_id>/', views.change_user_role, name='change_user_role'),
    path('admin-panel/change-staff-attributes/<int:user_id>/', views.change_staff_attributes, name='change_staff_attributes'),
    path('admin-panel/smtp-config/', views.manage_smtp_config, name='manage_smtp_config'),
    path('admin-panel/storage-config/', views.manage_storage_config, name='manage_storage_config'),

    # 自定义文件下载路由
    path('download/', views.download_file, name='download_file'),
]
