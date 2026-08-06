from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from clubs.models import (
    ActivityRegistration,
    Announcement,
    Club,
    ClubMember,
    DailyStat,
    Department,
    FormChannel,
    FormChannelClubState,
    FormCycle,
    FormField,
    FormFieldValue,
    FormSubmission,
    FormSubmissionReview,
    Officer,
    PublishedActivity,
    Room,
    RoomBooking,
    SiteSettings,
    StaffClubRelation,
    StorageConfig,
    TimeSlot,
    UserProfile,
)


TEST_PASSWORD = "Test123456"


class Command(BaseCommand):
    help = "Seed local development database with representative test data."

    def handle(self, *args, **options):
        with transaction.atomic():
            users = self.seed_users()
            departments = self.seed_departments(users["admin"])
            clubs = self.seed_clubs(users)
            self.seed_staff_relations(users, departments, clubs)
            self.seed_memberships(users, clubs)
            self.seed_announcements(users["admin"])
            rooms, slots = self.seed_rooms()
            self.seed_bookings(users, clubs, rooms, slots)
            channels = self.seed_form_channels(users["admin"], clubs)
            submissions = self.seed_submissions(users, clubs, channels)
            self.normalize_legacy_file_names()
            self.seed_public_activity(users, clubs, submissions)
            self.seed_site_defaults()
            self.seed_daily_stats()

        self.stdout.write(self.style.SUCCESS("测试数据已写入完成。"))
        self.stdout.write(f"登录密码统一为：{TEST_PASSWORD}")
        role_labels = {
            "admin": "管理员",
            "staff": "干事",
            "president": "社长",
            "member": "成员",
        }
        self.stdout.write("测试账号列表：")
        for role in ("admin", "staff", "president", "member"):
            matches = [user for user in users.values() if user.profile.role == role]
            if not matches:
                continue
            self.stdout.write(f"  [{role_labels[role]}]")
            for user in matches:
                self.stdout.write(f"    - {user.username}")

    def normalize_legacy_file_names(self):
        """修复历史遗留的异常存储名（file://、绝对路径等），统一为站内相对路径。"""
        from django.core.files.base import ContentFile

        from ...models import FormUploadedFile
        from ...storage_backends import ClubStorage

        fixed = 0
        for uploaded in FormUploadedFile.objects.exclude(file="").iterator():
            legacy_name = uploaded.file.name or ""
            if not legacy_name.startswith("/") and "://" not in legacy_name:
                continue
            try:
                with uploaded.file.open("rb") as source:
                    content = source.read()
                storage = ClubStorage()
                new_name = storage.save(legacy_name, ContentFile(content))
                old_name = uploaded.file.name
                uploaded.file.name = new_name
                uploaded.save(update_fields=["file"])
                try:
                    storage.delete(old_name)
                except Exception:
                    pass
                fixed += 1
            except Exception:
                self.stderr.write(f"跳过无法读取的历史文件记录：{uploaded.pk}")
        if fixed:
            self.stdout.write(f"已修复 {fixed} 条历史文件记录")

    def upsert_user(
        self,
        username,
        *,
        role,
        real_name,
        email,
        student_id,
        phone,
        gender="other",
        college="信息学院",
        class_name="测试班级",
        is_staff=False,
        is_superuser=False,
        staff_level="member",
    ):
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": real_name[-1:],
                "last_name": real_name[:-1],
                "is_staff": is_staff,
                "is_superuser": is_superuser,
            },
        )
        user.email = email
        user.first_name = real_name[-1:]
        user.last_name = real_name[:-1]
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.set_password(TEST_PASSWORD)
        user.save()

        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                "role": role,
                "status": "approved",
                "real_name": real_name,
                "student_id": student_id,
                "gender": gender,
                "college": college,
                "class_name": class_name,
                "phone": phone,
                "qq": f"{student_id[-6:]}01",
                "wechat": username,
                "political_status": "communist_youth_league",
                "is_info_public": True,
                "account_status": "active",
                "active_until": timezone.now() + timedelta(days=365),
                "staff_level": staff_level,
            },
        )
        return user

    def seed_users(self):
        return {
            "admin": self.upsert_user(
                "test_admin",
                role="admin",
                real_name="测试管理员",
                email="test_admin@example.com",
                student_id="ADMIN_TEST",
                phone="13800000000",
                is_staff=True,
                is_superuser=True,
                college="社团管理服务中心",
            ),
            "staff_activity": self.upsert_user(
                "test_staff_activity",
                role="staff",
                real_name="林活动",
                email="staff_activity@example.com",
                student_id="2026001001",
                phone="13800000001",
                gender="female",
                college="管理学院",
                class_name="社管中心活动部",
                staff_level="director",
            ),
            "staff_general": self.upsert_user(
                "test_staff_general",
                role="staff",
                real_name="周综合",
                email="staff_general@example.com",
                student_id="2026001002",
                phone="13800000002",
                gender="male",
                college="经济管理学院",
                class_name="社管中心综合事务部",
            ),
            "president_music": self.upsert_user(
                "test_president_music",
                role="president",
                real_name="陈星河",
                email="president_music@example.com",
                student_id="2026002001",
                phone="13800000011",
                gender="female",
                college="人文学院",
                class_name="音乐与传播 2601",
            ),
            "president_code": self.upsert_user(
                "test_president_code",
                role="president",
                real_name="李蓝桥",
                email="president_code@example.com",
                student_id="2026002002",
                phone="13800000012",
                gender="male",
                college="信息学院",
                class_name="软件工程 2602",
            ),
            "president_volunteer": self.upsert_user(
                "test_president_volunteer",
                role="president",
                real_name="王绿野",
                email="president_volunteer@example.com",
                student_id="2026002003",
                phone="13800000013",
                gender="female",
                college="海洋生态学院",
                class_name="生态学 2601",
            ),
            "member_one": self.upsert_user(
                "test_member_one",
                role="member",
                real_name="赵晴",
                email="member_one@example.com",
                student_id="2026003001",
                phone="13800000021",
                gender="female",
                college="食品学院",
                class_name="食品科学 2601",
            ),
            "member_two": self.upsert_user(
                "test_member_two",
                role="member",
                real_name="孙舟",
                email="member_two@example.com",
                student_id="2026003002",
                phone="13800000022",
                gender="male",
                college="工程学院",
                class_name="机械工程 2602",
            ),
        }

    def seed_departments(self, admin):
        data = [
            ("综合事务部", "负责社团档案、注册材料与日常协调。", "社团注册\n信息归档\n通知发布", "assignment", 1),
            ("活动管理部", "负责活动审批、现场巡查与活动数据统计。", "活动审核\n场地协调\n安全预案", "event_available", 2),
            ("宣传联络部", "负责新媒体发布、品牌物料与跨社团联络。", "推文排期\n海报审核\n外联沟通", "campaign", 3),
        ]
        departments = {}
        for name, description, highlights, icon, order in data:
            dept, _ = Department.objects.update_or_create(
                name=name,
                defaults={
                    "description": description,
                    "highlights": highlights,
                    "icon": icon,
                    "order": order,
                    "updated_by": admin,
                },
            )
            departments[name] = dept
        return departments

    def seed_clubs(self, users):
        data = [
            (
                "星海音乐社",
                "面向热爱声乐、器乐与舞台表演的同学，定期组织排练、开放麦和校园音乐会。",
                date(2019, 9, 15),
                42,
                users["president_music"],
            ),
            (
                "蓝桥编程协会",
                "组织算法训练、项目共创和技术分享，帮助成员参与程序设计竞赛与开源实践。",
                date(2020, 10, 8),
                58,
                users["president_code"],
            ),
            (
                "绿野志愿服务队",
                "聚焦校园环保、社区陪伴与海洋科普志愿服务，开展长期公益项目。",
                date(2018, 3, 12),
                76,
                users["president_volunteer"],
            ),
            (
                "社管示范社",
                "用于测试管理员主身份兼任社长后的身份切换、社长工作台和审批记录。",
                date(2021, 5, 20),
                31,
                users["admin"],
            ),
        ]
        clubs = {}
        for name, description, founded_date, members_count, president in data:
            club, _ = Club.objects.update_or_create(
                name=name,
                defaults={
                    "description": description,
                    "founded_date": founded_date,
                    "status": "active",
                    "members_count": members_count,
                },
            )
            Officer.objects.update_or_create(
                club=club,
                user_profile=president.profile,
                position="president",
                defaults={
                    "appointed_date": date(2026, 6, 1),
                    "is_current": True,
                    "end_date": None,
                },
            )
            clubs[name] = club
        return clubs

    def seed_staff_relations(self, users, departments, clubs):
        users["staff_activity"].profile.department_link = departments["活动管理部"]
        users["staff_activity"].profile.save()
        users["staff_general"].profile.department_link = departments["综合事务部"]
        users["staff_general"].profile.save()

        relations = [
            (users["staff_activity"].profile, clubs["星海音乐社"]),
            (users["staff_activity"].profile, clubs["蓝桥编程协会"]),
            (users["staff_general"].profile, clubs["绿野志愿服务队"]),
        ]
        for staff_profile, club in relations:
            StaffClubRelation.objects.update_or_create(
                staff=staff_profile,
                club=club,
                defaults={"is_active": True},
            )

    def seed_memberships(self, users, clubs):
        memberships = [
            (clubs["星海音乐社"], users["president_music"].profile),
            (clubs["星海音乐社"], users["member_one"].profile),
            (clubs["蓝桥编程协会"], users["president_code"].profile),
            (clubs["蓝桥编程协会"], users["member_two"].profile),
            (clubs["绿野志愿服务队"], users["president_volunteer"].profile),
            (clubs["绿野志愿服务队"], users["member_one"].profile),
            (clubs["绿野志愿服务队"], users["member_two"].profile),
            (clubs["社管示范社"], users["admin"].profile),
            (clubs["社管示范社"], users["member_two"].profile),
        ]
        for club, profile in memberships:
            ClubMember.objects.update_or_create(
                club=club,
                user_profile=profile,
                defaults={"status": "active"},
            )

    def seed_announcements(self, admin):
        now = timezone.now()
        data = [
            ("2026 年秋季社团注册测试通知", "请各社团在测试周期内提交注册材料，并核对社长、成员与指导单位信息。", now),
            ("活动申请流程演示公告", "本公告用于本地测试审核中心、公告展示与社长工作台提醒效果。", now - timedelta(days=2)),
            ("活动室预约规则测试版", "请按固定时段预约活动室，借用后保持场地整洁并及时归还设备。", now - timedelta(days=5)),
        ]
        for title, content, published_at in data:
            Announcement.objects.update_or_create(
                title=title,
                defaults={
                    "content": content,
                    "status": "published",
                    "created_by": admin,
                    "published_at": published_at,
                    "expires_at": now + timedelta(days=90),
                },
            )

    def seed_rooms(self):
        slots_data = [
            ("上午第一段", time(8, 30), time(10, 0)),
            ("上午第二段", time(10, 15), time(11, 45)),
            ("下午第一段", time(13, 30), time(15, 0)),
            ("下午第二段", time(15, 15), time(16, 45)),
            ("晚间时段", time(18, 30), time(20, 30)),
        ]
        slots = {}
        for label, start, end in slots_data:
            slot, _ = TimeSlot.objects.update_or_create(
                label=label,
                defaults={"start_time": start, "end_time": end, "is_active": True},
            )
            slots[label] = slot

        rooms_data = [
            ("大学生活动中心 A101", 80, "大学生活动中心一楼", "配备投影、音响和可移动桌椅。"),
            ("社团排练室 B204", 35, "大学生活动中心二楼", "适合小型排练、面试和社团例会。"),
            ("多功能研讨室 C303", 50, "教学楼 C 区三楼", "适合培训、沙龙和项目路演。"),
        ]
        rooms = {}
        for name, capacity, location, description in rooms_data:
            room, _ = Room.objects.update_or_create(
                name=name,
                defaults={
                    "capacity": capacity,
                    "location": location,
                    "description": description,
                    "status": "available",
                },
            )
            rooms[name] = room
        return rooms, slots

    def seed_bookings(self, users, clubs, rooms, slots):
        today = timezone.localdate()
        data = [
            (
                rooms["大学生活动中心 A101"],
                users["president_music"],
                clubs["星海音乐社"],
                today + timedelta(days=3),
                slots["晚间时段"],
                "星海音乐社新生开放麦彩排",
                45,
                "需要无线麦克风 2 支",
            ),
            (
                rooms["多功能研讨室 C303"],
                users["president_code"],
                clubs["蓝桥编程协会"],
                today + timedelta(days=5),
                slots["下午第一段"],
                "蓝桥编程协会算法训练营",
                38,
                "需要投影仪和白板笔",
            ),
            (
                rooms["社团排练室 B204"],
                users["president_volunteer"],
                clubs["绿野志愿服务队"],
                today + timedelta(days=7),
                slots["上午第二段"],
                "绿野志愿服务队项目例会",
                24,
                "",
            ),
        ]
        for room, user, club, booking_date, slot, purpose, count, requirements in data:
            RoomBooking.objects.update_or_create(
                room=room,
                user=user,
                booking_date=booking_date,
                start_time=slot.start_time,
                defaults={
                    "club": club,
                    "end_time": slot.end_time,
                    "purpose": purpose,
                    "participant_count": count,
                    "contact_phone": user.profile.phone,
                    "special_requirements": requirements,
                    "status": "active",
                },
            )

    def seed_form_channels(self, admin, clubs):
        specs = [
            (
                "activity_application",
                "活动申请",
                "event",
                "社团活动策划、场地、安全预案等材料提交。",
                "activity_application",
                "repeatable",
                1,
                [
                    ("活动名称", "activity_name", "text", 1, "请输入活动全称", [], {}),
                    ("活动类型", "activity_type", "select", 2, "", ["讲座", "比赛", "演出", "培训", "志愿服务", "其他"], {}),
                    ("活动日期", "activity_date", "date", 3, "", [], {}),
                    ("开始时间", "activity_time_start", "time", 4, "", [], {}),
                    ("结束时间", "activity_time_end", "time", 5, "", [], {}),
                    ("活动地点", "activity_location", "text", 6, "", [], {}),
                    ("预计人数", "expected_participants", "number", 7, "", [], {"min": 1}),
                    ("预算金额", "budget", "number", 8, "", [], {"min": 0}),
                    ("联系人", "contact_person", "text", 9, "", [], {}),
                    ("联系电话", "contact_phone", "text", 10, "", [], {}),
                    ("活动说明", "activity_description", "textarea", 11, "", [], {}),
                ],
            ),
            (
                "reimbursement",
                "报销申请",
                "payments",
                "社团活动经费报销、票据与明细提交。",
                "reimbursement",
                "repeatable",
                1,
                [
                    ("报销事项", "title", "text", 1, "", [], {}),
                    ("报销金额", "amount", "number", 2, "", [], {"min": 0}),
                    ("费用类别", "expense_type", "select", 3, "", ["物料", "宣传", "场地", "交通", "其他"], {}),
                    ("费用说明", "description", "textarea", 4, "", [], {}),
                ],
            ),
            (
                "annual_review",
                "社团年审",
                "fact_check",
                "年度自查、成员情况、活动总结与财务情况提交。",
                "annual_review",
                "once_per_cycle",
                2,
                [
                    ("提交年度", "submission_year", "number", 1, "", [], {"min": 2000, "max": 2100}),
                    ("社团总结", "summary", "textarea", 2, "", [], {}),
                    ("成员规模", "member_count", "number", 3, "", [], {"min": 1}),
                    ("财务情况", "finance_summary", "textarea", 4, "", [], {}),
                ],
            ),
        ]
        channels = {}
        for order, spec in enumerate(specs, start=1):
            slug, name, icon, description, action, policy, approval_count, fields = spec
            channel, _ = FormChannel.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "icon": icon,
                    "description": description,
                    "order": order,
                    "is_active": True,
                    "publish_status": "published",
                    "is_builtin": True,
                    "builtin_action": action,
                    "submission_policy": policy,
                    "required_approval_count": approval_count,
                    "show_zip_download": True,
                    "show_unsubmitted_status": policy == "once_per_cycle",
                    "show_unsubmitted_alert": action in ("annual_review", "club_registration"),
                    "alert_color": "#9a6700" if action == "annual_review" else "#b3261e",
                    "allow_staff_toggle": True,
                    "cycle_type": "year" if policy == "once_per_cycle" else "none",
                },
            )
            for label, key, field_type, field_order, placeholder, options, validation in fields:
                FormField.objects.update_or_create(
                    channel=channel,
                    field_key=key,
                    defaults={
                        "label": label,
                        "field_type": field_type,
                        "required": True,
                        "order": field_order,
                        "placeholder": placeholder,
                        "options": options,
                        "validation": validation,
                        "is_active": True,
                    },
                )
            for club in clubs.values():
                FormChannelClubState.objects.update_or_create(
                    channel=channel,
                    club=club,
                    defaults={"is_enabled": True, "updated_by": admin},
                )
            if policy == "once_per_cycle":
                FormCycle.objects.update_or_create(
                    channel=channel,
                    sequence=2026,
                    defaults={
                        "name": "2026 年度",
                        "is_active": True,
                        "starts_at": timezone.make_aware(timezone.datetime(2026, 1, 1, 0, 0)),
                        "ends_at": timezone.make_aware(timezone.datetime(2026, 12, 31, 23, 59)),
                        "created_by": admin,
                    },
                )
            channels[slug] = channel
        return channels

    def set_submission_values(self, submission, values):
        fields = {
            field.field_key: field
            for field in FormField.objects.filter(channel=submission.channel)
        }
        for key, value in values.items():
            field = fields[key]
            FormFieldValue.objects.update_or_create(
                submission=submission,
                field=field,
                defaults={
                    "value_text": str(value),
                    "value_json": {},
                    "review_status": "approved" if submission.status == "approved" else "pending",
                },
            )

    def seed_submissions(self, users, clubs, channels):
        today = timezone.localdate()
        activity_channel = channels["activity_application"]
        reimbursement_channel = channels["reimbursement"]
        annual_review_channel = channels["annual_review"]
        annual_cycle = annual_review_channel.cycles.get(sequence=2026)

        activity_submission, _ = FormSubmission.objects.update_or_create(
            channel=activity_channel,
            club=clubs["星海音乐社"],
            submitter=users["president_music"],
            metadata={"seed_key": "star_music_open_mic"},
            defaults={
                "status": "approved",
                "reviewer": users["staff_activity"],
                "review_comment": "材料完整，活动风险较低，同意举办。",
                "reviewed_at": timezone.now() - timedelta(days=1),
                "is_read": True,
            },
        )
        self.set_submission_values(
            activity_submission,
            {
                "activity_name": "星海夏夜开放麦",
                "activity_type": "演出",
                "activity_date": today + timedelta(days=10),
                "activity_time_start": "18:30",
                "activity_time_end": "20:30",
                "activity_location": "大学生活动中心 A101",
                "expected_participants": 80,
                "budget": "1200.00",
                "contact_person": "陈星河",
                "contact_phone": "13800000011",
                "activity_description": "面向全校同学开放报名的音乐交流活动，包含弹唱、合奏与互动点歌环节。",
            },
        )
        FormSubmissionReview.objects.update_or_create(
            submission=activity_submission,
            reviewer=users["staff_activity"],
            submission_attempt=1,
            defaults={"status": "approved", "comment": "同意举办。"},
        )

        reimbursement_submission, _ = FormSubmission.objects.update_or_create(
            channel=reimbursement_channel,
            club=clubs["蓝桥编程协会"],
            submitter=users["president_code"],
            metadata={"seed_key": "blue_bridge_training"},
            defaults={
                "status": "pending",
                "reviewer": None,
                "review_comment": "",
                "reviewed_at": None,
                "is_read": False,
            },
        )
        self.set_submission_values(
            reimbursement_submission,
            {
                "title": "算法训练营物料报销",
                "amount": "386.50",
                "expense_type": "物料",
                "description": "购买讲义打印、签到贴纸和获奖证书纸张。",
            },
        )

        annual_submission, _ = FormSubmission.objects.update_or_create(
            channel=annual_review_channel,
            club=clubs["绿野志愿服务队"],
            submitter=users["president_volunteer"],
            cycle=annual_cycle,
            metadata={"seed_key": "green_field_2026_review"},
            defaults={
                "status": "rejected",
                "reviewer": users["staff_general"],
                "review_comment": "财务情况说明还需补充票据编号与结余明细。",
                "reviewed_at": timezone.now() - timedelta(hours=6),
                "is_read": True,
            },
        )
        self.set_submission_values(
            annual_submission,
            {
                "submission_year": "2026",
                "summary": "全年组织海洋科普志愿讲解、校园清洁行动和社区陪伴项目共 18 场。",
                "member_count": 76,
                "finance_summary": "已列出主要支出，但票据编号待补充。",
            },
        )
        FormSubmissionReview.objects.update_or_create(
            submission=annual_submission,
            reviewer=users["staff_general"],
            submission_attempt=1,
            defaults={"status": "rejected", "comment": "请补充财务明细后重新提交。"},
        )

        return {
            "activity": activity_submission,
            "reimbursement": reimbursement_submission,
            "annual": annual_submission,
        }

    def seed_public_activity(self, users, clubs, submissions):
        today = timezone.localdate()
        activity, _ = PublishedActivity.objects.update_or_create(
            source_submission=submissions["activity"],
            defaults={
                "club": clubs["星海音乐社"],
                "activity_name": "星海夏夜开放麦",
                "activity_type": "演出",
                "activity_description": "面向全校同学开放报名的音乐交流活动，包含弹唱、合奏与互动点歌环节。",
                "activity_date": today + timedelta(days=10),
                "activity_time_start": time(18, 30),
                "activity_time_end": time(20, 30),
                "activity_location": "大学生活动中心 A101",
                "expected_participants": 80,
                "budget": Decimal("1200.00"),
                "contact_person": "陈星河",
                "contact_phone": "13800000011",
                "is_public": True,
                "published_at": timezone.now() - timedelta(days=1),
            },
        )
        for user_key in ["member_one", "member_two"]:
            ActivityRegistration.objects.update_or_create(
                activity=activity,
                user_profile=users[user_key].profile,
            )

    def seed_site_defaults(self):
        SiteSettings.get_settings()
        StorageConfig.get_active_config()

    def seed_daily_stats(self):
        today = timezone.localdate()
        visits = [68, 93, 117, 86, 142, 159, 121]
        for index, count in enumerate(visits):
            DailyStat.objects.update_or_create(
                date=today - timedelta(days=index),
                defaults={"visits": count},
            )
