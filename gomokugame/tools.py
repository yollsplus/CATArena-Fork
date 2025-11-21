#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理工具 - 用于清理迭代测试的临时文件
"""

import shutil
from pathlib import Path


def clean_ai_develop():
    """从 AI_develop_backup 恢复模板到 AI_develop"""
    base_path = Path(__file__).parent / "gomoku"
    ai_develop = base_path / "AI_develop"
    ai_backup = base_path / "AI_develop_backup"
    
    if not ai_backup.exists():
        print(f"❌ 错误: 备份目录不存在: {ai_backup}")
        return
    
    # 删除现有的 AI_develop
    if ai_develop.exists():
        shutil.rmtree(ai_develop)
        print(f"🗑️  已删除: {ai_develop}")
    
    # 从备份复制
    shutil.copytree(ai_backup, ai_develop)
    print(f"✅ 已恢复模板: {ai_backup} -> {ai_develop}")


def clean_gpt_ai():
    """清理 gpt-4o_ai 目录"""
    gpt_ai = Path(__file__).parent / "AI_competitors" / "gomoku" / "gpt-4o_ai"
    if gpt_ai.exists():
        shutil.rmtree(gpt_ai)
        print(f"✅ 已清理: {gpt_ai}")
    else:
        print(f"⏭️  跳过: {gpt_ai} (不存在)")


def clean_all():
    """清理所有目录"""
    print("=" * 60)
    print("开始清理迭代测试目录...")
    print("=" * 60)
    
    clean_ai_develop()
    clean_gpt_ai()
    
    print("=" * 60)
    print("清理完成!")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "develop":
            clean_ai_develop()
        elif cmd == "gpt":
            clean_gpt_ai()
        elif cmd == "all":
            clean_all()
        else:
            print("用法:")
            print("  python tools.py          # 清理所有")
            print("  python tools.py all      # 清理所有")
            print("  python tools.py develop  # 仅清理 AI_develop")
            print("  python tools.py gpt      # 仅清理 gpt-4o_ai")
    else:
        clean_all()
