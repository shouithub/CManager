from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import (
    Club,
    FormChannel,
    FormCycle,
    StaffClubRelation,
    UserProfile,
)


class StaffAlertSystemTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username='staff-alert', password='pw')
        self.staff_profile = UserProfile.objects.create(
            user=self.staff, role='staff', status='approved', real_name='测试干事',
        )
        self.admin = User.objects.create_superuser(
            username='admin-alert', email='', password='pw',
        )

        self.club_mine = Club.objects.create(name='我的社团', founded_date=date(2020, 1, 1), members_count=50)
        self.club_other = Club.objects.create(name='其他社团', founded_date=date(2020, 1, 1), members_count=30)
        StaffClubRelation.objects.create(staff=self.staff_profile, club=self.club_mine, is_active=True)

        self.channel = FormChannel.objects.create(
            name='场地申请',
            slug='venue-apply-alert',
            is_active=True,
            publish_status='published',
            submission_policy='once_per_cycle',
            cycle_type='year',
            show_unsubmitted_alert=True,
            alert_color='#123456',
        )
        FormCycle.objects.create(channel=self.channel, name='2026年度', sequence=1, is_active=True)

    def test_staff_management_unified_alerts(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('clubs:staff_management'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('未提交场地申请预警', html)
        self.assertIn('alertListModal', html)
        self.assertIn('ALERTS_DATA', html)
        # 其他干事的社团以弹窗按钮呈现，且使用通道配置的颜色
        self.assertIn('其他干事负责 (1)', html)
        self.assertIn('#123456', html)
        # 我的社团在卡片中直接展示
        self.assertIn('我的社团', html)

        # 局部渲染（AJAX 软导航）模式下告警区同样可用
        partial = self.client.get(
            reverse('clubs:staff_management'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(partial.status_code, 200)
        partial_html = partial.content.decode('utf-8')
        self.assertIn('未提交场地申请预警', partial_html)
        self.assertIn('alertListModal', partial_html)

    def test_form_channel_settings_ui_has_alert_options(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('clubs:manage_form_channels_detail', args=[self.channel.id])
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('告警设置', html)
        self.assertIn('show_unsubmitted_alert', html)
        self.assertIn('alert_color', html)
        self.assertIn('#123456', html)
