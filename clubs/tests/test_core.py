import json
import zipfile
from datetime import date, time
from hashlib import md5
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from ..avatar_utils import clear_avatar_settings_cache, get_profile_avatar_url
from ..models import (
    Club,
    ClubMember,
    FormChannel,
    FormCycle,
    FormField,
    FormFieldValue,
    FormSubmission,
    Officer,
    RegistrationToken,
    Room,
    RoomBooking,
    SiteSettings,
    SMTPConfig,
    StaffClubRelation,
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
        self.assertTrue(self.token.is_used)

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
