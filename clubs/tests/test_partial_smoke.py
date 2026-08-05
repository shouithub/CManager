from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class PartialRenderSmokeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='partial-admin', email='a@b.c', password='test-password',
        )
        self.client.force_login(self.user)

    def test_full_page_has_html_and_partial_has_fragment(self):
        full = self.client.get(reverse('clubs:index'))
        self.assertContains(full, '<html')
        partial = self.client.get(
            reverse('clubs:index'), HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertContains(partial, 'soft-partial-content')
        self.assertNotContains(partial, '<html')
        # 局部响应不应包含侧边栏
        self.assertNotContains(partial, 'sidebar-menu')

    def test_admin_page_partial_chain(self):
        from ..models import SiteSettings
        SiteSettings.get_settings()
        partial = self.client.get(
            reverse('clubs:manage_users'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(partial.status_code, 200)
        self.assertContains(partial, 'soft-partial-content')
        self.assertNotContains(partial, '<html')
        self.assertContains(partial, '批量导入')
