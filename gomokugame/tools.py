#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境初始化工具
功能：
1. 清理旧的比赛代码 (AI_competitors)
2. 将 AI_develop 模板代码分发给所有 Agent (AI_develop_workspace)
"""

import shutil
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent

def load_config():
    config_path = BASE_DIR / "my_config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def reset_template_from_backup():
    """(可选) 从 AI_develop_backup 强制恢复 AI_develop"""
    ai_develop = BASE_DIR / "gomoku" / "AI_develop"
    ai_backup = BASE_DIR / "gomoku" / "AI_develop_backup"
    
    if not ai_backup.exists():
        print(f"❌ 错误: 备份目录不存在: {ai_backup}")
        return
    
    if ai_develop.exists():
        shutil.rmtree(ai_develop)
        print(f"🗑️  已删除旧模板: {ai_develop}")
    
    shutil.copytree(ai_backup, ai_develop)
    print(f"✅ 已从备份恢复模板: {ai_develop}")

def clean_competitors():
    """清理 AI_competitors 下的 Agent 目录"""
    config = load_config()
    agents = config.get('agents', [])
    if not agents and 'agent' in config:
        agents = [config['agent']]
        
    competitors_base = BASE_DIR / "AI_competitors" / "gomoku"
    
    for agent in agents:
        model = agent['model']
        # 清理该模型下的所有版本
        target_dir = competitors_base / f"{model}_ai"
        if target_dir.exists():
            shutil.rmtree(target_dir)
            print(f"🗑️  已清理旧产物: {target_dir}")

def init_workspaces():
    """初始化所有 Agent 的工作区 (直接覆盖)"""
    config = load_config()
    agents = config.get('agents', [])
    if not agents and 'agent' in config:
        agents = [config['agent']]
        
    source_template = BASE_DIR / "gomoku" / "AI_develop"
    if not source_template.exists():
        print(f"❌ 错误: 开发模板不存在: {source_template}")
        return

    workspace_base = BASE_DIR / "gomoku" / "AI_develop_workspace"
    # 确保父目录存在
    workspace_base.mkdir(parents=True, exist_ok=True)

    print(f"📂 模板源: {source_template}")

    for agent in agents:
        model = agent['model']
        agent_workspace = workspace_base / f"{model}_ai"
        
        # 如果存在则删除，确保干净的覆盖
        if agent_workspace.exists():
            shutil.rmtree(agent_workspace)
        
        shutil.copytree(source_template, agent_workspace)
        print(f"✅ 已初始化工作区: {agent_workspace.name}")

def run_main():
    print("=" * 60)
    print("开始初始化开发环境...")
    print("=" * 60)
    
    # 1. 清理旧的比赛产出，防止混淆
    clean_competitors()
    
    # 2. 将 AI_develop 分发给各个 Agent
    init_workspaces()
    
    print("=" * 60)
    print("环境准备就绪! 请运行: python auto_iteration_manager.py --config my_config.json")
    print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset_template":
        # 只有显式要求时才重置模板
        reset_template_from_backup()
    else:
        run_main()
