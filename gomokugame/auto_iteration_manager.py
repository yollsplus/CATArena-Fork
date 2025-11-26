#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行请输入
python auto_iteration_manager.py --config my_config.json
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
import requests
import signal
import atexit
import anthropic
from openai import OpenAI
import ChatPrompt
import ChatPromptWithLlm


class ServiceManager:
    """统一管理游戏服务和ai选手们的服务"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.processes = []  # [(name, process, port), ...]

        atexit.register(self.cleanup)
    
    def start_game_server(self, game: str = 'gomoku', port: int = 9000) -> bool:
        print(f"启动游戏服务器 ({game})...")
        
        server_dir = self.base_dir / game
        
        log_dir = self.base_dir / "service_logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{game}_server.log"
        
        try:
            #将输出重定向到文件，避免管道阻塞
            with open(log_file, 'w', encoding='utf-8') as f:
                proc = subprocess.Popen(
                    [sys.executable, 'server.py'],
                    cwd=server_dir,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
                )
            
            self.processes.append(('game_server', proc, port))
            print(f"   日志文件: {log_file}")
            
            if self._wait_for_service(f'http://localhost:{port}/health', timeout=15):
                print(f"游戏服务器已启动 (端口 {port})")
                return True
            else:
                print(f"游戏服务器启动超时")
                print(f"请查看日志: {log_file}")
                return False
                
        except Exception as e:
            print(f"游戏服务器启动失败: {e}")
            return False
    
    def start_ai_service(self, ai_path: Path, port: int, ai_name: str, ai_id: str = None) -> bool:
        """启动 AI 服务（只传 --port 参数）"""
        print(f"启动 AI 服务: {ai_name} (端口 {port})...")
        
        # 找到第一个 .py 文件
        py_files = [f for f in ai_path.glob("*.py") if f.name != '__init__.py']
        
        if not py_files:
            print(f"找不到Python文件")
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
            print(f"日志文件: {log_file}")
            
            if self._wait_for_service(f'http://localhost:{port}/health', timeout=10):
                print(f"{ai_name} 已启动")
                return True
            else:
                if proc.poll() is not None:
                    print(f"AI {ai_name} 启动失败，进程已退出")
                    print(f"请查看日志: {log_file}")
                else:
                    print(f"健康检查超时（可能 /health 端点未实现）")
                return False
                
        except Exception as e:
            print(f"启动失败: {e}")
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
        if not self.processes:
            return
        
        print("清理服务进程...")
        
        for name, proc, port in self.processes:
            try:
                if proc.poll() is None:  #进程还在运行
                    print(f"   停止 {name} (端口 {port})...")
                    
                    if sys.platform == 'win32':
                        # Windows: 发送 CTRL_BREAK_EVENT
                        proc.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        # Linux/Mac: 发送 SIGTERM
                        proc.terminate()
                    
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    
                    print(f"已停止")
            except Exception as e:
                print(f"停止失败: {e}")
        
        self.processes.clear()
        print("清理完成\n")


class AutoIterationManager:
    
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.base_dir = Path(__file__).parent
        self.current_round = 1
        self.iteration_log = []
        
        # Support multiple agents
        if 'agents' in self.config:
            self.agents_config = self.config['agents']
        else:
            # Backward compatibility
            self.agents_config = [self.config['agent']]
            
        self.chat_histories = {agent['model']: [] for agent in self.agents_config}
        
        self.output_dir = self.base_dir / "iteration_contents"
        self.output_dir.mkdir(exist_ok=True)
        
        self.service_manager = ServiceManager(self.base_dir)
        
        print("=" * 80)
        print("CATArena 自动化迭代管理器 (Multi-Agent)")
        print("=" * 80)
        print(f"配置文件: {config_path}")
        print(f"游戏类型: {self.config['game']}")
        print(f"开发Agent: {[a['model'] for a in self.agents_config]}")
        print(f"最大轮次: {self.config['iteration']['max_rounds']}")
        print(f"输出目录: {self.output_dir}")
        print("=" * 80)
    
    def _load_config(self, config_path: str) -> Dict:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def run_full_iteration(self):
        """
        1. Round 1: 生成初始提示词 → 发送给Agent → 自动部署代码 → 运行对战
        2. Round 2+: 分析上轮日志 → 生成增强提示词 → 发送给Agent → 自动部署代码 → 运行对战
        3. 重复直到达到最大轮次
        """
        max_rounds = self.config['iteration']['max_rounds']
        
        for round_num in range(1, max_rounds + 1):
            self.current_round = round_num
            
            print("\n" + "=" * 80)
            print(f"开始 Round {round_num} / {max_rounds}")
            print("=" * 80)
            
            try:
                # Process each agent
                for agent_config in self.agents_config:
                    self._process_agent_round(agent_config, round_num)
                
                # Run Arena
                if self._should_run_arena(round_num):
                    arena_result = self._run_arena(round_num)
                    self._log_round_result(round_num, arena_result)
                else:
                    print(f"Round{round_num}没有可用的AI")

                print(f"\nRound{round_num}完成!")
                
            except Exception as e:
                print(f"\nRound{round_num}出错: {e}")
                import traceback
                traceback.print_exc()
                
                response = input("\n是否继续下一轮？(y/n): ")
                if response.lower() != 'y':
                    break
        
        print("\n" + "=" * 80)
        print("迭代流程完成!")
        print(f"详细日志: {self.output_dir}/iteration_log.json")
        print("=" * 80)

    def _process_agent_round(self, agent_config: Dict, round_num: int):
        agent_model = agent_config['model']
        print(f"\n>>> 处理 Agent: {agent_model} (Round {round_num})")
        
        # Prepare workspace
        workspace_dir = self.base_dir / "gomoku" / "AI_develop_workspace" / f"{agent_model}_ai"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        if round_num == 1:
            # Check if workspace is initialized
            if not any(workspace_dir.iterdir()):
                print(f"⚠️  警告: 工作区为空: {workspace_dir}")
                print(f"   请先运行 'python tools.py init' 初始化工作区")
                return

        prompt = self._generate_prompt(agent_config, round_num, workspace_dir)
        if not prompt: return

        prompt_file = self._save_prompt(prompt, round_num, agent_model)
        
        agent_response = self._send_to_agent_with_validation(agent_config, prompt, round_num, workspace_dir)
        self._save_agent_response(agent_response, round_num, agent_model)
        
        self._auto_deploy_code(agent_config, round_num, workspace_dir)
    
    def _generate_prompt(self, agent_config: Dict, round_num: int, workspace_dir: Path) -> str:
        """
        生成提示词
        """
        agent_model = agent_config['model']
        print(f"\n[1/6]生成 Round {round_num} 提示词 ({agent_model})...")
        
        prompt = ""
        
        if round_num == 1:
            #使用ChatPrompt.py
            prompt = ChatPrompt.generate_prompt(
                model_name=f"{agent_model}_ai",
                round_num=1,
                game_env=self.config['game'],
                game_suffix=self.config['game'],
                dir_path=str(workspace_dir)
            )
        else:
            # Previous round code is in the same workspace
            prev_round_dir = workspace_dir
            
            #Round2+使用ChatPromptWithLlm.py分析上一轮代码和对局记录
            use_llm = self.config['iteration'].get('use_llm_summary', False)
            if use_llm:
                llm_config = self.config['iteration']['llm_summary_config']
                prompt = ChatPromptWithLlm.generate_prompt_with_llm(
                    model_name=f"{agent_model}_ai_v{round_num}",
                    round_num=round_num,
                    log_path='./reports',
                    last_round_dir=str(prev_round_dir),
                    llm_api_url=llm_config['api_url'],
                    llm_api_key=llm_config['api_key'],
                    llm_model=llm_config['model'],
                    dir_path=str(workspace_dir),
                    is_concise=True  #使用简洁模式，只输出分析内容
                )
            else: 
                prompt = ChatPrompt.generate_prompt(
                    model_name=f"{agent_model}_ai_v{round_num}",
                    round_num=round_num,
                    log_path='./reports',
                    last_round_dir=str(prev_round_dir),
                    game_env=self.config['game'],
                    game_suffix=self.config['game'],
                    dir_path=str(workspace_dir)
                )
        
        if not prompt:
            print("警告: 提示词为空")
            return ""
        
        print(f"提示词已生成({len(prompt)}字符)")
        
        return prompt
    
    def _save_prompt(self, prompt: str, round_num: int, agent_model: str) -> Path:
        print(f"\n[2/6] 保存提示词...")
        
        prompt_file = self.output_dir / f"round_{round_num}_{agent_model}_prompt.txt"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(prompt)
        
        print(f"提示词已保存到: {prompt_file}")
        return prompt_file
    
    def _send_to_agent_with_validation(self, agent_config: Dict, initial_prompt: str, round_num: int, workspace_dir: Path) -> Dict[str, Any]:
        """
        发送提示词给Agent，并进行代码语法检查循环
        """
        max_retries = 3
        current_prompt = initial_prompt
        last_response = {}
        
        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"\n[3/6]修复尝试 {attempt}/{max_retries}...")
            
            # 发送请求
            last_response = self._send_to_agent(agent_config, current_prompt, round_num)
            
            # 检查语法
            syntax_error = self._check_code_syntax(workspace_dir)
            
            if syntax_error:
                print(f"检测到语法错误 (尝试 {attempt + 1}/{max_retries + 1}):")
                print(f"   {syntax_error}")
                
                if attempt < max_retries:
                    current_prompt = (
                        f"The code you modified has syntax errors. Please fix them immediately.\n\n"
                        f"Error details:\n{syntax_error}\n\n"
                        f"Use `replace_python_method` to fix the code."
                    )
                    continue
                else:
                    print("达到最大修复次数，放弃修复，继续执行...")
                    return last_response

            # 语法检查通过，进行运行时检查
            runtime_error = self._check_code_runtime(workspace_dir)
            
            if not runtime_error:
                if attempt > 0:
                    print("修复成功！")
                return last_response
            
            print(f"检测到运行时错误 (尝试 {attempt + 1}/{max_retries + 1}):")
            print(f"{runtime_error}")
            #单纯一个runtime error可能不一定能让agent知道自己哪里不符合游戏服务器的规定
            if attempt < max_retries:
                current_prompt = (
                    f"The code you modified has no syntax errors, but it failed to run validation tests.\n"
                    f"This usually means there are runtime errors like NameError, ImportError, or logic errors in your strategy.\n\n"
                    f"Runtime Error details:\n{runtime_error}\n\n"
                    f"Please fix the runtime error immediately."
                )
            else:
                print("达到最大修复次数，放弃修复，继续执行...")
        
        return last_response

    def _check_code_runtime(self, directory: Path) -> Optional[str]:
        """
        检查代码是否能正常运行并响应请求
        Returns:错误信息字符串，如果没有错误则返回 None
        """
        print("正在进行运行时验证...")
        
        # 找到 Python 文件
        py_files = list(directory.glob("*.py"))
        if not py_files:
            return "No Python files found"
        
        # 假设第一个是主文件，或者找 ai_service.py
        main_file = next((f for f in py_files if f.name == 'ai_service.py'), py_files[0])
        
        test_port = 19999 # 使用一个测试端口
        
        import subprocess
        import sys
        import time
        import requests
        import signal
        
        cmd = [sys.executable, str(main_file.name), '--port', str(test_port)]
        
        proc = None
        try:
            # 启动服务
            proc = subprocess.Popen(
                cmd,
                cwd=directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )
            
            # 等待启动 (最多 5 秒)
            start_time = time.time()
            server_ready = False
            while time.time() - start_time < 5:
                if proc.poll() is not None:
                    # 进程已退出
                    break
                try:
                    requests.get(f"http://localhost:{test_port}/health", timeout=1)
                    server_ready = True
                    break
                except:
                    time.sleep(0.5)
            
            if not server_ready:
                # 获取 stderr
                _, stderr = proc.communicate(timeout=1)
                return f"Service failed to start or health check failed.\nStderr: {stderr}"
            
            # 发送测试请求 (模拟 get_move)
            # 构造一个简单的空棋盘
            payload = {
                "game_id": "validation_test",
                "board": [[0] * 15 for _ in range(15)],
                "current_player": "black"
            }
            
            resp = requests.post(f"http://localhost:{test_port}/get_move", json=payload, timeout=5)
            if resp.status_code != 200:
                return f"Service returned error status: {resp.status_code}\nResponse: {resp.text}"
            
            # 验证通过
            return None
            
        except Exception as e:
            return f"Runtime validation exception: {str(e)}"
        finally:
            # 清理进程
            if proc and proc.poll() is None:
                if sys.platform == 'win32':
                    # Windows: 发送 CTRL_BREAK_EVENT
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=2)
                except:
                    proc.kill()

    def _check_code_syntax(self, directory: Path) -> Optional[str]:
        """
        检查目录下 Python 文件的语法
        Returns:
            错误信息字符串，如果没有错误则返回 None
        """
        if not directory.exists():
            return "Directory not found"
            
        py_files = list(directory.glob("*.py"))
        for py_file in py_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    source = f.read()
                compile(source, str(py_file), 'exec')
            except Exception as e:
                return f"File: {py_file.name}\nError: {str(e)}"
        return None

    def _send_to_agent(self, agent_config: Dict, prompt: str, round_num: int) -> Dict[str, Any]:
        """
        发送提示词给Agent
        Returns:
            Agent的响应
        """
        print(f"\n[3/6] 发送提示词给Agent ({agent_config['type']})...")
        
        agent_type = agent_config['type']
        
        try:
            if agent_type == 'openai':
                response = self._send_to_openai(agent_config, prompt)
            elif agent_type == 'anthropic':
                response = self._send_to_anthropic(agent_config, prompt)
            elif agent_type == 'custom':
                response = self._send_to_custom(agent_config, prompt)
            else:
                raise ValueError(f"不支持的Agent类型: {agent_type}")
            
            print(f"✅ Agent响应已接收 ({len(response.get('content', ''))} 字符)")
            return response
            
        except Exception as e:
            print(f"⚠️  发送失败: {e}")
            # 打印完整的错误堆栈
            import traceback
            traceback.print_exc()
            return {
                "error": str(e),
                "content": "",
                "timestamp": datetime.now().isoformat()
            }
    
    def _send_to_openai(self, agent_config: Dict, prompt: str) -> Dict[str, Any]:
        """通过OpenAI API发送（支持 MCP 工具调用）"""
        use_mcp = agent_config.get('use_mcp', False)
        agent_model = agent_config['model']
        
        # Ensure history has system prompt
        if not self.chat_histories[agent_model]:
             self.chat_histories[agent_model] = [{
                "role": "system",
                "content": "You are an expert AI programming assistant. You have access to file system tools. You MUST use 'replace_python_method' (preferred) or 'edit_file' to implement the requirements. Do not just output code in the chat."
            }]

        if use_mcp:
            # 使用 MCP 集成
            from mcp_integration import run_agent_with_mcp_sync
            
            max_iterations = agent_config.get('mcp_max_iterations', 15)
            
            # 传入当前的对话历史
            result = run_agent_with_mcp_sync(
                prompt=prompt,
                api_key=agent_config['api_key'],
                api_url=agent_config.get('base_url', 'https://api.openai.com/v1'),
                model=agent_model,
                workspace_root=self.base_dir,
                max_iterations=max_iterations,
                history=self.chat_histories[agent_model]  # 传入历史
            )
            
            # 更新对话历史
            if 'history' in result:
                self.chat_histories[agent_model] = result['history']
                print(f"   对话历史已更新，当前长度: {len(self.chat_histories[agent_model])}")
            
            result['timestamp'] = datetime.now().isoformat()
            return result
        else:
            
            client = OpenAI(
                api_key=agent_config['api_key'],
                base_url=agent_config.get('base_url')
            )
            
            # 构建消息列表
            # History already initialized above
            messages = list(self.chat_histories[agent_model])
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            response = client.chat.completions.create(
                model=agent_model,
                messages=messages,
                temperature=0.7,
                max_tokens=8000
            )
            
            # 更新历史
            messages.append(response.choices[0].message.model_dump())
            self.chat_histories[agent_model] = messages
            print(f"   对话历史已更新，当前长度: {len(self.chat_histories[agent_model])}")
            
            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": response.usage.model_dump() if response.usage else {},
                "timestamp": datetime.now().isoformat()
            }
    
    def _send_to_anthropic(self, agent_config: Dict, prompt: str) -> Dict[str, Any]:
        """通过Anthropic API发送（支持 MCP 工具调用）"""
        use_mcp = agent_config.get('use_mcp', False)
        agent_model = agent_config['model']
        
        if use_mcp:
            # 使用 MCP 集成
            from mcp_integration import run_agent_with_mcp_sync
            
            max_iterations = agent_config.get('mcp_max_iterations', 15)
            
            result = run_agent_with_mcp_sync(
                prompt=prompt,
                api_key=agent_config['api_key'],
                api_url='https://api.anthropic.com',  # Anthropic API
                model=agent_model,
                workspace_root=self.base_dir,
                max_iterations=max_iterations,
                history=self.chat_histories[agent_model]
            )
            
            if 'history' in result:
                self.chat_histories[agent_model] = result['history']
            
            result['timestamp'] = datetime.now().isoformat()
            return result
        else:
            
            client = anthropic.Anthropic(
                api_key=agent_config['api_key']
            )
            
            if not self.chat_histories[agent_model]:
                messages = [{"role": "user", "content": prompt}]
            else:
                messages = list(self.chat_histories[agent_model])
                messages.append({"role": "user", "content": prompt})
            
            response = client.messages.create(
                model=agent_model,
                max_tokens=8000,
                messages=messages
            )
            
            # 更新历史
            messages.append({"role": "assistant", "content": response.content[0].text})
            self.chat_histories[agent_model] = messages
            
            return {
                "content": response.content[0].text,
                "model": response.model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                },
                "timestamp": datetime.now().isoformat()
            }
    
    def _send_to_custom(self, agent_config: Dict, prompt: str) -> Dict[str, Any]:
        """
        通过自定义API发送
        """
        import requests
        
        url = agent_config['api_url']
        headers = agent_config.get('headers', {})
        headers['Authorization'] = f"Bearer {agent_config['api_key']}"
        
        payload = agent_config.get('payload_template', {})
        payload['prompt'] = prompt
        
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        response.raise_for_status()
        
        return {
            "content": response.json().get('response', ''),
            "raw_response": response.json(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _save_agent_response(self, response: Dict[str, Any], round_num: int, agent_model: str):
        """保存Agent响应"""
        print(f"\n[4/6] 保存Agent响应...")
        
        response_file = self.output_dir / f"round_{round_num}_{agent_model}_response.json"
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Agent响应已保存到: {response_file}")
    
    def _auto_deploy_code(self, agent_config: Dict, round_num: int, source_dir: Path) -> bool:
        """
        自动部署代码：从 workspace 复制到 AI_competitors/gomoku/round_N/<model_name>/v<round_num>/
        """
        agent_model = agent_config['model']
        print(f"\n[5/6] 自动部署代码 ({agent_model})...")
        
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
        
        # 新结构：AI_competitors/gomoku/<model_name>/v<round_num>/
        model_name = f"{agent_model}_ai"
        target_base = self.base_dir / "AI_competitors" / self.config['game'] / model_name
        target_dir = target_base / f"v{round_num}"
        
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
        competitors_dir = self.base_dir / f"AI_competitors/{self.config['game']}"
        
        if not competitors_dir.exists():
            print(f"⚠️  未找到 AI_competitors 目录: {competitors_dir}")
            return False
        
        # 统计可用的 AI（跳过 round_* 旧目录）
        available_ais = []
        for model_dir in competitors_dir.iterdir():
            if model_dir.is_dir() and not model_dir.name.startswith('round_'):
                # 检查是否有版本目录
                version_dirs = list(model_dir.glob('v*'))
                if version_dirs:
                    available_ais.append(model_dir.name)
        
        if not available_ais:
            print(f"⚠️  没有找到可用的 AI")
            return False
        
        print(f"✅ 找到 {len(available_ais)} 个 AI: {available_ais}")
        return True
    
    def _start_all_services(self, round_num: int) -> bool:
        """
        自动启动所有服务
        """
        print("\n" + "=" * 60)
        print("自动启动服务")
        print("=" * 60)
        
        game = self.config['game']
        
        # 1. 启动游戏服务器
        if not self.service_manager.start_game_server(game):
            print("\n❌ 游戏服务器启动失败")
            return False
        
        # 2. 加载 Arena 配置获取 AI 信息
        try:
            arena_path = self.base_dir / f"{game}_Arena"
            config_file = arena_path / "configs" / "round_1_config.json"
            
            with open(config_file, 'r', encoding='utf-8') as f:
                arena_config = json.load(f)
            
            ais = arena_config.get('ais', [])
            
            if not ais:
                print("\n⚠️  配置文件中没有 AI")
                return False
            
            # 3. 启动所有 AI 服务
            success_count = 0
            
            # 获取所有正在开发的模型名称
            developing_models = [a['model'] for a in self.agents_config]
            
            for ai in ais:
                ai_id = ai['ai_id']
                port = ai['port']
                ai_name = ai['ai_name']
                
                # 动态更新迭代 AI 的 ID 和 Name
                # 检查 ai_id 是否包含任何一个正在开发的模型名
                for target_model in developing_models:
                    if target_model in ai_id:
                        # 强制更新为当前轮次版本
                        new_ai_id = f"{target_model}_ai_v{round_num}"
                        print(f"   🔄 动态更新 AI 版本: {ai_id} -> {new_ai_id}")
                        ai_id = new_ai_id
                        ai_name = f"{target_model.upper()} AI v{round_num}"
                        break
                
                # 查找 AI 代码路径
                ai_path = self._find_ai_path(ai_id, round_num)
                
                if not ai_path:
                    print(f"\n⚠️  找不到 {ai_name} ({ai_id}) 的代码路径，跳过")
                    continue
                
                if self.service_manager.start_ai_service(ai_path, port, ai_name, ai_id):
                    success_count += 1
            
            print("\n" + "=" * 60)
            print(f"服务启动完成: {success_count}/{len(ais)} 个 AI 成功启动")
            print("=" * 60)
            
            return success_count > 0
            
        except Exception as e:
            print(f"\n❌ 启动服务时出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _find_ai_path(self, ai_id: str, round_num: int) -> Optional[Path]:
        """查找 AI 代码路径（支持新旧两种结构）"""
        game = self.config['game']
        competitors_dir = self.base_dir / f"AI_competitors/{game}"
        
        if not competitors_dir.exists():
            return None
        
        # 方案1: 新结构 AI_competitors/gomoku/<model>/v<N>/
        for model_dir in competitors_dir.iterdir():
            if model_dir.is_dir() and not model_dir.name.startswith('round_'):
                # 检查模型名是否匹配
                if ai_id in model_dir.name or model_dir.name in ai_id:
                    # 查找最新版本或指定版本
                    version_dirs = sorted(model_dir.glob('v*'), reverse=True)
                    for ver_dir in version_dirs:
                        if ver_dir.is_dir() and any(ver_dir.glob('*.py')):
                            return ver_dir
        
        return None
    
    def _run_arena(self, round_num: int) -> Dict[str, Any]:
        print(f"\n[6/6] 运行 Round {round_num} 对战...")
        
        game = self.config['game']
        
        # 自动启动所有服务
        if not self._start_all_services(round_num):
            return {
                "error": "服务启动失败",
                "timestamp": datetime.now().isoformat()
            }
        
        # 运行对战
        print("\n开始对战...")
        
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
            
            developing_models = [a['model'] for a in self.agents_config]
            
            for ai in selected_ais:
                # 动态更新迭代 AI 的 ID 和 Name
                for target_model in developing_models:
                    if target_model in ai['ai_id']:
                        ai['ai_id'] = f"{target_model}_ai_v{round_num}"
                        ai['ai_name'] = f"{target_model.upper()} AI v{round_num}"
                        break
                
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
                reports_dir = self.base_dir / "reports"
                if not reports_dir.exists():
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
    def _log_round_result(self, round_num: int, arena_result: Dict):
        """记录本轮结果（链接到 Arena 报告）"""
        print(f"\n[7/7] 记录 Round {round_num} 结果...")
        
        self.iteration_log.append({
            "round": round_num,
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

def main():
    parser = argparse.ArgumentParser(description='CATArena自动迭代')
    parser.add_argument('--config', type=str, required=True, help='配置文件路径')
    args = parser.parse_args()
    manager = AutoIterationManager(args.config)
    manager.run_full_iteration()

if __name__ == '__main__':
    main()
