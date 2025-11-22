#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent 学习能力验证脚本
========================================
让同一个 Agent 的不同版本 (v1, v2, v3...) 两两对战，评估学习效果
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
from typing import Dict, List, Optional, Tuple
import subprocess
import signal
import atexit
import requests


class ServiceManager:
    """服务进程管理器（复用 auto_iteration_manager 的实现）"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.processes = []
        atexit.register(self.cleanup)
    
    def start_game_server(self, game: str = 'gomoku', port: int = 9000) -> bool:
        """启动游戏服务器"""
        print(f"🚀 启动游戏服务器 ({game})...")
        
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
        print("\n🧹 清理服务进程...")
        
        # 1. 清理我们自己启动的进程
        if self.processes:
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
                except Exception as e:
                    pass
            self.processes.clear()
        
        # 2. 强力清理：检查端口占用并杀掉残留进程
        # 端口列表：9000 (server), 12001 (v1), 12002 (v2)
        target_ports = [9000, 12001, 12002]
        
        if sys.platform == 'win32':
            for port in target_ports:
                try:
                    # 查找占用端口的 PID
                    cmd = f"netstat -ano | findstr :{port}"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.stdout:
                        lines = result.stdout.strip().split('\n')
                        for line in lines:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                pid = parts[-1]
                                if pid != '0':
                                    print(f"   🔪 强制杀掉占用端口 {port} 的进程 (PID: {pid})")
                                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
                except Exception:
                    pass
        
        print("✅ 清理完成\n")


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
        print("Agent 学习能力验证器")
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
        """
        验证 Agent 的学习能力
        
        Args:
            versions: 指定要对战的版本列表，None 表示所有版本
            rounds_per_match: 每对 AI 对战的轮数
            
        Returns:
            验证报告
        """
        # 查找版本
        available_versions = self.find_versions()
        
        if not available_versions:
            print("❌ 没有找到任何版本")
            return {"error": "没有找到任何版本"}
        
        print(f"\n✅ 找到 {len(available_versions)} 个版本: {available_versions}")
        
        # 确定要对战的版本
        if versions:
            test_versions = [v for v in versions if v in available_versions]
            if not test_versions:
                print(f"⚠️  指定的版本都不存在")
                return {"error": "指定的版本不存在"}
        else:
            test_versions = available_versions
        
        print(f"📊 将测试 {len(test_versions)} 个版本: {test_versions}")
        
        # 检查代码变化
        self._check_code_changes(test_versions)
        
        if len(test_versions) < 2:
            print("⚠️  至少需要 2 个版本才能对战")
            return {"error": "版本数量不足"}
        
        # 启动游戏服务器
        if not self.service_manager.start_game_server(self.game):
            print("❌ 游戏服务器启动失败")
            return {"error": "游戏服务器启动失败"}
        
        # 生成对战配置
        matches = self._generate_matches(test_versions)
        print(f"\n📋 共需进行 {len(matches)} 场对战")
        
        # 运行所有对战
        results = []
        for i, (v1, v2) in enumerate(matches, 1):
            print(f"\n{'='*60}")
            print(f"对战 {i}/{len(matches)}: v{v1} vs v{v2}")
            print(f"{'='*60}")
            
            match_result = self._run_match(v1, v2, rounds_per_match)
            results.append(match_result)
            
            # 显示结果
            if 'error' not in match_result:
                print(f"✅ v{v1}: {match_result['v1_wins']} 胜")
                print(f"✅ v{v2}: {match_result['v2_wins']} 胜")
                print(f"   平局: {match_result['draws']}")
        
        # 生成报告
        report = self._generate_report(test_versions, results)
        
        # 保存报告
        self._save_report(report)
        
        return report

    def _check_code_changes(self, versions: List[int]):
        """检查不同版本的代码行数变化"""
        print("\n" + "=" * 80)
        print("代码变化检查")
        print("=" * 80)
        
        version_info = []
        
        for v in versions:
            agent_dir = self.base_dir / "AI_competitors" / self.game / self.agent_name / f"v{v}"
            py_files = [f for f in agent_dir.glob("*.py") if f.name != '__init__.py']
            
            if not py_files:
                version_info.append((v, 0, "No file"))
                continue
            
            target_file = py_files[0]
            try:
                with open(target_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    line_count = len(lines)
                    version_info.append((v, line_count, target_file.name))
            except Exception as e:
                version_info.append((v, -1, str(e)))

        print(f"{'版本':<10} {'文件名':<30} {'行数':<10} {'变化':<10}")
        print("-" * 60)
        
        prev_count = None
        for v, count, name in version_info:
            change = "-"
            if prev_count is not None and count != -1 and prev_count != -1:
                diff = count - prev_count
                if diff > 0:
                    change = f"+{diff}"
                elif diff < 0:
                    change = f"{diff}"
                else:
                    change = "0"
            
            print(f"v{v:<9} {name:<30} {count:<10} {change:<10}")
            prev_count = count
            
        unchanged = []
        for i in range(1, len(version_info)):
            curr_v, curr_count, _ = version_info[i]
            prev_v, prev_count, _ = version_info[i-1]
            if curr_count == prev_count and curr_count > 0:
                unchanged.append(f"v{curr_v}")
        
        if unchanged:
            print(f"\n⚠️  警告: 以下版本代码行数与上一版本相同，可能未修改代码: {', '.join(unchanged)}")
        else:
            print("\n✅ 代码行数均有变化")
    
    def _generate_matches(self, versions: List[int]) -> List[Tuple[int, int]]:
        """生成对战配对（所有版本两两对战）"""
        matches = []
        
        # 所有版本两两对战
        for i in range(len(versions)):
            for j in range(i + 1, len(versions)):
                matches.append((versions[i], versions[j]))
        
        return matches
    
    def _debug_ai_service(self, port: int, ai_name: str):
        """调试 AI 服务，发送测试请求并打印错误"""
        print(f"\n🔍 调试 AI 服务: {ai_name} (端口 {port})")
        url = f"http://localhost:{port}/get_move"
        
        # 构造一个简单的测试请求
        payload = {
            "game_id": "debug_test",
            "board": [[0] * 15 for _ in range(15)],
            "current_player": "black"
        }
        
        try:
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code != 200:
                print(f"❌ AI 返回错误状态码: {resp.status_code}")
                try:
                    print(f"❌ 错误详情: {resp.json()}")
                except:
                    print(f"❌ 原始响应: {resp.text}")
            else:
                print(f"✅ AI 响应正常: {resp.json().get('move')}")
        except Exception as e:
            print(f"❌ 请求异常: {e}")

    def _run_match(self, v1: int, v2: int, rounds: int) -> Dict:
        """运行单场对战"""
        # AI 路径
        v1_path = self.base_dir / "AI_competitors" / self.game / self.agent_name / f"v{v1}"
        v2_path = self.base_dir / "AI_competitors" / self.game / self.agent_name / f"v{v2}"
        
        # 启动 AI 服务
        v1_port = 12001
        v2_port = 12002
        
        v1_name = f"{self.agent_name}_v{v1}"
        v2_name = f"{self.agent_name}_v{v2}"
        
        if not self.service_manager.start_ai_service(v1_path, v1_port, v1_name):
            return {"error": f"v{v1} 启动失败"}
        
        if not self.service_manager.start_ai_service(v2_path, v2_port, v2_name):
            return {"error": f"v{v2} 启动失败"}
            
        # 🔍 启动后立即进行健康检查和调试
        self._debug_ai_service(v1_port, v1_name)
        self._debug_ai_service(v2_port, v2_name)
        
        # 运行对战
        try:
            import sys
            arena_path = self.base_dir / f"{self.game}_Arena"
            if str(arena_path) not in sys.path:
                sys.path.insert(0, str(arena_path))
            
            from arena import GomokuArena
            
            game_server_url = "http://localhost:9000"
            timeout = 10
            
            arena = GomokuArena(game_server_url, timeout)
            
            # 添加两个 AI
            v1_id = f"v{v1}"
            v2_id = f"v{v2}"
            
            arena.add_ai(v1_id, v1_name, v1_port)
            arena.add_ai(v2_id, v2_name, v2_port)
            
            # 获取 AI 配置对象
            ai_v1_config = next(ai for ai in arena.ais if ai.ai_id == v1_id)
            ai_v2_config = next(ai for ai in arena.ais if ai.ai_id == v2_id)
            
            # 运行对战
            print(f"\n开始 {rounds} 轮对战...")
            
            v1_wins = 0
            v2_wins = 0
            draws = 0
            games = []
            
            for round_num in range(1, rounds + 1):
                # v1 黑棋 vs v2 白棋
                print(f"  第 {round_num} 轮: {v1_name} (黑) vs {v2_name} (白)")
                game_result = arena.play_game(ai_v1_config, ai_v2_config)
                
                if game_result:
                    # 将 GameResult 对象转换为字典
                    result = {
                        'winner': game_result.winner,
                        'game_id': game_result.game_id,
                        'black': game_result.player_black,
                        'white': game_result.player_white,
                        'end_reason': game_result.end_reason
                    }
                    games.append(result)
                    winner = result.get('winner')
                    if winner == v1_id:
                        v1_wins += 1
                        print(f"    ✅ v{v1} 获胜")
                    elif winner == v2_id:
                        v2_wins += 1
                        print(f"    ✅ v{v2} 获胜")
                    else:
                        draws += 1
                        print(f"    ⚖️  平局")
                
                # v2 黑棋 vs v1 白棋（交换顺序）
                print(f"  第 {round_num} 轮: {v2_name} (黑) vs {v1_name} (白)")
                game_result = arena.play_game(ai_v2_config, ai_v1_config)
                
                if game_result:
                    # 将 GameResult 对象转换为字典
                    result = {
                        'winner': game_result.winner,
                        'game_id': game_result.game_id,
                        'black': game_result.player_black,
                        'white': game_result.player_white,
                        'end_reason': game_result.end_reason
                    }
                    games.append(result)
                    winner = result.get('winner')
                    if winner == v2_id:
                        v2_wins += 1
                        print(f"    ✅ v{v2} 获胜")
                    elif winner == v1_id:
                        v1_wins += 1
                        print(f"    ✅ v{v1} 获胜")
                    else:
                        draws += 1
                        print(f"    ⚖️  平局")
            
            # 停止这两个 AI 服务（为下一场对战让出资源）
            for name, proc, port in list(self.service_manager.processes):
                if port in [v1_port, v2_port]:
                    try:
                        if proc.poll() is None:
                            if sys.platform == 'win32':
                                proc.send_signal(signal.CTRL_BREAK_EVENT)
                            else:
                                proc.terminate()
                        proc.wait(timeout=3)
                    except:
                        pass
                    self.service_manager.processes.remove((name, proc, port))
            
            return {
                "v1": v1,
                "v2": v2,
                "v1_wins": v1_wins,
                "v2_wins": v2_wins,
                "draws": draws,
                "total_games": len(games),
                "games": games,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ 对战出错: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "v1": v1, "v2": v2}
    
    def _generate_report(self, versions: List[int], results: List[Dict]) -> Dict:
        """生成验证报告"""
        print("\n" + "=" * 80)
        print("生成学习能力报告...")
        print("=" * 80)
        
        # 统计每个版本的胜率
        version_stats = {}
        for v in versions:
            version_stats[v] = {
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "total_games": 0
            }
        
        # 统计结果
        for result in results:
            if 'error' in result:
                continue
            
            v1 = result['v1']
            v2 = result['v2']
            
            version_stats[v1]['wins'] += result['v1_wins']
            version_stats[v1]['losses'] += result['v2_wins']
            version_stats[v1]['draws'] += result['draws']
            version_stats[v1]['total_games'] += result['total_games']
            
            version_stats[v2]['wins'] += result['v2_wins']
            version_stats[v2]['losses'] += result['v1_wins']
            version_stats[v2]['draws'] += result['draws']
            version_stats[v2]['total_games'] += result['total_games']
        
        # 计算胜率
        for v, stats in version_stats.items():
            if stats['total_games'] > 0:
                stats['win_rate'] = stats['wins'] / stats['total_games']
            else:
                stats['win_rate'] = 0.0
        
        # 显示统计
        print("\n📊 版本统计:")
        print(f"{'版本':<10} {'总局数':<10} {'胜局':<10} {'败局':<10} {'平局':<10} {'胜率':<10}")
        print("-" * 60)
        for v in sorted(versions):
            stats = version_stats[v]
            print(f"v{v:<9} {stats['total_games']:<10} {stats['wins']:<10} "
                  f"{stats['losses']:<10} {stats['draws']:<10} {stats['win_rate']:.2%}")
        
        # 学习趋势分析
        win_rates = [version_stats[v]['win_rate'] for v in sorted(versions)]
        learning_trend = "improving" if win_rates[-1] > win_rates[0] else "declining"
        
        if len(win_rates) >= 2:
            avg_improvement = (win_rates[-1] - win_rates[0]) / (len(win_rates) - 1)
        else:
            avg_improvement = 0.0
        
        print(f"\n📈 学习趋势: {learning_trend}")
        print(f"   首版本胜率: {win_rates[0]:.2%}")
        print(f"   末版本胜率: {win_rates[-1]:.2%}")
        print(f"   平均提升: {avg_improvement:.2%} / 版本")
        
        report = {
            "agent_name": self.agent_name,
            "game": self.game,
            "versions_tested": versions,
            "version_stats": version_stats,
            "match_results": results,
            "learning_analysis": {
                "trend": learning_trend,
                "first_version_win_rate": win_rates[0],
                "last_version_win_rate": win_rates[-1],
                "average_improvement_per_version": avg_improvement,
                "win_rates_by_version": {f"v{v}": win_rates[i] for i, v in enumerate(sorted(versions))}
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return report
    
    def _save_report(self, report: Dict):
        """保存报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.agent_name}_{self.game}_{timestamp}.json"
        report_file = self.output_dir / filename
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ 报告已保存: {report_file}")


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
