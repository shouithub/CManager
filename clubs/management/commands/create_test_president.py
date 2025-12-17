from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from clubs.models import UserProfile


class Command(BaseCommand):
    help = '创建测试社长账号'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='test_president',
            help='用户名 (默认: test_president)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='testpass123',
            help='密码 (默认: testpass123)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='president@test.com',
            help='邮箱 (默认: president@test.com)'
        )
        parser.add_argument(
            '--student_id',
            type=str,
            default='2024000001',
            help='学号 (默认: 2024000001)'
        )

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']
        student_id = options['student_id']

        # 检查用户是否已存在
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.ERROR(f'用户 "{username}" 已存在！')
            )
            return

        # 检查学号是否已存在
        if UserProfile.objects.filter(student_id=student_id).exists():
            self.stdout.write(
                self.style.ERROR(f'学号 "{student_id}" 已被使用！')
            )
            return

        try:
            # 创建用户
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            # 创建用户角色信息
            profile = UserProfile.objects.create(
                user=user,
                role='president',
                status='approved',
                real_name='测试社长',
                student_id=student_id,
                phone='13800138000',
                wechat='test_wechat',
                political_status='non_member'
            )

            self.stdout.write(
                self.style.SUCCESS(f'✓ 成功创建测试社长账号')
            )
            self.stdout.write(f'  用户名: {username}')
            self.stdout.write(f'  密码: {password}')
            self.stdout.write(f'  邮箱: {email}')
            self.stdout.write(f'  学号: {student_id}')
            self.stdout.write(f'  角色: 社长')
            self.stdout.write(f'  状态: 已批准')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'创建失败: {str(e)}')
            )
