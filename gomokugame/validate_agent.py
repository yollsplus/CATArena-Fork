#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent 学习能力验证脚本 (重构版)
========================================
让同一个 Agent 的不同版本 (v1, v2, v3...) 两两对战，评估学习效果
完全复用 auto_iteration_manager 的对战逻辑 (GomokuArena)

    python validate_agent.py --agent gpt-4o_ai --game gomoku
    python validate_agent.py --agent gpt-4o_ai --game gomoku --versions 1 2 3
    python validate_agent.py --agent gpt-4o_ai --game gomoku --rounds 5
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import subprocess
import signal
import atexit
import requests

# =============================================================================
# ServiceManager (复用 auto_iteration_manager.py 的实现)
# =============================================================================

class ServiceManager:
    """服务进程管理器"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.processes = []  # [(name, process, port), ...]
        atexit.register(self.cleanup)
    
    def start_game_server(self, game: str = 'gomoku', port: int = 9000) -> bool:
        """启动游戏服务器"""
        print(f"\n🚀 启动游戏服务器 ({game})...")
        
        server_dir = self.base_dir / game
        log_dir = self.base_dir / "service_logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{game}_server.log"
        
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                proc = subprocess.Popen(
                    [sys.executable, 'server.py'],
                    cwd=server_dir,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
                )
            
            self.processes.append(('game_server', proc, port))
            
            if self._wait_for_service(f'http://localhost:{port}/health', timeout=15):
                print(f"   ✅ 游戏服务器已启动 (端口 {port})")
                return True
            else:
                print(f"   ⚠️  游戏服务器启动超时")
                return False
                
        except Exception as e:
            print(f"   ❌ 启动失败: {e}")
            return False
    
    def start_ai_service(self, ai_path: Path, port: int, ai_name: str) -> bool:
        """启动 AI 服务"""
        print(f"🤖 启动 AI 服务: {ai_name} (端口 {port})...")
        
        py_files = [f for f in ai_path.glob("*.py") if f.name != '__init__.py']
        
        if not py_files:
            print(f"   ❌ 找不到 Python 文件")
            return False
        
        py_file = py_files[0].name
        
        log_dir = self.base_dir / "service_logs"
        log_dir.mkdir(exist_ok=True)
        safe_name = ai_name.replace(' ', '_').replace('/', '_')
        log_file = log_dir / f"{safe_name}_{port}.log"
        
        try:
            cmd = [sys.executable, py_file, '--port', str(port)]
            
            with open(log_file, 'w', encoding='utf-8') as f:
                proc = subprocess.Popen(
                    cmd,
                    cwd=ai_path,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
                )
            
            self.processes.append((f'ai_{ai_name}', proc, port))
            
            if self._wait_for_service(f'http://localhost:{port}/health', timeout=10):
                print(f"   ✅ {ai_name} 已启动")
                return True
            else:
                if proc.poll() is not None:
                    print(f"   ❌ AI 启动失败")
                else:
                    print(f"   ⚠️  健康检查超时")
                return False
                
        except Exception as e:
            print(f"   ❌ 启动失败: {e}")
            return False
    
    def _wait_for_service(self, url: str, timeout: int = 30) -> bool:
        """等待服务就绪"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                resp = requests.get(url, timeout=1)
                if resp.status_code == 200:
                    return True
            except:
                pass
            time.sleep(0.5)
        return False
    
    def cleanup(self):
        """清理所有进程"""
        if not self.processes:
            return
            
        print("\n🧹 清理服务进程...")
        for name, proc, port in self.processes:
            try:
                if proc.poll() is None:
                    if sys.platform == 'win32':
                        proc.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
            except Exception:
                pass
        self.processes.clear()
        
        # 强力清理端口
        target_ports = [9000] + [p for _, _, p in self.processes]
        if sys.platform == 'win32':
            for port in target_ports:
                try:
                    cmd = f"netstat -ano | findstr :{port}"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.stdout:
                        lines = result.stdout.strip().split('\n')
                        for line in lines:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                pid = parts[-1]
                                if pid != '0':
                                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
                except Exception:
                    pass
        print("✅ 清理完成\n")

