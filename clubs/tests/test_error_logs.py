"""错误页（404/500）、求助通知与 BUG 日志管理后台测试。"""

from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from ..models import ErrorLog, SMTPConfig, SiteSettings
from ..views.errors import _error_help_token, handler404, handler500


def make_smtp_config(**kwargs):
    defaults = {
        'provider': 'custom',
        'smtp_host': 'smtp.test.com',
        'smtp_port': 587,
        'sender_email': 'noreply@test.com',
        'sender_password': 'secret',
        'use_tls': True,
        'is_active': True,
        'help_recipient_email': 'ops@example.com',
    }
    defaults.update(kwargs)
    return SMTPConfig.objects.create(**defaults)


def enable_site_error_help(enabled=True):
    """开启/关闭站点级错误页求助开关（不依赖 SMTP 配置）。"""
    settings = SiteSettings.get_settings()
    settings.error_help_enabled = enabled
    settings.save(update_fields=['error_help_enabled'])
    return settings


class ErrorHandlerTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.factory = RequestFactory()
        # 创建管理员以避免 InitialSetupMiddleware 将请求重定向到 OOBE。
        self.admin = User.objects.create_superuser(
            username='err-admin',
            email='admin@example.com',
            password='test-password',
        )
        self.admin.profile.real_name = '管理员'
        self.admin.profile.save(update_fields=['real_name'])

    def _request(self, path='/test/'):
        request = self.factory.get(path)
        request.user = AnonymousUser()
        return request

    def test_handler404_does_not_create_error_log(self):
        request = self._request('/missing/page/')
        request.META['HTTP_REFERER'] = 'https://example.com/from/'
        response = handler404(request)
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, '页面走丢了', status_code=404)
        self.assertEqual(ErrorLog.objects.count(), 0)

    def test_handler500_creates_error_log_and_renders_page(self):
        request = self._request('/broken/page/')
        request.META['HTTP_REFERER'] = 'https://example.com/source/'
        request.META['HTTP_USER_AGENT'] = 'test-agent'
        response = handler500(request, ValueError('boom'))
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, '服务器开小差了', status_code=500)
        log = ErrorLog.objects.get()
        self.assertEqual(log.status_code, 500)
        self.assertEqual(log.path, '/broken/page/')
        self.assertEqual(log.referer, 'https://example.com/source/')
        self.assertEqual(log.exception_name, 'ValueError')
        self.assertIn('boom', log.exception_message)
        self.assertFalse(log.help_requested)

    def test_handler500_records_exception_from_exc_info_when_not_passed(self):
        """生产环境普通 500 不传异常对象，需从 sys.exc_info 兜底取回。"""
        request = self._request('/broken/page/')
        try:
            raise KeyError('missing-key')
        except KeyError:
            response = handler500(request)
        self.assertEqual(response.status_code, 500)
        log = ErrorLog.objects.get()
        self.assertEqual(log.exception_name, 'KeyError')
        self.assertIn('missing-key', log.exception_message)
        self.assertIn('KeyError', log.exception_message)

    def test_handler500_stores_full_traceback_in_log(self):
        request = self._request('/broken/page/')
        try:
            raise ValueError('detail-message')
        except ValueError:
            handler500(request)
        log = ErrorLog.objects.get()
        self.assertIn('detail-message', log.exception_message)
        self.assertIn('test_error_logs.py', log.exception_message)

    @override_settings(USE_X_FORWARDED_FOR=True)
    def test_handler500_records_leftmost_forwarded_ip(self):
        request = self._request('/broken/page/')
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.5, 104.16.1.1, 10.0.0.1'
        handler500(request, ValueError('boom'))
        log = ErrorLog.objects.get()
        self.assertEqual(log.ip, '203.0.113.5')

    def test_error_page_help_button_controlled_by_site_switch(self):
        # 开关开启时，未配置 SMTP 也显示求助按钮。
        enable_site_error_help(True)
        request = self._request('/missing/page/')
        response = handler404(request)
        self.assertContains(response, '请求帮助', status_code=404)

        enable_site_error_help(False)
        response = handler404(request)
        self.assertNotContains(response, '请求帮助', status_code=404)

    def test_help_request_rejected_when_switch_disabled(self):
        make_smtp_config()
        enable_site_error_help(False)
        with patch('clubs.views.errors.send_email_with_config') as send_mock:
            response = self.client.post(
                reverse('clubs:error_help_request'),
                {
                    'error_help_token': _error_help_token(500, '/broken/page/'),
                    'error_type': '500',
                    'error_path': '/broken/page/',
                    'contact_email': 'user@example.com',
                },
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()['success'])
        self.assertEqual(ErrorLog.objects.count(), 0)
        send_mock.assert_not_called()

    def test_help_request_updates_log_and_sends_email(self):
        make_smtp_config()
        enable_site_error_help(True)
        request = self._request('/broken/page/')
        handler500(request, RuntimeError('bad'))
        log = ErrorLog.objects.get()

        with patch('clubs.views.errors.send_email_with_config') as send_mock:
            response = self.client.post(
                reverse('clubs:error_help_request'),
                {
                    'error_help_token': _error_help_token(500, '/broken/page/', log.pk),
                    'error_log_id': log.pk,
                    'error_type': '500',
                    'error_path': '/broken/page/',
                    'contact_email': 'user@example.com',
                    'note': '麻烦看一下',
                },
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        log.refresh_from_db()
        self.assertTrue(log.help_requested)
        self.assertEqual(log.help_email, 'user@example.com')
        self.assertEqual(log.help_note, '麻烦看一下')
        send_mock.assert_called_once()
        self.assertEqual(send_mock.call_args.kwargs['to_email'], 'ops@example.com')
        self.assertIn('用户请求帮助', send_mock.call_args.kwargs['subject'])

    def test_help_request_cannot_modify_log_without_its_signed_token(self):
        enable_site_error_help(True)
        log = ErrorLog.objects.create(status_code=500, path='/victim/')

        response = self.client.post(
            reverse('clubs:error_help_request'),
            {
                'error_log_id': log.pk,
                'contact_email': 'attacker@example.com',
                'note': 'overwrite',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 403)
        log.refresh_from_db()
        self.assertFalse(log.help_requested)
        self.assertEqual(log.help_email, '')

    def test_help_request_without_log_creates_record_for_404(self):
        make_smtp_config()
        enable_site_error_help(True)
        with patch('clubs.views.errors.send_email_with_config') as send_mock:
            response = self.client.post(
                reverse('clubs:error_help_request'),
                {
                    'error_help_token': _error_help_token(404, '/lost/page/'),
                    'error_type': '404',
                    'error_path': '/lost/page/',
                    'contact_email': 'helper@example.com',
                },
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        self.assertTrue(response.json()['success'])
        log = ErrorLog.objects.get()
        self.assertEqual(log.status_code, 404)
        self.assertTrue(log.help_requested)
        self.assertEqual(log.path, '/lost/page/')
        self.assertEqual(log.help_email, 'helper@example.com')
        self.assertEqual(send_mock.call_count, 1)

    def test_help_request_works_without_smtp_config(self):
        # 未配置 SMTP 时求助仍然有效：记录 BUG 日志，但不发邮件。
        enable_site_error_help(True)
        with patch('clubs.views.errors.send_email_with_config') as send_mock:
            response = self.client.post(
                reverse('clubs:error_help_request'),
                {
                    'error_help_token': _error_help_token(500, '/broken/page/'),
                    'error_type': '500',
                    'error_path': '/broken/page/',
                    'contact_email': 'user@example.com',
                    'note': '没有 SMTP 也要能求助',
                },
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        log = ErrorLog.objects.get()
        self.assertTrue(log.help_requested)
        self.assertEqual(log.path, '/broken/page/')
        self.assertEqual(log.help_email, 'user@example.com')
        self.assertEqual(log.help_note, '没有 SMTP 也要能求助')
        send_mock.assert_not_called()


class BugLogAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='bug-admin',
            email='admin@example.com',
            password='test-password',
        )
        # 超级用户创建时信号已自动生成 admin 角色 profile，这里只需补齐实名。
        self.admin.profile.real_name = '管理员'
        self.admin.profile.save(update_fields=['real_name'])
        self.other = User.objects.create_user(
            username='normal-user',
            email='user@example.com',
            password='test-password',
        )

    def test_bug_logs_page_requires_admin(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse('clubs:manage_bug_logs'))
        self.assertRedirects(response, reverse('clubs:index'))

        self.client.force_login(self.admin)
        ErrorLog.objects.create(
            status_code=500,
            path='/boom/',
            exception_name='ValueError',
            exception_message='ValueError: boom',
        )
        response = self.client.get(reverse('clubs:manage_bug_logs'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BUG日志')
        self.assertContains(response, '/boom/')
        self.assertContains(response, 'ValueError')
        self.assertContains(response, 'boom')

    def test_dashboard_shows_help_request_alert_and_jump_button(self):
        self.client.force_login(self.admin)
        ErrorLog.objects.create(
            status_code=500,
            path='/broken/',
            exception_name='KeyError',
            exception_message='KeyError: missing-key',
            help_requested=True,
            user_identifier='tester',
        )
        response = self.client.get(reverse('clubs:admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BUG日志')
        self.assertContains(response, '有用户正在等待帮助')
        self.assertContains(response, 'tester')
        self.assertContains(response, 'missing-key')
        self.assertContains(response, reverse('clubs:manage_bug_logs'))

    def test_resolve_and_delete_actions(self):
        self.client.force_login(self.admin)
        log = ErrorLog.objects.create(status_code=500, path='/boom/')
        response = self.client.post(reverse('clubs:manage_bug_logs'), {
            'action': 'resolve',
            'log_id': log.pk,
        })
        self.assertRedirects(response, reverse('clubs:manage_bug_logs'))
        log.refresh_from_db()
        self.assertTrue(log.resolved)
        self.assertEqual(log.resolved_by, self.admin)

        response = self.client.post(reverse('clubs:manage_bug_logs'), {
            'action': 'delete',
            'log_id': log.pk,
        })
        self.assertRedirects(response, reverse('clubs:manage_bug_logs'))
        self.assertFalse(ErrorLog.objects.filter(pk=log.pk).exists())

    def test_smtp_config_page_saves_error_help_site_switch(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('clubs:manage_smtp_config'), {
            'action': 'error_help',
            'error_help_enabled': 'on',
        })
        self.assertRedirects(response, reverse('clubs:manage_smtp_config'))
        self.assertTrue(SiteSettings.get_settings().error_help_enabled)

        get_response = self.client.get(reverse('clubs:manage_smtp_config'))
        self.assertContains(get_response, '错误页求助')
        self.assertContains(get_response, 'error_help_enabled')
