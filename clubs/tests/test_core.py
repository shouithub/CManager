import json
import zipfile
from datetime import date, time
from hashlib import md5
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from ..avatar_utils import clear_avatar_settings_cache, get_profile_avatar_url
from ..models import (
    Announcement,
    ChannelExampleFile,
    Club,
    ClubMember,
    FormChannel,
    FormCycle,
    FormField,
    FormFieldValue,
    FormSubmission,
    FormSubmissionReview,
    Officer,
    RegistrationToken,
    Room,
    RoomBooking,
    SiteSettings,
    SMTPConfig,
    StaffClubRelation,
    TimeSlot,
    UserProfile,
)
from ..services.booking_service import BookingConflictError, create_room_booking
from ..services.registration_service import (
    RegistrationTokenUnavailable,
    register_member_with_token,
)
from ..upload_security import validate_upload


class AvatarServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='avatar-admin',
            email='',
            password='test-password',
        )
        self.config = SiteSettings.get_settings()
        self.config.cravatar_enabled = True
        self.config.save(update_fields=['cravatar_enabled'])
        clear_avatar_settings_cache()
        self.client.force_login(self.user)

    def tearDown(self):
        clear_avatar_settings_cache()

    def test_cravatar_is_an_individual_user_choice(self):
        profile = self.user.profile
        profile.avatar_email = 'Person@Example.COM'
        profile.avatar_source = 'cravatar'
        profile.save(update_fields=['avatar_email', 'avatar_source'])
        expected_hash = md5(b'person@example.com').hexdigest()

        self.assertIn(expected_hash, get_profile_avatar_url(profile))

    def test_cravatar_proxy_rejects_invalid_digest(self):
        response = self.client.get('/cravatar/not-a-digest/', secure=True)
        self.assertEqual(response.status_code, 404)

    def test_cravatar_proxy_serves_cached_with_immutable_header(self):
        digest = 'a' * 32
        cache.set(f'cravatar:{digest}:160:mp:g', {'content': b'png-bytes', 'content_type': 'image/png'})

        response = self.client.get(f'/cravatar/{digest}/', secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'public, max-age=31536000, immutable')
        self.assertEqual(response.content, b'png-bytes')

    def test_is_image_file_supports_model_file_objects(self):
        from django.core.files.base import ContentFile
        from ..templatetags.common_tags import is_image_file
        from ..models import FormUploadedFile

        channel = FormChannel.objects.create(name='图片通道', slug='image-channel', is_active=True)
        submission = FormSubmission.objects.create(
            channel=channel,
            club=Club.objects.create(name='图片社团', founded_date=date(2026, 1, 1)),
            submitter=self.user,
        )
        field = FormField.objects.create(channel=channel, field_key='img', label='图片', field_type='file')
        uploaded = FormUploadedFile.objects.create(
            submission=submission,
            field=field,
            file=ContentFile(b'png', name='photo.png'),
            original_name='photo.png',
        )

        self.assertTrue(is_image_file(uploaded))

    def test_disabled_cravatar_does_not_override_local_avatar(self):
        profile = self.user.profile
        profile.avatar_email = 'person@example.com'
        profile.avatar_source = 'cravatar'
        profile.save(update_fields=['avatar_email', 'avatar_source'])
        self.config.cravatar_enabled = False
        self.config.save(update_fields=['cravatar_enabled'])
        clear_avatar_settings_cache()

        self.assertEqual(get_profile_avatar_url(profile), '')

    def test_admin_only_controls_cravatar_availability(self):
        response = self.client.post(
            reverse('clubs:site_settings'),
            {'form_type': 'avatar_settings', 'cravatar_enabled': 'on'},
            secure=True,
        )

        self.assertRedirects(response, reverse('clubs:site_settings'), fetch_redirect_response=False)
        self.config.refresh_from_db()
        self.assertTrue(self.config.cravatar_enabled)

    def test_avatar_upload_returns_json_when_accept_header_requests_it(self):
        response = self.client.post(
            reverse('clubs:edit_profile'),
            {'action': 'upload_avatar'},
            HTTP_ACCEPT='application/json',
            secure=True,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['message'], '请选择图片文件')

    def test_upload_avatar_deletes_old_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from ..storage_backends import ClubStorage

        def upload_png():
            buffer = BytesIO()
            Image.new('RGB', (32, 32), 'red').save(buffer, format='PNG')
            response = self.client.post(
                reverse('clubs:edit_profile'),
                {
                    'action': 'upload_avatar',
                    'avatar': SimpleUploadedFile('avatar.png', buffer.getvalue(), content_type='image/png'),
                },
                HTTP_ACCEPT='application/json',
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                secure=True,
            )
            return response

        with (
            patch.object(
                ClubStorage,
                'save',
                side_effect=lambda name, content, max_length=None: name,
            ) as save_mock,
            patch.object(ClubStorage, 'delete') as delete_mock,
        ):
            first_response = upload_png()
            self.assertEqual(first_response.status_code, 200)
            self.user.profile.refresh_from_db()
            first_name = self.user.profile.avatar.name

            second_response = upload_png()
            self.assertEqual(second_response.status_code, 200)
            self.user.profile.refresh_from_db()
            second_name = self.user.profile.avatar.name

        self.assertNotEqual(first_name, second_name)
        self.assertEqual(save_mock.call_count, 2)
        delete_mock.assert_called_once_with(first_name)

    def test_department_members_visible_to_logged_in_users(self):
        from ..models import Department

        department = Department.objects.create(name='测试部门')
        member = User.objects.create_user(username='plain-member', password='test-password')
        UserProfile.objects.create(user=member, role='member', status='approved')
        self.client.force_login(member)

        response = self.client.get(
            reverse('clubs:get_department_members', args=[department.pk]),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], '测试部门')

    def test_department_members_requires_login(self):
        from ..models import Department

        department = Department.objects.create(name='测试部门')
        self.client.logout()

        response = self.client.get(
            reverse('clubs:get_department_members', args=[department.pk]),
            secure=True,
        )

        self.assertEqual(response.status_code, 302)

    def test_admin_room_add_rejects_invalid_capacity(self):
        staff = User.objects.create_user(username='audit-staff', password='test-password')
        UserProfile.objects.create(user=staff, role='staff', status='approved')
        self.client.force_login(staff)

        response = self.client.post(
            reverse('clubs:admin_room_add'),
            {
                'name': '测试房间',
                'capacity': 'not-a-number',
                'status': 'available',
            },
            secure=True,
        )

        self.assertRedirects(response, reverse('clubs:admin_room_add'), fetch_redirect_response=False)
        self.assertEqual(Room.objects.count(), 0)

    @override_settings(USE_X_FORWARDED_FOR=True)
    def test_login_lockout_uses_forwarded_for_ip(self):
        from ..views import auth as auth_views

        self.client.logout()
        login_url = reverse('clubs:login')
        fake_ip = '203.0.113.99'
        for _ in range(auth_views.MAX_LOGIN_ATTEMPTS):
            self.client.post(
                login_url,
                {'username': 'unknown-user-xyz', 'password': 'wrong-password'},
                HTTP_X_FORWARDED_FOR=fake_ip,
                secure=True,
            )

        response = self.client.post(
            login_url,
            {'username': 'unknown-user-xyz', 'password': 'wrong-password'},
            HTTP_X_FORWARDED_FOR=fake_ip,
            secure=True,
        )

        self.assertContains(response, '登录尝试过多')

    def test_login_lockout_ignores_forwarded_for_without_proxy(self):
        from ..views import auth as auth_views

        self.client.logout()
        login_url = reverse('clubs:login')
        for index in range(auth_views.MAX_LOGIN_ATTEMPTS):
            self.client.post(
                login_url,
                {'username': 'unknown-user-abc', 'password': 'wrong-password'},
                HTTP_X_FORWARDED_FOR=f'10.0.0.{index}',
                secure=True,
            )

        response = self.client.post(
            login_url,
            {'username': 'unknown-user-abc', 'password': 'wrong-password'},
            HTTP_X_FORWARDED_FOR='10.0.0.99',
            secure=True,
        )

        self.assertContains(response, '登录尝试过多')

    def test_build_external_url_respects_proxy_switch(self):
        from django.test import RequestFactory

        from ..views.core import _build_external_url

        request = RequestFactory().get('/some/path')
        request.META['HTTP_X_FORWARDED_PROTO'] = 'https'
        request.META['HTTP_X_FORWARDED_HOST'] = 'public.example.com'

        with override_settings(USE_X_FORWARDED_PROTO=False, USE_X_FORWARDED_HOST=False):
            url = _build_external_url(request, '/path')
            self.assertTrue(url.startswith('http://testserver'))

        with override_settings(USE_X_FORWARDED_PROTO=True, USE_X_FORWARDED_HOST=True):
            url = _build_external_url(request, '/path')
            parsed = urlparse(url)
            self.assertEqual(parsed.scheme, 'https')
            self.assertEqual(parsed.hostname, 'public.example.com')

    def test_office_preview_url_rejects_non_http_schemes(self):
        from django.core.files.base import ContentFile
        from django.test import RequestFactory

        from ..views.core import _office_preview_url
        from ..models import FormField, FormSubmission, FormUploadedFile

        channel = FormChannel.objects.create(
            name='预览测试通道',
            slug='preview-test',
            is_active=True,
            publish_status='published',
        )
        submission = FormSubmission.objects.create(
            channel=channel,
            club=Club.objects.create(name='预览测试社团', founded_date=date(2026, 1, 1)),
            submitter=self.user,
        )
        field = FormField.objects.create(channel=channel, field_key='f', label='附件', field_type='file')
        uploaded = FormUploadedFile.objects.create(
            submission=submission,
            field=field,
            file=ContentFile(b'docx-bytes', name='doc.docx'),
            original_name='doc.docx',
        )
        uploaded.file.name = 'file:///etc/passwd.docx'

        request = RequestFactory().get('/')
        self.assertEqual(_office_preview_url(request, uploaded), '')

    def test_storage_name_sanitization(self):
        from ..storage_backends import _sanitize_storage_name

        self.assertEqual(_sanitize_storage_name('file:///etc/passwd.docx'), 'etc/passwd.docx')
        self.assertEqual(_sanitize_storage_name('/abs/path/x.docx'), 'abs/path/x.docx')
        self.assertEqual(_sanitize_storage_name('form_submissions/abc/x.docx'), 'form_submissions/abc/x.docx')
        self.assertEqual(_sanitize_storage_name('a/../b.docx'), 'b.docx')
        self.assertEqual(_sanitize_storage_name(''), 'unnamed')

    def test_admin_can_change_third_party_cdn(self):
        response = self.client.post(
            reverse('clubs:site_settings'),
            {
                'form_type': 'cdn_settings',
                'third_party_cdn_base_url': 'https://mirrors.sustech.edu.cn/cdnjs/',
                'third_party_cdn_sri': json.dumps({
                    'chartjs': 'sha384-XcdcwHqIPULERb2yDEM4R0XaQKU3YnDsrTmjACBZyfdVVqjh6xQ4/DCMd7XLcA6Y',
                    'swiper_js': 'sha384-T6qkM4ANslBL/pKcwNUeB0bpsiI6pkXXzwrl7Avc6FXEC/UZaXAeBpZZ2zQ3Zbez',
                    'swiper_css': 'sha384-eKrJLy2KlZuvuza/yNmSyFUE2Qb5aehRlXikp6XUOxXVw5pOQBb5n1C0UOcCnAJb',
                    'cropper_js': 'sha384-jrOgQzBlDeUNdmQn3rUt/PZD+pdcRBdWd/HWRqRo+n2OR2QtGyjSaJC0GiCeH+ir',
                    'cropper_css': 'sha384-6LFfkTKLRlzFtgx8xsWyBdKGpcMMQTkv+dB7rAbugeJAu1Ym2q1Aji1cjHBG12Xh',
                }),
            },
            secure=True,
        )

        self.assertRedirects(response, reverse('clubs:site_settings'), fetch_redirect_response=False)
        self.config.refresh_from_db()
        self.assertEqual(
            self.config.third_party_cdn_base_url,
            'https://mirrors.sustech.edu.cn/cdnjs',
        )
        self.assertTrue(self.config.third_party_cdn_sri['chartjs'].startswith('sha384-'))

    def test_admin_can_change_site_name_and_homepage_title(self):
        response = self.client.post(
            reverse('clubs:site_settings'),
            {
                'form_type': 'site_info_settings',
                'site_name': '测试站点',
                'homepage_title': '测试首页标题',
                'homepage_subtitle': '测试首页副标题',
            },
            secure=True,
        )

        self.assertRedirects(response, reverse('clubs:site_settings'), fetch_redirect_response=False)
        self.config.refresh_from_db()
        self.assertEqual(self.config.site_name, '测试站点')
        self.assertEqual(self.config.homepage_title, '测试首页标题')
        self.assertEqual(self.config.homepage_subtitle, '测试首页副标题')

    def test_third_party_cdn_rejects_urls_with_query_parameters(self):
        original_url = self.config.third_party_cdn_base_url
        response = self.client.post(
            reverse('clubs:site_settings'),
            {
                'form_type': 'cdn_settings',
                'third_party_cdn_base_url': 'https://cdn.example.com?redirect=elsewhere',
            },
            secure=True,
        )

        self.assertRedirects(response, reverse('clubs:site_settings'), fetch_redirect_response=False)
        self.config.refresh_from_db()
        self.assertEqual(self.config.third_party_cdn_base_url, original_url)

    @patch('clubs.avatar_utils.cravatar_exists', return_value=True)
    def test_existing_cravatar_is_saved_and_selected(self, exists_mock):
        response = self.client.post(
            reverse('clubs:edit_profile'),
            {'action': 'use_cravatar', 'avatar_email': 'Avatar@Example.com'},
            secure=True,
        )

        self.assertRedirects(
            response,
            f"{reverse('clubs:edit_profile')}?tab=avatar",
            fetch_redirect_response=False,
        )
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.avatar_email, 'avatar@example.com')
        self.assertEqual(self.user.profile.avatar_source, 'cravatar')
        exists_mock.assert_called_once_with('avatar@example.com')

    @patch('clubs.avatar_utils.cravatar_exists', return_value=False)
    def test_missing_cravatar_keeps_current_selection(self, exists_mock):
        response = self.client.post(
            reverse('clubs:edit_profile'),
            {'action': 'use_cravatar', 'avatar_email': 'missing@example.com'},
            secure=True,
        )

        self.assertRedirects(
            response,
            f"{reverse('clubs:edit_profile')}?tab=avatar",
            fetch_redirect_response=False,
        )
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.avatar_email, '')
        self.assertEqual(self.user.profile.avatar_source, 'local')
        exists_mock.assert_called_once_with('missing@example.com')

    def test_user_can_switch_back_to_local(self):
        profile = self.user.profile
        profile.avatar_source = 'cravatar'
        profile.avatar_email = 'person@example.com'
        profile.save(update_fields=['avatar_source', 'avatar_email'])

        response = self.client.post(
            reverse('clubs:edit_profile'),
            {'action': 'use_local_avatar'},
            secure=True,
        )

        self.assertRedirects(
            response,
            f"{reverse('clubs:edit_profile')}?tab=avatar",
            fetch_redirect_response=False,
        )
        profile.refresh_from_db()
        self.assertEqual(profile.avatar_source, 'local')

    def test_local_avatar_response_has_immutable_browser_cache(self):
        with TemporaryDirectory() as media_root:
            avatar_path = Path(media_root, 'avatars', '2026', '08', 'avatar.jpg')
            avatar_path.parent.mkdir(parents=True)
            avatar_path.write_bytes(b'avatar-image')

            with self.settings(MEDIA_ROOT=media_root):
                response = self.client.get('/media/avatars/2026/08/avatar.jpg', secure=True)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.headers['Cache-Control'],
                'public, max-age=31536000, immutable',
            )


class StaffRegistrationReviewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='review-admin',
            email='',
            password='test-password',
        )
        UserProfile.objects.get_or_create(
            user=self.admin,
            defaults={'role': 'admin', 'status': 'approved'},
        )
        self.client.force_login(self.admin)

    @staticmethod
    def create_pending_staff(username):
        user = User.objects.create_user(username=username, password='test-password')
        UserProfile.objects.create(user=user, role='staff', status='pending')
        return user

    def test_review_accepts_current_decision_field(self):
        staff = self.create_pending_staff('pending-current')

        response = self.client.post(
            reverse('clubs:review_staff_registration', args=[staff.pk]),
            {'decision': 'approved'},
            secure=True,
        )

        self.assertRedirects(response, reverse('clubs:manage_users'), fetch_redirect_response=False)
        staff.profile.refresh_from_db()
        self.assertEqual(staff.profile.status, 'approved')

    def test_review_rejects_already_processed_submission(self):
        first_reviewer = self.create_pending_staff('reviewer-first')
        first_reviewer.profile.status = 'approved'
        first_reviewer.profile.save(update_fields=['status'])
        channel = FormChannel.objects.create(
            name='审核通道',
            slug='review-channel',
            is_active=True,
            publish_status='published',
        )
        club = Club.objects.create(name='审核社团', founded_date=date(2026, 1, 1))
        submission = FormSubmission.objects.create(
            channel=channel,
            club=club,
            submitter=first_reviewer,
            status='approved',
        )
        FormSubmissionReview.objects.create(
            submission=submission,
            reviewer=first_reviewer,
            status='approved',
            submission_attempt=1,
        )

        response = self.client.post(
            reverse('clubs:staff_review_form_submission', args=[submission.public_id]),
            {'decision': 'approved', 'comment': '重复审核'},
            secure=True,
        )

        self.assertRedirects(
            response,
            reverse('clubs:staff_audit_center', args=[submission.channel.slug]),
            fetch_redirect_response=False,
        )
        followed = self.client.get(response.url, secure=True)
        self.assertContains(followed, '无需重复审核')
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'approved')

    def test_user_management_shows_pending_review_count(self):
        self.create_pending_staff('pending-count')
        approved = self.create_pending_staff('approved-count')
        approved.profile.status = 'approved'
        approved.profile.save(update_fields=['status', 'updated_at'])

        response = self.client.get(reverse('clubs:manage_users'), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['pending_review_users'], 1)
        self.assertContains(response, '1 个待审核')
        self.assertContains(response, '?role=staff&amp;status=pending')

    def test_batch_delete_users(self):
        first = User.objects.create_user(username='batch-del-1', password='test-password')
        UserProfile.objects.create(user=first, role='member', status='approved')
        second = User.objects.create_user(username='batch-del-2', password='test-password')
        UserProfile.objects.create(user=second, role='member', status='approved')

        response = self.client.post(
            reverse('clubs:manage_users'),
            {'action': 'batch_delete', 'user_ids': f'{first.pk},{second.pk}'},
            secure=True,
        )

        self.assertRedirects(response, reverse('clubs:manage_users'), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk__in=[first.pk, second.pk]).exists())

    def test_batch_toggle_active_users(self):
        first = User.objects.create_user(username='batch-tog-1', password='test-password')
        UserProfile.objects.create(user=first, role='member', status='approved')
        second = User.objects.create_user(username='batch-tog-2', password='test-password')
        UserProfile.objects.create(user=second, role='member', status='approved')

        self.client.post(
            reverse('clubs:manage_users'),
            {'action': 'batch_disable', 'user_ids': f'{first.pk},{second.pk}'},
            secure=True,
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertFalse(second.is_active)

        self.client.post(
            reverse('clubs:manage_users'),
            {'action': 'batch_enable', 'user_ids': f'{first.pk},{second.pk}'},
            secure=True,
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.is_active)
        self.assertTrue(second.is_active)

    def test_batch_delete_skips_superuser_and_self(self):
        target = User.objects.create_user(username='batch-skip-1', password='test-password')
        UserProfile.objects.create(user=target, role='member', status='approved')

        self.client.post(
            reverse('clubs:manage_users'),
            {'action': 'batch_delete', 'user_ids': f'{target.pk},{self.admin.pk}'},
            secure=True,
        )

        self.assertFalse(User.objects.filter(pk=target.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_manage_announcements_page_and_toggle(self):
        announcement = Announcement.objects.create(
            title='测试公告',
            content='公告内容',
            status='draft',
            created_by=self.admin,
        )

        response = self.client.get(reverse('clubs:manage_announcements'), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '测试公告')

        self.client.post(
            reverse('clubs:toggle_announcement_status', args=[announcement.pk]),
            secure=True,
        )
        announcement.refresh_from_db()
        self.assertEqual(announcement.status, 'published')

    def test_time_slot_import_template_and_import(self):
        template_response = self.client.get(reverse('clubs:download_time_slot_import_template'), secure=True)
        self.assertEqual(template_response.status_code, 200)
        self.assertContains(template_response, '显示名称')

        csv_content = '显示名称,开始时间,结束时间,状态\n第1-2节,08:15,09:55,启用\n午休,11:40,13:00,启用\n'
        upload = SimpleUploadedFile(
            'time_slots.csv',
            csv_content.encode('utf-8-sig'),
            content_type='text/csv',
        )
        response = self.client.post(
            reverse('clubs:import_time_slots_csv'),
            {'csv_file': upload},
            HTTP_ACCEPT='application/json',
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(TimeSlot.objects.filter(label='第1-2节').count(), 1)
        self.assertEqual(TimeSlot.objects.filter(label='午休').count(), 1)

    def test_weekly_export_uses_monday_and_configured_slots(self):
        from openpyxl import load_workbook

        room = Room.objects.create(name='导出测试房间', capacity=10)
        TimeSlot.objects.create(label='自定义时段', start_time=time(9, 0), end_time=time(10, 0), is_active=True)

        response = self.client.get(
            reverse('clubs:export_room_bookings_weekly'),
            {'room_id': room.pk, 'week_start': '2026-08-05'},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.content))
        worksheet = workbook.active
        self.assertIn('2026年08月03日', worksheet['A1'].value)
        labels = [worksheet.cell(row=row, column=1).value for row in range(3, worksheet.max_row + 1)]
        self.assertTrue(any(label and '自定义时段' in label for label in labels))
        self.assertTrue(any(label and '09:00-10:00' in label for label in labels))

    def test_save_form_channel_accepts_multiple_example_files(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        channel = FormChannel.objects.create(
            name='示例通道',
            slug='example-channel',
            is_active=True,
            publish_status='draft',
        )

        def make_docx(name):
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as archive:
                archive.writestr('[Content_Types].xml', '<Types/>')
            return SimpleUploadedFile(
                name,
                zip_buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            )

        response = self.client.post(
            reverse('clubs:edit_form_channel', args=[channel.pk]),
            {
                'name': '示例通道',
                'slug': 'example-channel',
                'icon': 'description',
                'order': '0',
                'required_approval_count': '1',
                'publish_status': 'draft',
                'example_files': [make_docx('a.docx'), make_docx('b.docx')],
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ChannelExampleFile.objects.filter(channel=channel).count(), 2)


class BookingServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('booking-admin', '', 'password')
        self.room = Room.objects.create(name='事务测试房间', capacity=20)

    def create_booking(self, start=time(9), end=time(10)):
        return create_room_booking(
            room_id=self.room.pk,
            user=self.user,
            club=None,
            booking_date=date(2026, 8, 10),
            start_time=start,
            end_time=end,
            purpose='测试预约',
            participant_count=5,
            contact_phone='13800000000',
        )

    def test_overlapping_booking_is_rejected(self):
        self.create_booking()

        with self.assertRaises(BookingConflictError):
            self.create_booking(time(9, 30), time(10, 30))

        self.assertEqual(RoomBooking.objects.count(), 1)

    def test_adjacent_booking_is_allowed(self):
        self.create_booking()
        self.create_booking(time(10), time(11))

        self.assertEqual(RoomBooking.objects.count(), 2)

    def test_database_rejects_non_positive_participants(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            RoomBooking.objects.create(
                room=self.room,
                user=self.user,
                booking_date=date(2026, 8, 10),
                start_time=time(9),
                end_time=time(10),
                purpose='无效预约',
                participant_count=0,
                contact_phone='13800000000',
            )

    def test_booking_cancellation_requires_confirmed_post(self):
        booking = self.create_booking()
        self.client.force_login(self.user)

        confirmation = self.client.get(
            reverse('clubs:delete_room_booking', args=[booking.pk]),
            secure=True,
        )
        self.assertEqual(confirmation.status_code, 200)
        self.assertTrue(RoomBooking.objects.filter(pk=booking.pk).exists())

        response = self.client.post(
            reverse('clubs:delete_room_booking', args=[booking.pk]),
            secure=True,
        )
        self.assertRedirects(
            response,
            reverse('clubs:my_room_bookings'),
            fetch_redirect_response=False,
        )
        self.assertFalse(RoomBooking.objects.filter(pk=booking.pk).exists())


class RegistrationTokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('token-admin', '', 'password')
        self.club = Club.objects.create(
            name='令牌测试社团',
            founded_date=date(2020, 1, 1),
        )
        self.token = RegistrationToken.create_for_club(
            club=self.club,
            created_by=self.user,
            minutes=10,
            max_uses=1,
        )

    def test_last_token_use_cannot_be_consumed_twice(self):
        self.token.mark_used()

        with self.assertRaises(ValidationError):
            self.token.mark_used()

        self.token.refresh_from_db()
        self.assertEqual(self.token.used_count, 1)

    def test_generated_tokens_are_unique_and_url_safe(self):
        first = RegistrationToken.generate_code()
        second = RegistrationToken.generate_code()

        self.assertNotEqual(first, second)
        self.assertGreaterEqual(len(first), 32)
        self.assertRegex(first, r'^[A-Za-z0-9_-]+$')

    def test_registration_and_last_use_are_one_transaction(self):
        registered_user, _ = register_member_with_token(
            token_id=self.token.pk,
            user=None,
            existing_account=False,
            username='new-member',
            password='member-password',
            email='member@example.com',
            profile_data={
                'real_name': '新社员',
                'student_id': '20260001',
                'gender': 'other',
                'college': '测试学院',
                'class_name': '测试班',
                'phone': '13800000000',
                'qq': '',
                'wechat': 'new-member',
            },
        )

        self.assertTrue(ClubMember.objects.filter(
            club=self.club,
            user_profile=registered_user.profile,
        ).exists())
        self.token.refresh_from_db()
        self.assertEqual(self.token.used_count, 1)

        with self.assertRaises(RegistrationTokenUnavailable):
            register_member_with_token(
                token_id=self.token.pk,
                user=None,
                existing_account=False,
                username='should-not-exist',
                password='member-password',
                email='unused@example.com',
                profile_data={
                    'real_name': '不会创建',
                    'student_id': '20260002',
                    'gender': 'other',
                    'college': '测试学院',
                    'class_name': '测试班',
                    'phone': '13800000001',
                    'qq': '',
                    'wechat': 'unused',
                },
            )

        self.assertFalse(User.objects.filter(username='should-not-exist').exists())


class SecurityInfrastructureTests(TestCase):
    def test_service_credentials_are_encrypted_at_rest(self):
        config = SMTPConfig.objects.create(
            provider='custom',
            smtp_host='smtp.example.com',
            smtp_port=587,
            sender_email='sender@example.com',
            sender_password='plain-secret',
        )
        with connection.cursor() as cursor:
            cursor.execute('SELECT sender_password FROM clubs_smtpconfig WHERE id = %s', [config.pk])
            stored = cursor.fetchone()[0]

        self.assertNotEqual(stored, 'plain-secret')
        self.assertTrue(stored.startswith('enc:v1:'))
        config.refresh_from_db()
        self.assertEqual(config.sender_password, 'plain-secret')

    def test_upload_signature_must_match_extension(self):
        upload = SimpleUploadedFile('fake.png', b'not-a-png', content_type='image/png')

        error = validate_upload(upload, field_name='图片', allowed_extensions={'.png'})

        self.assertIn('实际内容', error)

    def test_zip_path_traversal_is_rejected(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('../escape.txt', 'unsafe')
        upload = SimpleUploadedFile('unsafe.zip', buffer.getvalue(), content_type='application/zip')

        error = validate_upload(upload, field_name='压缩包', allowed_extensions={'.zip'})

        self.assertIn('不安全的路径', error)

    def test_generic_download_requires_staff_role(self):
        User.objects.create_superuser(
            username='download-admin',
            email='',
            password='test-password',
        )
        member = User.objects.create_user('ordinary-member', password='password')
        self.client.force_login(member)

        response = self.client.get(
            reverse('clubs:download_file'),
            {'file_path': 'anything.pdf'},
            secure=True,
        )

        self.assertRedirects(response, reverse('clubs:index'), fetch_redirect_response=False)


class StaticPageSmokeTests(TestCase):
    """Render every named, parameter-free page and fail on server errors."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='page-smoke-admin',
            email='admin@example.com',
            password='test-password',
        )

    def _named_static_patterns(self, patterns=None, namespace=''):
        patterns = patterns or get_resolver().url_patterns
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                child_namespace = namespace
                if pattern.namespace:
                    child_namespace = f'{namespace}:{pattern.namespace}' if namespace else pattern.namespace
                yield from self._named_static_patterns(pattern.url_patterns, child_namespace)
            elif isinstance(pattern, URLPattern) and pattern.name and '<' not in str(pattern.pattern):
                name = f'{namespace}:{pattern.name}' if namespace else pattern.name
                yield name

    def test_named_static_pages_do_not_raise_server_errors(self):
        excluded = {'admin:index', 'clubs:oobe_setup'}
        for name in sorted(set(self._named_static_patterns())):
            if name in excluded:
                continue
            with self.subTest(route=name):
                self.client.force_login(self.admin)
                response = self.client.get(reverse(name), follow=False, secure=True)
                self.assertLess(response.status_code, 500, f'{name} returned {response.status_code}')

    def test_form_channel_admin_exposes_status_overview_and_search(self):
        initial_count = FormChannel.objects.count()
        FormChannel.objects.create(
            name='界面测试通道',
            slug='ui-test-channel',
            publish_status='published',
            is_active=True,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse('clubs:manage_form_channels'), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['channel_summary']['total'], initial_count + 1)
        self.assertGreaterEqual(response.context['channel_summary']['published'], 1)
        self.assertContains(response, 'js-channel-search')
        self.assertContains(response, 'rail-search-control')
        self.assertContains(response, 'aria-label="搜索通道名称或标识"')
        self.assertContains(response, '通道状态概览')

    def test_new_form_channel_page_exposes_material_icon_preview_and_reference(self):
        self.client.force_login(self.admin)

        response = self.client.get(f"{reverse('clubs:manage_form_channels')}?new=1", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js-material-icon-preview')
        self.assertContains(response, 'js-material-icon-input')
        self.assertContains(response, '正在预览：description')
        self.assertContains(response, 'https://mui.com/material-ui/material-icons/')

    def test_staff_management_query_count_does_not_scale_per_club(self):
        profile = self.admin.profile
        profile.role = 'admin'
        profile.save(update_fields=['role'])
        for action, slug in [('annual_review', 'query-annual'), ('club_registration', 'query-registration')]:
            channel = FormChannel.objects.create(
                name=slug,
                slug=slug,
                builtin_action=action,
                cycle_type='count',
                submission_policy='once_per_cycle',
                allow_staff_toggle=True,
            )
            FormCycle.objects.create(channel=channel, name='性能测试周期', created_by=self.admin)

        def add_clubs(start, stop):
            for index in range(start, stop):
                president = User.objects.create(username=f'query-president-{index}')
                president_profile = UserProfile.objects.create(
                    user=president,
                    role='president',
                    real_name=f'性能社长 {index:02d}',
                )
                club = Club.objects.create(
                    name=f'查询性能社团 {index:02d}',
                    description='查询性能测试',
                    founded_date=date.today(),
                    members_count=1,
                )
                Officer.objects.create(
                    club=club,
                    user_profile=president_profile,
                    position='president',
                    appointed_date=date.today(),
                )
                StaffClubRelation.objects.create(staff=profile, club=club)

        def request_query_count():
            cache.clear()
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(
                    f"{reverse('clubs:staff_management')}?q=&page=1",
                    secure=True,
                )
            self.assertEqual(response.status_code, 200)
            return len(queries)

        self.client.force_login(self.admin)
        add_clubs(0, 5)
        small_dataset_queries = request_query_count()
        add_clubs(5, 25)
        large_dataset_queries = request_query_count()

        self.assertLessEqual(large_dataset_queries, small_dataset_queries)

    def test_user_dashboard_bulk_loads_clubs_channels_and_latest_submissions(self):
        profile = self.admin.profile
        profile.role = 'admin'
        profile.save(update_fields=['role'])
        channels = [
            FormChannel.objects.create(
                name=f'仪表板通道 {index}',
                slug=f'dashboard-channel-{index}',
                publish_status='published',
                submission_policy='once_total',
                is_active=True,
            )
            for index in range(5)
        ]
        def add_clubs(start, stop):
            clubs = []
            for index in range(start, stop):
                club = Club.objects.create(
                    name=f'仪表板社团 {index:02d}',
                    founded_date=date.today(),
                    members_count=20,
                )
                Officer.objects.create(
                    club=club,
                    user_profile=profile,
                    position='president',
                    appointed_date=date.today(),
                )
                StaffClubRelation.objects.create(staff=profile, club=club)
                clubs.append(club)
            FormSubmission.objects.bulk_create([
                FormSubmission(channel=channel, club=club, submitter=self.admin)
                for club in clubs
                for channel in channels
            ])

        def request_query_count():
            cache.clear()
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(reverse('clubs:user_dashboard'), secure=True)
            self.assertEqual(response.status_code, 200)
            return response, len(queries)

        self.client.force_login(self.admin)
        session = self.client.session
        session['active_identity'] = 'president'
        session.save()
        add_clubs(0, 5)
        _, small_dataset_queries = request_query_count()
        add_clubs(5, 20)
        response, large_dataset_queries = request_query_count()

        self.assertContains(response, '仪表板社团 19')
        self.assertLessEqual(large_dataset_queries, small_dataset_queries)

    def test_submission_display_title_uses_prefetched_values_without_queries(self):
        channel = FormChannel.objects.create(name='标题预取', slug='title-prefetch')
        field = FormField.objects.create(
            channel=channel,
            label='标题',
            field_key='title',
            field_type='text',
        )
        club = Club.objects.create(
            name='标题预取社团',
            founded_date=date.today(),
        )
        submission = FormSubmission.objects.create(
            channel=channel,
            club=club,
            submitter=self.admin,
        )
        FormFieldValue.objects.create(
            submission=submission,
            field=field,
            value_text='无需额外查询的标题',
        )
        loaded = FormSubmission.objects.prefetch_related('values__field').get(pk=submission.pk)

        with CaptureQueriesContext(connection) as queries:
            title = loaded.display_title

        self.assertEqual(title, '无需额外查询的标题')
        self.assertEqual(len(queries), 0)

    def test_my_room_bookings_is_paginated(self):
        room = Room.objects.create(name='分页测试房间')
        RoomBooking.objects.bulk_create([
            RoomBooking(
                room=room,
                user=self.admin,
                booking_date=date.today(),
                start_time=time(8, 0),
                end_time=time(9, 0),
                purpose=f'分页预约 {index:02d}',
                participant_count=1,
                contact_phone='13800000000',
            )
            for index in range(25)
        ])
        self.client.force_login(self.admin)

        response = self.client.get(f"{reverse('clubs:my_room_bookings')}?page=2", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['bookings']), 1)
        self.assertContains(response, '预约记录分页')
        self.assertContains(response, '第 2 / 2 页，共 25 条')


class DynamicFormReReviewTests(TestCase):
    """已完成审核请求的重新审核与修改自己的审核结果。"""

    def setUp(self):
        self.admin = User.objects.create_superuser('re-admin', '', 'test-password')
        UserProfile.objects.get_or_create(
            user=self.admin,
            defaults={'role': 'admin', 'status': 'approved'},
        )
        self.reviewer = User.objects.create_user('re-reviewer', password='test-password')
        UserProfile.objects.create(user=self.reviewer, role='staff', status='approved')
        self.submitter = User.objects.create_user('re-submitter', password='test-password')
        UserProfile.objects.create(user=self.submitter, role='member', status='approved')
        self.club = Club.objects.create(name='重审社团', founded_date=date(2026, 1, 1))
        self.channel = FormChannel.objects.create(
            name='普通审核通道',
            slug='plain-rereview',
            is_active=True,
            publish_status='published',
            required_approval_count=2,
        )

    def make_rejected_submission(self, attempt=1):
        submission = FormSubmission.objects.create(
            channel=self.channel,
            club=self.club,
            submitter=self.submitter,
            status='rejected',
            resubmission_count=attempt,
            review_comment='原打回意见',
        )
        FormSubmissionReview.objects.create(
            submission=submission,
            reviewer=self.reviewer,
            status='rejected',
            comment='原审核意见',
            submission_attempt=attempt,
        )
        return submission

    def test_admin_reenter_starts_new_review_round_keeping_history(self):
        submission = self.make_rejected_submission()
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('clubs:staff_review_form_submission', args=[submission.public_id]),
            {'action': 'reenter', 'comment': '重新审核'},
            secure=True,
        )

        self.assertRedirects(
            response,
            reverse('clubs:staff_audit_center', args=[self.channel.slug]),
            fetch_redirect_response=False,
        )
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'pending')
        self.assertEqual(submission.resubmission_count, 2)
        self.assertIsNone(submission.reviewer)
        self.assertIsNone(submission.reviewed_at)
        self.assertEqual(submission.review_comment, '')
        # 原审核记录保留在旧轮次，新轮次无任何投票
        self.assertEqual(submission.reviews.count(), 1)
        self.assertEqual(submission.reviews.first().submission_attempt, 1)
        self.assertFalse(submission.reviews.filter(submission_attempt=2).exists())
        self.assertEqual(submission.reviewer_count, 0)

    def test_admin_reenter_approved_submission_allowed(self):
        submission = self.make_rejected_submission()
        submission.status = 'approved'
        submission.review_comment = '已通过'
        submission.save(update_fields=['status', 'review_comment'])
        FormSubmissionReview.objects.filter(submission=submission).update(status='approved')
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('clubs:staff_review_form_submission', args=[submission.public_id]),
            {'action': 'reenter'},
            secure=True,
        )

        self.assertRedirects(
            response,
            reverse('clubs:staff_audit_center', args=[self.channel.slug]),
            fetch_redirect_response=False,
        )
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'pending')
        self.assertEqual(submission.resubmission_count, 2)

    def test_non_admin_cannot_reenter(self):
        submission = self.make_rejected_submission()
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('clubs:staff_review_form_submission', args=[submission.public_id]),
            {'action': 'reenter'},
            secure=True,
        )
        followed = self.client.get(response.url, secure=True)
        self.assertContains(followed, '仅管理员可以重新审核')
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'rejected')
        self.assertEqual(submission.resubmission_count, 1)

    def test_reenter_rejected_on_pending_submission(self):
        submission = FormSubmission.objects.create(
            channel=self.channel,
            club=self.club,
            submitter=self.submitter,
            status='pending',
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('clubs:staff_review_form_submission', args=[submission.public_id]),
            {'action': 'reenter'},
            secure=True,
        )
        followed = self.client.get(response.url, secure=True)
        self.assertContains(followed, '仅已完成审核的请求可以重新审核')

    def test_business_action_channel_blocks_override_and_reenter(self):
        channel = FormChannel.objects.create(
            name='业务动作通道',
            slug='biz-rereview',
            builtin_action='club_application',
            is_active=True,
            publish_status='published',
        )
        submission = FormSubmission.objects.create(
            channel=channel,
            club=self.club,
            submitter=self.submitter,
            status='approved',
        )
        FormSubmissionReview.objects.create(
            submission=submission,
            reviewer=self.reviewer,
            status='approved',
            submission_attempt=1,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('clubs:staff_review_form_submission', args=[submission.public_id]),
            {'action': 'reenter'},
            secure=True,
        )
        self.assertContains(self.client.get(response.url, secure=True), '不允许重新审核')
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'approved')

        response = self.client.post(
            reverse('clubs:staff_review_form_submission', args=[submission.public_id]),
            {'action': 'direct_reject'},
            secure=True,
        )
        self.assertContains(self.client.get(response.url, secure=True), '不允许覆盖修改')
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'approved')

    def test_direct_modify_only_changes_own_review(self):
        second_reviewer = User.objects.create_user('re-reviewer-2', password='test-password')
        UserProfile.objects.create(user=second_reviewer, role='staff', status='approved')
        submission = self.make_rejected_submission()
        FormSubmissionReview.objects.create(
            submission=submission,
            reviewer=second_reviewer,
            status='rejected',
            submission_attempt=1,
        )
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('clubs:staff_review_form_submission', args=[submission.public_id]),
            {'action': 'direct_approve', 'comment': '改为通过'},
            secure=True,
        )

        self.assertRedirects(
            response,
            reverse('clubs:staff_review_form_submission', args=[submission.public_id]),
            fetch_redirect_response=False,
        )
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'approved')
        self.assertEqual(
            submission.reviews.get(reviewer=self.reviewer).status,
            'approved',
        )
        self.assertEqual(
            submission.reviews.get(reviewer=second_reviewer).status,
            'rejected',
        )
        # 审核人数不因修改而增加
        self.assertEqual(submission.reviewer_count, 2)
        self.assertEqual(submission.reviews.count(), 2)

    def test_reviewer_direct_modify_requires_participation(self):
        outsider = User.objects.create_user('re-outsider', password='test-password')
        UserProfile.objects.create(user=outsider, role='staff', status='approved')
        submission = self.make_rejected_submission()
        self.client.force_login(outsider)

        response = self.client.post(
            reverse('clubs:staff_review_form_submission', args=[submission.public_id]),
            {'action': 'direct_approve'},
            secure=True,
        )
        self.assertContains(self.client.get(response.url, secure=True), '仅参与本次审核的审核人或管理员可以修改审核结果')
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'rejected')

    def test_review_page_context_permissions(self):
        submission = self.make_rejected_submission()
        self.client.force_login(self.reviewer)
        response = self.client.get(
            reverse('clubs:staff_review_form_submission', args=[submission.public_id]),
            secure=True,
        )
        self.assertTrue(response.context['can_edit_own_review'])
        self.assertFalse(response.context['can_reenter_review'])

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('clubs:staff_review_form_submission', args=[submission.public_id]),
            secure=True,
        )
        self.assertTrue(response.context['can_edit_own_review'])
        self.assertTrue(response.context['can_reenter_review'])


class DepartmentEditAndProfileRobustnessTests(TestCase):
    """审计修复回归测试：非法表单参数不产生 500，缺失 profile 的用户操作有兜底。"""

    def setUp(self):
        # 首启引导中间件要求系统存在管理员，否则所有请求都会重定向到 /oobe/
        self.admin = User.objects.create_superuser(
            username='robustness-admin',
            email='',
            password='test-password',
        )

    def _make_staff(self, username='dept-edit-staff'):
        staff = User.objects.create_user(username=username, password='test-password')
        UserProfile.objects.create(user=staff, role='staff', status='approved')
        self.client.force_login(staff)
        return staff

    def test_edit_department_rejects_non_numeric_order(self):
        from ..models import Department

        self._make_staff()
        dept = Department.objects.create(name='原部门', order=2)
        response = self.client.post(
            reverse('clubs:edit_department', args=[dept.pk]),
            {'name': '新部门', 'order': 'abc'},
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '排序顺序必须是大于或等于 0 的整数')
        dept.refresh_from_db()
        self.assertEqual(dept.name, '原部门')
        self.assertEqual(dept.order, 2)

    def test_edit_department_rejects_empty_name(self):
        from ..models import Department

        self._make_staff()
        dept = Department.objects.create(name='原部门')
        response = self.client.post(
            reverse('clubs:edit_department', args=[dept.pk]),
            {'name': '   ', 'order': '3'},
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '部门名称不能为空')
        dept.refresh_from_db()
        self.assertEqual(dept.name, '原部门')

    def test_edit_department_accepts_valid_update(self):
        from ..models import Department

        self._make_staff()
        dept = Department.objects.create(name='原部门', order=1)
        response = self.client.post(
            reverse('clubs:edit_department', args=[dept.pk]),
            {'name': '新部门', 'order': '5'},
            secure=True,
        )
        self.assertRedirects(
            response,
            reverse('clubs:manage_departments'),
            fetch_redirect_response=False,
        )
        dept.refresh_from_db()
        self.assertEqual(dept.name, '新部门')
        self.assertEqual(dept.order, 5)

    def test_edit_profile_without_profile_redirects(self):
        user = User.objects.create_user(username='no-profile-user', password='test-password')
        self.client.force_login(user)
        response = self.client.post(
            reverse('clubs:edit_profile'),
            {'action': 'update_info'},
            secure=True,
        )
        self.assertRedirects(
            response,
            reverse('clubs:index'),
            fetch_redirect_response=False,
        )
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_delete_account_without_profile_redirects(self):
        user = User.objects.create_user(username='no-profile-del', password='test-password')
        self.client.force_login(user)
        response = self.client.post(
            reverse('clubs:delete_account'),
            {'confirm_username': user.username},
            secure=True,
        )
        self.assertRedirects(
            response,
            reverse('clubs:index'),
            fetch_redirect_response=False,
        )
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_room_booking_str_without_profile(self):
        from ..models import Room, RoomBooking

        user = User.objects.create_user(username='booking-no-profile', password='test-password')
        room = Room.objects.create(name='测试房间', capacity=10)
        booking = RoomBooking.objects.create(
            room=room,
            user=user,
            booking_date=date(2026, 8, 6),
            start_time=time(9, 0),
            end_time=time(10, 0),
            purpose='测试',
            participant_count=2,
            contact_phone='13800000000',
        )
        self.assertIn('booking-no-profile', str(booking))
