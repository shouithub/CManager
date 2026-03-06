#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复模板文件中 {% load i18n %} 和 {% extends %} 的顺序问题
Django 要求 {% extends %} 必须是第一个标签
"""

import os
from pathlib import Path

def fix_template_order(file_path):
    """修复单个模板文件的标签顺序"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if len(lines) < 2:
        return False
    
    # 检查是否需要修复
    first_line = lines[0].strip()
    second_line = lines[1].strip()
    
    if first_line == '{% load i18n %}' and second_line.startswith('{% extends'):
        # 交换前两行
        lines[0], lines[1] = lines[1], lines[0]
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        return True
    
    return False

def main():
    """查找并修复所有受影响的模板文件"""
    templates_dir = Path('templates')
    
    if not templates_dir.exists():
        print(f"❌ 目录不存在: {templates_dir}")
        return
    
    # 查找所有 HTML 文件
    html_files = list(templates_dir.rglob('*.html'))
    
    fixed_count = 0
    total_count = len(html_files)
    
    print(f"正在检查 {total_count} 个模板文件...")
    
    for html_file in html_files:
        try:
            if fix_template_order(html_file):
                print(f"✅ 已修复: {html_file}")
                fixed_count += 1
        except Exception as e:
            print(f"❌ 处理失败 {html_file}: {e}")
    
    print(f"\n✅ 完成！修复了 {fixed_count}/{total_count} 个文件")

if __name__ == '__main__':
    main()