# =============================================================================
# AgentValidator
# =============================================================================

class AgentValidator:
    """Agent 学习能力验证器"""
    
    def __init__(self, agent_name: str, game: str, base_dir: Path):
        self.agent_name = agent_name
        self.game = game
        self.base_dir = base_dir
        self.service_manager = ServiceManager(base_dir)
        
        # 输出目录
        self.output_dir = base_dir / "validation_reports"
        self.output_dir.mkdir(exist_ok=True)
        
        print("=" * 80)
        print("Agent 学习能力验证器 (Arena Mode)")
        print("=" * 80)
        print(f"Agent: {agent_name}")
        print(f"游戏: {game}")
        print(f"输出目录: {self.output_dir}")
        print("=" * 80)
    
    def find_versions(self) -> List[int]:
        """查找该 Agent 的所有版本"""
        agent_dir = self.base_dir / "AI_competitors" / self.game / self.agent_name
        if not agent_dir.exists():
            print(f"⚠️  Agent 目录不存在: {agent_dir}")
            return []
        
        versions = []
        for ver_dir in agent_dir.iterdir():
            if ver_dir.is_dir() and ver_dir.name.startswith('v'):
                try:
                    ver_num = int(ver_dir.name[1:])
                    versions.append(ver_num)
                except ValueError:
                    continue
        versions.sort()
        return versions
    
    def validate_learning(self, versions: Optional[List[int]] = None, 
                         rounds_per_match: int = 2) -> Dict:
        """验证 Agent 的学习能力"""
        
        # 1. 查找版本
        available_versions = self.find_versions()
        if not available_versions:
            return {"error": "没有找到任何版本"}
        
        print(f"\n✅ 找到 {len(available_versions)} 个版本: {available_versions}")
        
        # 确定要对战的版本
        if versions:
            test_versions = [v for v in versions if v in available_versions]
            if not test_versions:
                return {"error": "指定的版本不存在"}
        else:
            test_versions = available_versions
        
        if len(test_versions) < 2:
            return {"error": "至少需要 2 个版本才能对战"}
            
        print(f"📊 将测试 {len(test_versions)} 个版本: {test_versions}")
        
        # 2. 启动游戏服务器
        if not self.service_manager.start_game_server(self.game):
            return {"error": "游戏服务器启动失败"}
            
        # 3. 启动所有版本的 AI 服务
        ai_configs = []
        start_port = 12000
        
        for i, v in enumerate(test_versions):
            port = start_port + i + 1
            v_name = f"{self.agent_name}_v{v}"
            v_path = self.base_dir / "AI_competitors" / self.game / self.agent_name / f"v{v}"
            
            if self.service_manager.start_ai_service(v_path, port, v_name):
                ai_configs.append({
                    "ai_id": f"v{v}",
                    "ai_name": v_name,
                    "port": port
                })
            else:
                print(f"⚠️  v{v} 启动失败，跳过")
        
        if len(ai_configs) < 2:
            return {"error": "成功启动的 AI 数量不足 2 个"}
            
        # 4. 初始化 Arena 并运行锦标赛
        try:
            # 导入 Arena 相关模块
            arena_path = self.base_dir / f"{self.game}_Arena"
            if str(arena_path) not in sys.path:
                sys.path.insert(0, str(arena_path))
            
            from arena import GomokuArena
            from config import ArenaConfig
            
            # 加载配置 (为了获取 timeout 等设置)
            config_file = arena_path / "configs" / "round_1_config.json"
            print(f"\n使用配置文件: {config_file}")
            
            arena_config = ArenaConfig(str(config_file))
            game_server_url = arena_config.get_game_server_url()
            timeout = arena_config.get_timeout()
            
            # 初始化 Arena
            # 注意：这里我们使用 rounds_per_match 参数覆盖配置中的设置
            arena = GomokuArena(game_server_url, timeout, rounds_per_match)
            
            # 添加 AI
            print("\n添加参赛 AI:")
            for ai in ai_configs:
                arena.add_ai(ai['ai_id'], ai['ai_name'], ai['port'])
                print(f"  - {ai['ai_name']} (ID: {ai['ai_id']}, Port: {ai['port']})")
            
            # 运行锦标赛
            print("\n" + "=" * 60)
            print("开始锦标赛 (Arena Mode)")
            print("=" * 60)
            
            tournament_report = arena.run_tournament()
            
            if not tournament_report:
                return {"error": "锦标赛运行失败"}
            
            # 保存 Arena 的报告
            arena.save_report(tournament_report)
            
            # 5. 生成学习能力分析报告
            learning_report = self._generate_learning_report(test_versions, tournament_report)
            self._save_report(learning_report)
            
            return learning_report
            
        except Exception as e:
            print(f"❌ 运行出错: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
            
    def _generate_learning_report(self, versions: List[int], tournament_report: Dict) -> Dict:
        """基于锦标赛结果生成学习能力报告"""
        print("\n" + "=" * 80)
        print("生成学习能力分析报告...")
        print("=" * 80)
        
        ai_stats = tournament_report.get('ai_stats', {})
        
        # 提取胜率信息
        version_stats = {}
        for v in versions:
            ai_id = f"v{v}"
            if ai_id in ai_stats:
                stats = ai_stats[ai_id]
                total = stats['games_played']
                wins = stats['wins']
                win_rate = wins / total if total > 0 else 0
                
                version_stats[ai_id] = {
                    "wins": wins,
                    "losses": stats['losses'],
                    "draws": stats['draws'],
                    "total_games": total,
                    "win_rate": win_rate,
                    "avg_thinking_time": stats.get('avg_thinking_time', 0)
                }
        
        # 学习趋势分析
        sorted_versions = sorted(versions)
        win_rates = []
        for v in sorted_versions:
            ai_id = f"v{v}"
            if ai_id in version_stats:
                win_rates.append(version_stats[ai_id]['win_rate'])
            else:
                win_rates.append(0)
                
        learning_trend = "unknown"
        if len(win_rates) >= 2:
            if win_rates[-1] > win_rates[0]:
                learning_trend = "improving"
            elif win_rates[-1] < win_rates[0]:
                learning_trend = "declining"
            else:
                learning_trend = "stable"
                
        avg_improvement = 0.0
        if len(win_rates) >= 2:
            avg_improvement = (win_rates[-1] - win_rates[0]) / (len(win_rates) - 1)
            
        print(f"\n📈 学习趋势: {learning_trend}")
        print(f"   首版本 (v{sorted_versions[0]}) 胜率: {win_rates[0]:.2%}")
        print(f"   末版本 (v{sorted_versions[-1]}) 胜率: {win_rates[-1]:.2%}")
        
        return {
            "agent_name": self.agent_name,
            "game": self.game,
            "versions_tested": versions,
            "tournament_id": tournament_report.get('tournament_id'),
            "version_stats": version_stats,
            "learning_analysis": {
                "trend": learning_trend,
                "first_version_win_rate": win_rates[0],
                "last_version_win_rate": win_rates[-1],
                "average_improvement": avg_improvement
            },
            "timestamp": datetime.now().isoformat()
        }

    def _save_report(self, report: Dict):
        """保存报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.agent_name}_{self.game}_validation_{timestamp}.json"
        report_file = self.output_dir / filename
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ 验证报告已保存: {report_file}")

def main():
    parser = argparse.ArgumentParser(description='Agent 学习能力验证器')
    parser.add_argument('--agent', type=str, required=True, help='Agent 名称 (如 gpt-4o_ai)')
    parser.add_argument('--game', type=str, default='gomoku', help='游戏类型')
    parser.add_argument('--versions', type=int, nargs='+', help='指定要测试的版本 (如 1 2 3)')
    parser.add_argument('--rounds', type=int, default=2, help='每对 AI 对战的轮数')
    
    args = parser.parse_args()
    
    base_dir = Path(__file__).parent
    
    validator = AgentValidator(args.agent, args.game, base_dir)
    
    report = validator.validate_learning(
        versions=args.versions,
        rounds_per_match=args.rounds
    )
    
    if 'error' in report:
        print(f"\n❌ 验证失败: {report['error']}")
        sys.exit(1)
    else:
        print("\n✅ 验证完成!")

if __name__ == '__main__':
    main()
