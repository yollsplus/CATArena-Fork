#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CATArena 自动化迭代管理器
========================================
python auto_iteration_manager.py --config config.json --rounds 3
"""

import json
import os
import sys
import time
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import glob


class AutoIterationManager:
    """CATArena自动化迭代管理器"""
    
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.base_dir = Path(__file__).parent
        self.current_round = 1
        self.iteration_log = []
        
        # 创建输出目录
        self.output_dir = self.base_dir / "auto_iteration_output"
        self.output_dir.mkdir(exist_ok=True)
        
        print("=" * 80)
        print("CATArena 自动化迭代管理器")
        print("=" * 80)
        print(f"配置文件: {config_path}")
        print(f"游戏类型: {self.config['game']}")
        print(f"Agent类型: {self.config['agent']['type']}")
        print(f"最大轮次: {self.config['iteration']['max_rounds']}")
        print(f"输出目录: {self.output_dir}")
        print("=" * 80)
    
    def _load_config(self, config_path: str) -> Dict:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def run_full_iteration(self):
        """
        运行完整的迭代流程
        
        流程：
        1. Round 1: 生成初始提示词 → 发送给Agent → 自动部署代码 → 运行对战
        2. Round 2+: 分析上轮日志 → 生成增强提示词 → 发送给Agent → 自动部署代码 → 运行对战
        3. 重复直到达到最大轮次
        
        自动部署：Agent生成的代码在 ./gomoku/AI_develop/ 中，
                  脚本会自动复制到 AI_competitors/gomoku/round_N/<ai_name>/gomoku_v1/
        """
        max_rounds = self.config['iteration']['max_rounds']
        
        for round_num in range(1, max_rounds + 1):
            self.current_round = round_num
            
            print("\n" + "=" * 80)
            print(f"开始 Round {round_num} / {max_rounds}")
            print("=" * 80)
            
            try:
                # Step 1: 生成提示词
                prompt = self._generate_prompt(round_num)
                
                # Step 2: 保存提示词到文件
                prompt_file = self._save_prompt(prompt, round_num)
                
                # Step 3: 发送提示词给Agent
                agent_response = self._send_to_agent(prompt, round_num)
                
                # Step 4: 保存Agent响应
                self._save_agent_response(agent_response, round_num)
                
                # Step 5: 自动部署代码
                deploy_success = self._auto_deploy_code(round_num)
                
                if not deploy_success:
                    print(f"\n⚠️  代码部署失败，跳过 Round {round_num} 对战")
                    continue
                
                # Step 6: 运行对战
                if self._should_run_arena(round_num):
                    arena_result = self._run_arena(round_num)
                    
                    # Step 7: 记录本轮结果
                    self._log_round_result(round_num, prompt_file, agent_response, arena_result)
                else:
                    print(f"⚠️  跳过 Round {round_num} 对战（没有可用的 AI）")
                
                print(f"\n✅ Round {round_num} 完成!")
                
            except Exception as e:
                print(f"\n❌ Round {round_num} 出错: {e}")
                import traceback
                traceback.print_exc()
                
                response = input("\n是否继续下一轮？(y/n): ")
                if response.lower() != 'y':
                    break
        
        # 生成最终报告
        self._generate_final_report()
        
        print("\n" + "=" * 80)
        print("迭代流程完成!")
        print(f"详细日志: {self.output_dir}/iteration_log.json")
        print("=" * 80)
    
    def _generate_prompt(self, round_num: int) -> str:
        """
        生成提示词
        
        Args:
            round_num: 当前轮次
            
        Returns:
            生成的提示词文本
        """
        print(f"\n[1/6] 生成 Round {round_num} 提示词...")
        
        if round_num == 1:
            # Round 1: 使用基础 ChatPrompt.py
            cmd = [
                sys.executable,
                'ChatPrompt.py',
                '--model_name', f"{self.config['agent']['model']}_ai",
                '--round_num', '1',
                '--game_env', self.config['game'],
                '--game_suffix', self.config['game']
            ]
        else:
            # Round 2+: 先检查上一轮的代码目录是否存在
            prev_round_dir = self.base_dir / f"AI_competitors/{self.config['game']}/round_{round_num-1}"
            if not prev_round_dir.exists():
                print(f"\n⚠️  错误: 找不到上一轮的代码目录: {prev_round_dir}")
                print(f"请先完成以下步骤:")
                print(f"  1. 将 Round {round_num-1} 的 Agent 响应中的代码提取出来")
                print(f"  2. 保存到 {prev_round_dir}")
                print(f"  3. 然后再继续运行 Round {round_num}")
                print(f"\n提示: Agent 响应已保存在 ./auto_iteration_output/round_{round_num-1}_response.json")
                return ""
            
            # Round 2+: 使用 ChatPromptWithLlm.py 分析上一轮
            use_llm = self.config['iteration'].get('use_llm_summary', False)
            
            if use_llm:
                llm_config = self.config['iteration']['llm_summary_config']
                cmd = [
                    sys.executable,
                    'ChatPromptWithLlm.py',
                    '--model_name', f"{self.config['agent']['model']}_ai_v{round_num}",
                    '--round_num', str(round_num),
                    '--log_path', './reports',
                    '--last_round_dir', f'./AI_competitors/{self.config["game"]}/round_{round_num-1}',
                    '--llm_api_url', llm_config['api_url'],
                    '--llm_api_key', llm_config['api_key'],
                    '--llm_model', llm_config['model']
                ]
            else:
                cmd = [
                    sys.executable,
                    'ChatPrompt.py',
                    '--model_name', f"{self.config['agent']['model']}_ai_v{round_num}",
                    '--round_num', str(round_num),
                    '--log_path', './reports',
                    '--last_round_dir', f'./AI_competitors/{self.config["game"]}/round_{round_num-1}',
                    '--game_env', self.config['game'],
                    '--game_suffix', self.config['game']
                ]
        
        # 执行命令（设置UTF-8环境变量避免乱码）
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'  # 强制Python子进程使用UTF-8编码
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.base_dir,
            encoding='utf-8',
            errors='ignore',  # 忽略无法解码的字符
            env=env
        )
        
        if result.returncode != 0:
            print(f"⚠️  生成提示词时出现警告:")
            if result.stderr:
                print(result.stderr)
        
        prompt = result.stdout
        if not prompt:
            print("⚠️  警告: 提示词为空")
            print(f"返回码: {result.returncode}")
            print(f"错误输出: {result.stderr}")
            return ""
        
        print(f"✅ 提示词已生成 ({len(prompt)} 字符)")
        
        return prompt
    
    def _save_prompt(self, prompt: str, round_num: int) -> Path:
        """
        保存提示词到文件
        
        Args:
            prompt: 提示词内容
            round_num: 轮次
            
        Returns:
            保存的文件路径
        """
        print(f"\n[2/6] 保存提示词...")
        
        prompt_file = self.output_dir / f"round_{round_num}_prompt.txt"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(prompt)
        
        print(f"✅ 提示词已保存到: {prompt_file}")
        return prompt_file
    
    def _send_to_agent(self, prompt: str, round_num: int) -> Dict[str, Any]:
        """
        发送提示词给Agent
        
        Args:
            prompt: 提示词
            round_num: 轮次
            
        Returns:
            Agent的响应
        """
        print(f"\n[3/6] 发送提示词给Agent ({self.config['agent']['type']})...")
        
        agent_type = self.config['agent']['type']
        
        try:
            if agent_type == 'openai':
                response = self._send_to_openai(prompt)
            elif agent_type == 'anthropic':
                response = self._send_to_anthropic(prompt)
            elif agent_type == 'custom':
                response = self._send_to_custom(prompt)
            else:
                raise ValueError(f"不支持的Agent类型: {agent_type}")
            
            print(f"✅ Agent响应已接收 ({len(response.get('content', ''))} 字符)")
            return response
            
        except Exception as e:
            print(f"⚠️  发送失败: {e}")
            return {
                "error": str(e),
                "content": "",
                "timestamp": datetime.now().isoformat()
            }
    
    def _send_to_openai(self, prompt: str) -> Dict[str, Any]:
        """通过OpenAI API发送（支持 MCP 工具调用）"""
        use_mcp = self.config['agent'].get('use_mcp', False)
        
        if use_mcp:
            # 使用 MCP 集成
            from mcp_integration import run_agent_with_mcp_sync
            
            max_iterations = self.config['agent'].get('mcp_max_iterations', 15)
            
            result = run_agent_with_mcp_sync(
                prompt=prompt,
                api_key=self.config['agent']['api_key'],
                api_url=self.config['agent'].get('base_url', 'https://api.openai.com/v1'),
                model=self.config['agent']['model'],
                workspace_root=self.base_dir,
                max_iterations=max_iterations
            )
            
            result['timestamp'] = datetime.now().isoformat()
            return result
        else:
            # 原始的简单 API 调用（无工具）
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError("需要安装 openai 库: pip install openai")
            
            client = OpenAI(
                api_key=self.config['agent']['api_key'],
                base_url=self.config['agent'].get('base_url')
            )
            
            response = client.chat.completions.create(
                model=self.config['agent']['model'],
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert AI programming assistant. Generate complete, production-ready code."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=8000
            )
            
            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": response.usage.model_dump() if response.usage else {},
                "timestamp": datetime.now().isoformat()
            }
    
    def _send_to_anthropic(self, prompt: str) -> Dict[str, Any]:
        """通过Anthropic API发送（支持 MCP 工具调用）"""
        use_mcp = self.config['agent'].get('use_mcp', False)
        
        if use_mcp:
            # 使用 MCP 集成
            from mcp_integration import run_agent_with_mcp_sync
            
            max_iterations = self.config['agent'].get('mcp_max_iterations', 15)
            
            result = run_agent_with_mcp_sync(
                prompt=prompt,
                api_key=self.config['agent']['api_key'],
                api_url='https://api.anthropic.com',  # Anthropic API
                model=self.config['agent']['model'],
                workspace_root=self.base_dir,
                max_iterations=max_iterations
            )
            
            result['timestamp'] = datetime.now().isoformat()
            return result
        else:
            # 原始的简单 API 调用（无工具）
            try:
                import anthropic
            except ImportError:
                raise ImportError("需要安装 anthropic 库: pip install anthropic")
            
            client = anthropic.Anthropic(
                api_key=self.config['agent']['api_key']
            )
            
            response = client.messages.create(
                model=self.config['agent']['model'],
                max_tokens=8000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            return {
                "content": response.content[0].text,
                "model": response.model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                },
                "timestamp": datetime.now().isoformat()
            }
    
    def _send_to_custom(self, prompt: str) -> Dict[str, Any]:
        """
        通过自定义API发送
        
        配置示例:
        {
            "agent": {
                "type": "custom",
                "api_url": "http://your-agent-api.com/generate",
                "api_key": "xxx",
                "headers": {...},
                "payload_template": {...}
            }
        }
        """
        import requests
        
        url = self.config['agent']['api_url']
        headers = self.config['agent'].get('headers', {})
        headers['Authorization'] = f"Bearer {self.config['agent']['api_key']}"
        
        payload = self.config['agent'].get('payload_template', {})
        payload['prompt'] = prompt
        
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        response.raise_for_status()
        
        return {
            "content": response.json().get('response', ''),
            "raw_response": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _save_agent_response(self, response: Dict[str, Any], round_num: int):
        """保存Agent响应"""
        print(f"\n[4/6] 保存Agent响应...")
        
        response_file = self.output_dir / f"round_{round_num}_agent_response.json"
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Agent响应已保存到: {response_file}")
    
    def _auto_deploy_code(self, round_num: int) -> bool:
        """
        自动部署代码：从 ./gomoku/AI_develop/ 复制到 AI_competitors/gomoku/round_N/
        
        Args:
            round_num: 当前轮次
            
        Returns:
            是否部署成功
        """
        print(f"\n[5/6] 自动部署代码...")
        
        # 源目录：Agent 生成代码的位置
        source_dir = self.base_dir / "gomoku" / "AI_develop"
        
        if not source_dir.exists():
            print(f"⚠️  错误: 源目录不存在: {source_dir}")
            return False
        
        # 检查是否有 Python 文件
        py_files = list(source_dir.glob("*.py"))
        if not py_files:
            print(f"⚠️  错误: 源目录中没有 Python 文件: {source_dir}")
            return False
        
        print(f"✅ 找到 {len(py_files)} 个 Python 文件:")
        for f in py_files:
            print(f"   - {f.name}")
        
        # 目标目录：AI_competitors/gomoku/round_N/<ai_name>/
        ai_name = f"{self.config['agent']['model']}_ai_v{round_num}"
        target_base = self.base_dir / "AI_competitors" / self.config['game'] / f"round_{round_num}"
        target_dir = target_base / ai_name / f"{self.config['game']}_v1"
        
        # 创建目标目录
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ 创建目标目录: {target_dir}")
        
        # 复制所有文件
        import shutil
        copied_files = []
        
        for item in source_dir.iterdir():
            target_path = target_dir / item.name
            
            if item.is_file():
                shutil.copy2(item, target_path)
                copied_files.append(item.name)
                print(f"   复制: {item.name}")
            elif item.is_dir():
                if target_path.exists():
                    shutil.rmtree(target_path)
                shutil.copytree(item, target_path)
                copied_files.append(f"{item.name}/ (目录)")
                print(f"   复制: {item.name}/ (目录)")
        
        print(f"✅ 成功复制 {len(copied_files)} 个文件/目录到 {target_dir}")
        
        # 检查必要文件
        required_files = ['ai_service.py', 'start_ai.sh']
        missing_files = [f for f in required_files if not (target_dir / f).exists()]
        
        if missing_files:
            print(f"⚠️  警告: 缺少必要文件: {missing_files}")
            print(f"   但仍然继续部署...")
        
        return True
    
    def _should_run_arena(self, round_num: int) -> bool:
        """检查是否应该运行对战"""
        # 检查是否有AI代码部署
        ai_dir = self.base_dir / f"AI_competitors/{self.config['game']}/round_{round_num}"
        
        if not ai_dir.exists():
            print(f"⚠️  未找到 Round {round_num} 的AI代码目录: {ai_dir}")
            return False
        
        # 检查是否有AI子目录
        ai_subdirs = [d for d in ai_dir.iterdir() if d.is_dir()]
        if not ai_subdirs:
            print(f"⚠️  Round {round_num} 没有AI代码")
            return False
        
        print(f"✅ 找到 {len(ai_subdirs)} 个AI: {[d.name for d in ai_subdirs]}")
        return True
    
    def _run_arena(self, round_num: int) -> Dict[str, Any]:
        """
        运行对战竞技场
        
        Args:
            round_num: 轮次
            
        Returns:
            对战结果信息
        """
        print(f"\n[6/6] 运行 Round {round_num} 对战...")
        
        game = self.config['game']
        
        # 运行对战
        print("开始对战...")
        
        try:
            # 导入 arena 模块
            import sys
            arena_path = self.base_dir / f"{game}_Arena"
            if str(arena_path) not in sys.path:
                sys.path.insert(0, str(arena_path))
            
            from arena import GomokuArena  # type: ignore
            from config import ArenaConfig  # type: ignore
            
            # 加载配置
            config_file = arena_path / "configs" / "round_1_config.json"
            print(f"使用配置文件: {config_file}")
            
            config = ArenaConfig(str(config_file))
            
            # 创建 Arena
            game_server_url = config.get_game_server_url()
            timeout = config.get_timeout()
            tournament_config = config.get_tournament_config()
            rounds_per_match = tournament_config.get('rounds_per_match', 2)
            
            arena = GomokuArena(game_server_url, timeout)
            
            # 添加所有 AI
            selected_ais = config.get_ais()
            
            if not selected_ais:
                print("⚠️  错误: 没有可用的AI")
                return {
                    "error": "没有可用的AI",
                    "timestamp": datetime.now().isoformat()
                }
            
            print("=" * 60)
            print(f"游戏服务器: {game_server_url}")
            print(f"超时时间: {timeout}秒")
            print(f"每对AI对战轮数: {rounds_per_match}")
            print(f"参赛AI数量: {len(selected_ais)}")
            
            for ai in selected_ais:
                arena.add_ai(ai['ai_id'], ai['ai_name'], ai['port'])
                print(f"  - {ai['ai_name']} (端口: {ai['port']})")
            
            print("\n开始锦标赛...")
            
            # 运行锦标赛
            report = arena.run_tournament()
            
            if report:
                # 保存报告
                arena.save_report(report)
                
                print("\n" + "=" * 60)
                print("✅ 锦标赛完成！")
                print("=" * 60)
                
                # 查找报告文件
                reports_dir = self.base_dir / f"{game}_Arena/reports"
                csv_reports = list(reports_dir.glob("tournament_report_tournament_*.csv"))
                json_reports = list(reports_dir.glob("tournament_report_history_*.json"))
                
                latest_csv = max(csv_reports, key=os.path.getctime) if csv_reports else None
                latest_json = max(json_reports, key=os.path.getctime) if json_reports else None
                
                return {
                    "csv_report": str(latest_csv) if latest_csv else None,
                    "json_report": str(latest_json) if latest_json else None,
                    "tournament_id": report.get('tournament_id'),
                    "total_games": report.get('total_games'),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                print("⚠️  锦标赛运行失败")
                return {
                    "error": "锦标赛运行失败",
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            print(f"❌ 运行对战时出错: {e}")
            import traceback
            traceback.print_exc()
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    def _log_round_result(self, round_num: int, prompt_file: Path, 
                         agent_response: Dict, arena_result: Dict):
        """记录本轮结果（链接到 Arena 报告）"""
        print(f"\n[7/7] 记录 Round {round_num} 结果...")
        
        self.iteration_log.append({
            "round": round_num,
            "prompt_file": str(prompt_file),
            "agent_response_file": str(self.output_dir / f"round_{round_num}_agent_response.json"),
            "arena_reports": {
                "csv": arena_result.get("csv_report"),
                "json": arena_result.get("json_report"),
                "tournament_id": arena_result.get("tournament_id")
            },
            "timestamp": datetime.now().isoformat()
        })
        
        # 保存简化的迭代日志（只记录文件路径，不复制内容）
        log_file = self.output_dir / "iteration_log.json"
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(self.iteration_log, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 结果已记录")
        print(f"   迭代日志: {log_file}")
        if arena_result.get("csv_report"):
            print(f"   Arena报告: {arena_result.get('csv_report')}")
            print(f"   详细历史: {arena_result.get('json_report')}")
    
    def _generate_final_report(self):
        """生成最终评测报告"""
        print("\n" + "=" * 80)
        print("生成最终评测报告...")
        print("=" * 80)
        
        report = {
            "evaluation_summary": {
                "total_rounds": len(self.iteration_log),
                "game": self.config['game'],
                "agent_type": self.config['agent']['type'],
                "agent_model": self.config['agent']['model'],
                "start_time": self.iteration_log[0]['timestamp'] if self.iteration_log else None,
                "end_time": self.iteration_log[-1]['timestamp'] if self.iteration_log else None
            },
            "rounds": self.iteration_log,
            "config": self.config
        }
        
        report_file = self.output_dir / "final_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 最终报告已保存到: {report_file}")


def main():
    parser = argparse.ArgumentParser(description='CATArena 自动化迭代管理器')
    parser.add_argument('--config', type=str, required=True, help='配置文件路径')
    parser.add_argument('--rounds', type=int, help='覆盖配置文件中的最大轮次')
    
    args = parser.parse_args()
    
    # 加载并可能覆盖配置
    if args.rounds:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
        config['iteration']['max_rounds'] = args.rounds
        
        # 保存临时配置
        temp_config = Path(args.config).parent / 'temp_config.json'
        with open(temp_config, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        manager = AutoIterationManager(str(temp_config))
    else:
        manager = AutoIterationManager(args.config)
    
    # 运行迭代
    manager.run_full_iteration()


if __name__ == '__main__':
    main()
