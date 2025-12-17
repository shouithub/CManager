#!/usr/bin/env python3
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
import os
import shutil
from clubs.models import (
    Club,
    ReviewSubmission,
    Reimbursement,
    ClubInfoChangeRequest,
    ClubRegistrationRequest,
    ClubApplicationReview,
    ClubRegistration,
    ClubRegistrationReview
)

class Command(BaseCommand):
    help = '删除数据库中所有社团信息及相关上传文件'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('警告：此操作将删除所有社团相关数据和上传文件，不可恢复！'))
        self.stdout.write(self.style.WARNING('请确认是否继续？(y/N)'))
        
        # 获取用户输入
        user_input = input().lower()
        if user_input != 'y':
            self.stdout.write(self.style.SUCCESS('操作已取消'))
            return

        try:
            # 使用事务确保数据一致性
            with transaction.atomic():
                # 删除所有社团相关数据
                self.stdout.write('正在删除社团数据...')
                Club.objects.all().delete()
                self.stdout.write(self.style.SUCCESS('✓ 社团数据已删除'))

                self.stdout.write('正在删除年审提交数据...')
                ReviewSubmission.objects.all().delete()
                self.stdout.write(self.style.SUCCESS('✓ 年审提交数据已删除'))

                self.stdout.write('正在删除报销数据...')
                Reimbursement.objects.all().delete()
                self.stdout.write(self.style.SUCCESS('✓ 报销数据已删除'))

                self.stdout.write('正在删除社团信息变更请求...')
                ClubInfoChangeRequest.objects.all().delete()
                self.stdout.write(self.style.SUCCESS('✓ 社团信息变更请求已删除'))

                self.stdout.write('正在删除社团注册请求...')
                ClubRegistrationRequest.objects.all().delete()
                self.stdout.write(self.style.SUCCESS('✓ 社团注册请求已删除'))

                self.stdout.write('正在删除社团申请审核...')
                ClubApplicationReview.objects.all().delete()
                self.stdout.write(self.style.SUCCESS('✓ 社团申请审核已删除'))

                self.stdout.write('正在删除社团注册数据...')
                ClubRegistration.objects.all().delete()
                self.stdout.write(self.style.SUCCESS('✓ 社团注册数据已删除'))

                self.stdout.write('正在删除社团注册审核...')
                ClubRegistrationReview.objects.all().delete()
                self.stdout.write(self.style.SUCCESS('✓ 社团注册审核已删除'))

            # 删除上传的文件
            self.stdout.write('正在删除上传的文件...')
            media_dir = settings.MEDIA_ROOT
            
            # 删除announcements目录
            announcements_dir = os.path.join(media_dir, 'announcements')
            if os.path.exists(announcements_dir):
                shutil.rmtree(announcements_dir)
                self.stdout.write(self.style.SUCCESS(f'✓ 已删除 {announcements_dir}'))

            # 删除reviews目录
            reviews_dir = os.path.join(media_dir, 'reviews')
            if os.path.exists(reviews_dir):
                shutil.rmtree(reviews_dir)
                self.stdout.write(self.style.SUCCESS(f'✓ 已删除 {reviews_dir}'))

            # 删除templates目录
            templates_dir = os.path.join(media_dir, 'templates')
            if os.path.exists(templates_dir):
                shutil.rmtree(templates_dir)
                self.stdout.write(self.style.SUCCESS(f'✓ 已删除 {templates_dir}'))

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('所有社团信息及相关上传文件已成功删除！'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'操作失败：{str(e)}'))
            import traceback
            traceback.print_exc()