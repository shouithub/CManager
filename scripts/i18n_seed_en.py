#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seed English translations for common Chinese UI strings."""
from pathlib import Path

MAPPING = {
    "保存": "Save",
    "取消": "Cancel",
    "提交": "Submit",
    "登录": "Login",
    "登出": "Logout",
    "注册": "Register",
    "搜索": "Search",
    "删除": "Delete",
    "编辑": "Edit",
    "修改": "Modify",
    "新增": "Add",
    "创建": "Create",
    "确认": "Confirm",
    "返回": "Back",
    "首页": "Home",
    "用户": "User",
    "社团": "Club",
    "部门": "Department",
    "房间": "Room",
    "活动": "Activity",
    "公告": "Announcement",
    "设置": "Settings",
    "管理": "Manage",
    "审核": "Review",
    "审批": "Approve",
    "通过": "Approve",
    "不通过": "Reject",
    "打回": "Reject",
    "待审核": "Pending",
    "已通过": "Approved",
    "已拒绝": "Rejected",
    "名称": "Name",
    "描述": "Description",
    "标题": "Title",
    "内容": "Content",
    "状态": "Status",
    "操作": "Actions",
    "时间": "Time",
    "日期": "Date",
    "邮箱": "Email",
    "电话": "Phone",
    "用户名": "Username",
    "密码": "Password",
    "头像": "Avatar",
    "上传": "Upload",
    "下载": "Download",
    "预览": "Preview",
    "导出": "Export",
    "导入": "Import",
    "刷新": "Refresh",
    "加载中": "Loading",
    "暂无数据": "No data",
    "确定要删除吗": "Are you sure you want to delete?",
    "成功": "Success",
    "失败": "Failed",
    "错误": "Error",
    "警告": "Warning",
    "信息": "Info",
    "欢迎使用": "Welcome",
}


def fill_po(path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        out.append(line)
        if line.startswith('msgid "'):
            # Collect full msgid
            msgid_parts = []
            while line.startswith('msgid "') or (line.startswith('"') and not line.startswith('msgstr')):
                if line.startswith('msgid '):
                    msgid_parts.append(line[6:].strip('"'))
                else:
                    msgid_parts.append(line.strip('"'))
                i += 1
                if i >= n:
                    break
                line = lines[i]
            msgid = "".join(msgid_parts)
            # Now line is msgstr
            if line.startswith('msgstr "'):
                msgstr_parts = []
                while line.startswith('msgstr "') or (line.startswith('"') and not line.startswith('msgid')):
                    if line.startswith('msgstr '):
                        msgstr_parts.append(line[7:].strip('"'))
                    else:
                        msgstr_parts.append(line.strip('"'))
                    out.append(line)
                    i += 1
                    if i >= n:
                        break
                    line = lines[i]
                msgstr = "".join(msgstr_parts)
                if not msgstr and msgid in MAPPING:
                    # Replace last msgstr line
                    out[-1] = f'msgstr "{MAPPING[msgid]}"'
            continue
        i += 1
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    for domain in ("django", "djangojs"):
        po = Path(f"locale/en/LC_MESSAGES/{domain}.po")
        if po.exists():
            fill_po(po)
            print(f"Filled {po}")
