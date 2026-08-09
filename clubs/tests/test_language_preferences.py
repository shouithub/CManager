"""用户首选语言 / 全站默认语言相关的多语言行为测试。"""

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from ..models import PREFERRED_LANGUAGE_CHOICES, SiteSettings, UserProfile


class SiteDefaultLanguageTests(TestCase):
    def setUp(self):
        # 需要一个管理员，避免 OOBE 中间件把请求重定向走。
        self.admin = User.objects.create_superuser(
            username='lang-admin', email='', password='test-password',
        )
        self.cfg = SiteSettings.get_settings()

    def test_anonymous_visitor_uses_site_default_language(self):
        self.cfg.default_language = 'en'
        self.cfg.save(update_fields=['default_language'])

        response = self.client.get(reverse('clubs:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign In')
        self.assertNotContains(response, '立即登录')

    def test_anonymous_cookie_overrides_site_default(self):
        self.cfg.default_language = 'en'
        self.cfg.save(update_fields=['default_language'])

        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'mn'
        response = self.client.get(reverse('clubs:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Нэвтрэх')

    def test_logged_in_preferred_language_overrides_site_default(self):
        self.cfg.default_language = 'en'
        self.cfg.save(update_fields=['default_language'])

        profile = self.admin.profile
        profile.preferred_language = 'ug'
        profile.save(update_fields=['preferred_language', 'updated_at'])
        self.client.force_login(self.admin)

        response = self.client.get(reverse('clubs:index'))
        self.assertEqual(response.status_code, 200)
        # 登录用户的首选语言（ug）优先于站点默认语言（en）
        self.assertEqual(response.context['LANGUAGE_CODE'], 'ug')


class PreferredLanguageUpdateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='lang-edit-admin', email='', password='test-password',
        )
        self.client.force_login(self.admin)

    def test_update_language_saves_profile_and_sets_cookie(self):
        response = self.client.post(
            reverse('clubs:edit_profile'),
            {'action': 'update_language', 'preferred_language': 'ug'},
        )
        self.assertRedirects(
            response,
            f"{reverse('clubs:edit_profile')}?tab=language",
            fetch_redirect_response=False,
        )
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.profile.preferred_language, 'ug')
        # Cookie 与数据库同步，保证当前设备立即生效
        self.assertIn(settings.LANGUAGE_COOKIE_NAME, self.client.cookies)
        self.assertEqual(
            self.client.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'ug',
        )

    def test_clearing_preference_follows_site_default(self):
        profile = self.admin.profile
        profile.preferred_language = 'en'
        profile.save(update_fields=['preferred_language', 'updated_at'])
        self.cfg = SiteSettings.get_settings()
        self.cfg.default_language = 'mn'
        self.cfg.save(update_fields=['default_language'])

        response = self.client.post(
            reverse('clubs:edit_profile'),
            {'action': 'update_language', 'preferred_language': ''},
        )
        self.assertRedirects(
            response,
            f"{reverse('clubs:edit_profile')}?tab=language",
            fetch_redirect_response=False,
        )
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.profile.preferred_language, '')
        # 清除偏好后回落站点默认语言（mn）
        followup = self.client.get(reverse('clubs:index'))
        self.assertEqual(followup.status_code, 200)
        self.assertEqual(followup.context['LANGUAGE_CODE'], 'mn')

    def test_invalid_language_is_rejected(self):
        response = self.client.post(
            reverse('clubs:edit_profile'),
            {'action': 'update_language', 'preferred_language': 'xx'},
        )
        self.assertRedirects(
            response,
            f"{reverse('clubs:edit_profile')}?tab=language",
            fetch_redirect_response=False,
        )
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.profile.preferred_language, '')


class ProfileOptionsTranslationTests(TestCase):
    def test_political_status_labels_are_translatable(self):
        labels = dict(UserProfile.POLITICAL_STATUS_CHOICES)
        with translation.override('en'):
            self.assertEqual(str(labels['communist_party_member']), 'Communist Party Member')
            self.assertEqual(str(labels['non_member']), 'General public')
        with translation.override('zh-hans'):
            self.assertEqual(str(labels['communist_party_member']), '中共党员')

    def test_preferred_language_empty_option_is_translatable(self):
        labels = dict(PREFERRED_LANGUAGE_CHOICES)
        with translation.override('en'):
            self.assertEqual(str(labels['']), 'Follow Site Default')


class SiteSettingsLanguageFieldTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='lang-site-admin', email='', password='test-password',
        )
        self.config = SiteSettings.get_settings()

    def test_site_settings_saves_default_language(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('clubs:site_settings'),
            {
                'form_type': 'site_info_settings',
                'site_name': '测试站点',
                'homepage_title': '测试首页标题',
                'homepage_subtitle': '测试首页副标题',
                'default_language': 'en',
            },
        )
        self.assertRedirects(
            response, reverse('clubs:site_settings'), fetch_redirect_response=False,
        )
        self.config.refresh_from_db()
        self.assertEqual(self.config.default_language, 'en')

    def test_site_settings_page_translated_for_english_admin(self):
        self.config.default_language = 'en'
        self.config.save(update_fields=['default_language'])
        self.admin.profile.preferred_language = 'en'
        self.admin.profile.save(update_fields=['preferred_language', 'updated_at'])
        self.client.force_login(self.admin)

        response = self.client.get(reverse('clubs:site_settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Site Default Language')
        self.assertContains(response, 'Save Site Info')
        self.assertContains(response, 'Automatic Translation')
