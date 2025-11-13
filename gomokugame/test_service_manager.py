#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试服务管理器
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from auto_iteration_manager import ServiceManager
import time

def test_service_manager():
    """测试服务管理器"""
    base_dir = Path(__file__).parent
    manager = ServiceManager(base_dir)
    
    print("=" * 60)
    print("测试服务管理器")
    print("=" * 60)
    
    try:
        # 1. 启动游戏服务器
        print("\n1️⃣ 测试启动游戏服务器...")
        if manager.start_game_server('gomoku', 9000):
            print("✅ 游戏服务器启动成功")
        else:
            print("❌ 游戏服务器启动失败")
            return
        
        # 2. 启动 demo1 AI
        print("\n2️⃣ 测试启动 demo1 AI...")
        demo1_path = base_dir / "AI_competitors/gomoku/round_1/demo1/gomoku_v1"
        if demo1_path.exists():
            if manager.start_ai_service(demo1_path, 12001, "Demo 1"):
                print("✅ demo1 启动成功")
            else:
                print("❌ demo1 启动失败")
        else:
            print(f"⚠️  找不到 demo1 路径: {demo1_path}")
        
        # 3. 启动 demo2 AI
        print("\n3️⃣ 测试启动 demo2 AI...")
        demo2_path = base_dir / "AI_competitors/gomoku/round_1/demo2/gomoku_v1"
        if demo2_path.exists():
            if manager.start_ai_service(demo2_path, 12002, "Demo 2"):
                print("✅ demo2 启动成功")
            else:
                print("❌ demo2 启动失败")
        else:
            print(f"⚠️  找不到 demo2 路径: {demo2_path}")
        
        # 4. 启动 gpt-4o-mini AI
        print("\n4️⃣ 测试启动 gpt-4o-mini_ai_v1...")
        gpt_path = base_dir / "AI_competitors/gomoku/round_1/gpt-4o-mini_ai_v1/gomoku_v1"
        if gpt_path.exists():
            if manager.start_ai_service(gpt_path, 12003, "GPT-4o-mini AI v1"):
                print("✅ gpt-4o-mini_ai_v1 启动成功")
            else:
                print("❌ gpt-4o-mini_ai_v1 启动失败")
        else:
            print(f"⚠️  找不到 gpt-4o-mini_ai_v1 路径: {gpt_path}")
        
        # 5. 等待用户按键
        print("\n" + "=" * 60)
        print("所有服务已启动！")
        print("按 Enter 键停止所有服务...")
        print("=" * 60)
        input()
        
    finally:
        # 清理
        manager.cleanup()

if __name__ == '__main__':
    test_service_manager()
