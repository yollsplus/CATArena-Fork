import requests
import json
import os
import shutil
import time
import glob
import argparse


def call_llm_api(prompt, api_url, api_key, model):
    
    if not api_url or not api_key:
        print("LLM API未配置，跳过分析步骤")
        return None
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        data = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a Gomoku AI strategy expert. Analyze game data and provide actionable improvement suggestions."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        response = requests.post(api_url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except Exception as e:
        print(f"LLM API调用失败: {e}")
        return None


def analyze_tournament_data(csv_path, history_path, code_dir=None, agent_dirs=None):
    """
    读取并分析上一轮的比赛数据
    
    Args:
        csv_path: CSV报告路径
        history_path: 历史JSON文件路径
        code_dir: 上一轮所有AI的代码目录 (旧模式)
        agent_dirs: 字典 {ai_name: ai_path}，指定每个AI的代码路径 (新模式)
    
    Returns:
        包含数据摘要的字典
    """
    data_summary = {
        "csv_report": None,
        "history_data": None,
        "ai_codes": {}
    }
    
    # 读取CSV报告
    try:
        if csv_path and os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                csv_content = f.read()
                data_summary["csv_report"] = csv_content
                print(f"  - CSV报告大小: {len(csv_content)} 字符")
    except Exception as e:
        print(f"读取CSV报告失败: {e}")
    
    # 读取完整的历史JSON数据
    try:
        if history_path and os.path.exists(history_path):
            with open(history_path, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
                data_summary["history_data"] = history_data
                total_games = history_data.get('total_games', 0)
                print(f"  - 历史记录总局数: {total_games}")
    except Exception as e:
        print(f"读取历史JSON失败: {e}")
    
    # 读取AI代码
    try:
        # 模式1: 指定了具体的 agent_dirs (推荐)
        if agent_dirs:
            print(f"  - 扫描指定的 {len(agent_dirs)} 个AI代码目录")
            for ai_name, ai_path in agent_dirs.items():
                if os.path.exists(ai_path):
                    ai_code_files = {}
                    # 读取该AI的主要代码文件
                    for root, dirs, files in os.walk(ai_path):
                        for file in files:
                            if file.endswith(('.py', '.sh')):
                                file_path = os.path.join(root, file)
                                rel_path = os.path.relpath(file_path, ai_path)
                                try:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        content = f.read()
                                        if len(content) < 50000:
                                            ai_code_files[rel_path] = content
                                except Exception as e:
                                    print(f"    警告: 无法读取 {file_path}: {e}")
                    
                    if ai_code_files:
                        data_summary["ai_codes"][ai_name] = ai_code_files
                        print(f"    - {ai_name}: {len(ai_code_files)} 个代码文件")
                else:
                    print(f"    警告: 目录不存在 {ai_path}")

        # 模式2: 扫描整个 code_dir (旧模式)
        elif code_dir and os.path.exists(code_dir):
            print(f"  - 扫描代码目录: {code_dir}")
            
            # 1. 检查是否是扁平结构
            root_code_files = [f for f in os.listdir(code_dir) 
                              if os.path.isfile(os.path.join(code_dir, f)) and f.endswith(('.py', '.sh'))]
            
            if root_code_files:
                print(f"    检测到扁平结构，发现 {len(root_code_files)} 个代码文件")
                ai_name = "current_ai" 
                ai_code_files = {}
                for file in root_code_files:
                    file_path = os.path.join(code_dir, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            if len(content) < 50000:
                                ai_code_files[file] = content
                    except Exception as e:
                        print(f"    警告: 无法读取 {file_path}: {e}")
                if ai_code_files:
                    data_summary["ai_codes"][ai_name] = ai_code_files

            # 2. 遍历子目录
            for ai_name in os.listdir(code_dir):
                ai_path = os.path.join(code_dir, ai_name)
                if os.path.isdir(ai_path):
                    ai_code_files = {}
                    for root, dirs, files in os.walk(ai_path):
                        for file in files:
                            if file.endswith(('.py', '.sh')):
                                file_path = os.path.join(root, file)
                                rel_path = os.path.relpath(file_path, ai_path)
                                try:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        content = f.read()
                                        if len(content) < 50000:
                                            ai_code_files[rel_path] = content
                                except Exception as e:
                                    print(f"    警告: 无法读取 {file_path}: {e}")
                    if ai_code_files:
                        data_summary["ai_codes"][ai_name] = ai_code_files
        else:
            print(f"  - 未提供有效的代码目录")
            
    except Exception as e:
        print(f"读取AI代码失败: {e}")
    
    return data_summary


def create_llm_analysis_prompt(data_summary):
    """
    创建用于LLM分析的提示词 (Global Version)
    """
    prompt = """# Gomoku AI Tournament Analysis

Analyze the previous round data and suggest improvements for ALL participating agents.

## Tournament Stats

"""
    
    if data_summary.get("csv_report"):
        prompt += f"```csv\n{data_summary['csv_report']}\n```\n\n"
    
    prompt += """## Game History

"""
    
    if data_summary.get("history_data"):
        history_json = json.dumps(data_summary['history_data'], indent=2, ensure_ascii=False)
        prompt += f"```json\n{history_json}\n```\n\n"
    
    prompt += """## AI Code Implementations

"""
    
    if data_summary.get("ai_codes"):
        for ai_name, code_files in data_summary["ai_codes"].items():
            prompt += f"\n### Agent: {ai_name}\n\n"
            for file_path, content in code_files.items():
                prompt += f"**{file_path}**:\n```python\n{content}\n```\n\n"
    
    prompt += """## Analysis Task

You are the **Chief Architect** for a Gomoku AI Tournament.
Your goal is to analyze the performance of ALL agents, identifying who is acting correctly and who is making mistakes, acting like a coach who guides rather than dictates.

**Your Output must be a single comprehensive report that will be sent to ALL agents.**

**CRITICAL: Do NOT provide the final answer or specific code implementations. Your job is to point out the problems and let the agents decide how to solve them.**

Please structure your analysis as follows:

1. **Tournament Overview**:
   - Who won? Why?
   - What were the common failure patterns across agents?

2. **Performance Review (Who's Acting Right vs. Who's Acting Dumb)**:
   - **The Good**: Which agent showed promising behavior? What concept did they get right? (e.g., "Agent A correctly valued center control.")
   - **The Bad**: Which agent made embarrassing mistakes? What logic was missing? (e.g., "Agent B completely ignored opponent's threats.")
   - Compare the approaches.

3. **Strategic Coaching**:
   - Highlight the *concepts* that are missing (e.g., "You are all playing too passively", "You are missing deep search capabilities").
   - Ask guiding questions to stimulate their thinking (e.g., "How can you detect threats faster?", "Is your evaluation function accurate?").

4. **Focus Areas for Next Round**:
   - List 3 general areas where the team needs to improve.
   - Leave the implementation details open for the agents to decide.

**IMPORTANT**: The agents will receive this EXACT output. Write it as a direct instruction to them. Be tough but fair.
"""
    
    return prompt


def summarize_with_llm(csv_path, history_path, code_dir=None, agent_dirs=None, api_url=None, api_key=None, model=None):
    """
    使用LLM总结上一轮的比赛数据
    """
    print("=" * 60)
    print("开始使用LLM分析上一轮比赛数据 (Global Summary)...")
    print("=" * 60)
    
    # 1. 收集并读取完整数据
    print("\n[1/3] 读取完整比赛数据和AI代码...")
    data_summary = analyze_tournament_data(csv_path, history_path, code_dir, agent_dirs)
    
    # 2. 创建分析提示词
    print("\n[2/3] 创建LLM分析提示词...")
    analysis_prompt = create_llm_analysis_prompt(data_summary)
    
    # 保存提示词以供调试
    prompt_debug_path = "./llm_summary/global_summary_prompt.txt"
    os.makedirs("./llm_summary", exist_ok=True)
    with open(prompt_debug_path, 'w', encoding='utf-8') as f:
        f.write(analysis_prompt)
    print(f"  - 提示词已保存到: {prompt_debug_path}")
    
    # 3. 调用LLM API
    print(f"\n[3/3] 调用LLM API ({model}) 进行分析...")
    llm_response = call_llm_api(analysis_prompt, api_url, api_key, model)
    
    if llm_response is None:
        print("  - LLM分析失败，返回空总结")
        return None
    
    # 4. 保存结果
    try:
        summary_data = {
            "raw_analysis": llm_response,
            "note": "Global LLM strategy analysis"
        }
        
        summary_output_path = "./llm_summary/global_round_summary.json"
        with open(summary_output_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n[SUCCESS] LLM分析完成！总结已保存到: {summary_output_path}")
        return summary_data
        
    except Exception as e:
        print(f"  - 保存LLM响应失败: {e}")
        return None


def generate_global_prompt_with_llm(
    round_num,
    log_path,
    agent_dirs,
    llm_api_url,
    llm_api_key,
    llm_model,
    is_concise=True,
    error_context=None
):
    """
    生成全局统一的提示词
    """
    if round_num <= 1:
        return ""

    # 找到上一轮的日志文件
    try:
        last_round_log_dir = glob.glob(os.path.join(log_path, f'tournament_report_history_*.json'))
        last_round_log_dir = sorted(last_round_log_dir, key=lambda x: int(x.split('_')[-1].split('.')[0]))[-1]
        
        last_round_info = glob.glob(os.path.join(log_path, f'tournament_report_tournament_*.csv'))
        last_round_info = sorted(last_round_info, key=lambda x: int(x.split('_')[-1].split('.')[0]))[-1]
    except IndexError:
        print("找不到上一轮的日志文件")
        return "Error: Could not find previous round logs."

    # 生成全局总结
    llm_summary = summarize_with_llm(
        csv_path=last_round_info,
        history_path=last_round_log_dir,
        agent_dirs=agent_dirs,
        api_url=llm_api_url,
        api_key=llm_api_key,
        model=llm_model
    )

    prompt_data = ""
    
    if error_context:
        prompt_data += f"!!! URGENT FIX REQUIRED !!!\n{error_context}\n\n"

    if llm_summary and "raw_analysis" in llm_summary:
        prompt_data += llm_summary["raw_analysis"]
    else:
        prompt_data += "Analysis failed. Please check logs."

    if is_concise:
        prompt_data += """

IMPORTANT: Based on the GLOBAL analysis above, you MUST now call `replace_python_method` (preferred) or `edit_file` to modify your `ai_service.py` to implement these improvements. Do not just plan, ACT NOW.

## CRITICAL CODING & PERFORMANCE WARNINGS (READ CAREFULLY):

1. **NESTED FUNCTIONS & SCOPE**:
   - If you define a helper function (like `minimax` or `evaluate`) inside `select_best_move`, **DO NOT** call it with `self.`. Call it directly.
   - **WRONG**: `self.minimax(...)` (raises AttributeError)
   - **RIGHT**: `minimax(...)`

2. **PERFORMANCE (TIMEOUT PREVENTION)**:
   - **MAX DEPTH**: Python is slow. Do NOT use depth > 3 for Minimax unless you have highly optimized pruning. Depth 5 WILL TIMEOUT (>10s).
   - **EVALUATION**: Keep evaluation simple. Do not scan the entire board (15x15) at every leaf node.

3. **RECURSION LOGIC**:
   - If your `check_win` function needs the last move coordinates (x, y), make sure your recursive `minimax` passes them along or calculates them correctly.
   - **Common Bug**: Using `x, y` from the outer loop inside a recursive function where `x, y` should be the *current* move being evaluated.
"""

    return prompt_data
def generate_prompt_with_llm(model_name="gpt_4_1", language="", game_env="gomoku", game_suffix="gomoku",
                            game_server="http://127.0.0.1:9000", dir_path="./gomoku/AI_develop",
                            round_num=1, log_path=None, last_round_dir=None,
                            llm_api_url="https://az.gptplus5.com/v1/chat/completions",
                            llm_api_key="sk-2p51ZI79J5X4OL6S343c17F08f3c432395C711608b2eB0D5",
                            llm_model="gpt-4o", summary_output_path="./llm_summary/last_round_summary.json",
                            is_concise=False, error_context=None):
    
    game_env_path = f'./{game_env}'

    # 构建基础提示词
    # 注意: ChatPromptWithLlm.py 只在 Round 2+ 被调用 (当 use_llm_summary=true 时)
    # Round 1 始终使用 ChatPrompt.py
    if round_num == 1:
        raise ValueError("ChatPromptWithLlm.py should not be called for Round 1. Use ChatPrompt.py instead.")

    # 现在一直保持简洁模式
    if is_concise:
        prompt_header = ""
        prompt_footer = ""

    # 初始化 prompt_data（后面会插入分析内容）
    prompt_data = prompt_header

    if error_context:
        prompt_data += f"!!! URGENT FIX REQUIRED !!!\n{error_context}\n\n"

    # 处理多轮学习
    if round_num > 1:
        assert os.path.exists(last_round_dir), f"上一轮的代码不存在: {last_round_dir}"
        
        # 找到上一轮的日志文件
        last_round_log_dir = glob.glob(os.path.join(log_path, f'tournament_report_history_*.json'))
        last_round_log_dir = sorted(last_round_log_dir, key=lambda x: int(x.split('_')[-1].split('.')[0]))[-1]
        
        last_round_info = glob.glob(os.path.join(log_path, f'tournament_report_tournament_*.csv'))
        last_round_info = sorted(last_round_info, key=lambda x: int(x.split('_')[-1].split('.')[0]))[-1]
        
        assert os.path.exists(last_round_log_dir), f"上一轮的日志不存在: {last_round_log_dir}"
        assert os.path.exists(last_round_info), f"上一轮的报告不存在: {last_round_info}"
        
        print("=" * 60)
        print(f"检测到第 {round_num} 轮，开始分析上一轮数据...")
        print(f"  - CSV报告: {last_round_info}")
        print(f"  - 历史记录: {last_round_log_dir}")
        print(f"  - 代码目录: {last_round_dir}")
        print("=" * 60)
        
        # 使用LLM分析总结
        llm_summary = summarize_with_llm(
            csv_path=last_round_info,
            history_path=last_round_log_dir,
            code_dir=last_round_dir,
            api_url=llm_api_url,
            api_key=llm_api_key,
            model=llm_model
        )
        
        # 将LLM总结添加到提示词中（放在最前面，确保Agent先看到分析）
        if llm_summary:
            # 如果有raw_analysis字段，直接用原始文本
            if isinstance(llm_summary, dict) and "raw_analysis" in llm_summary:
                analysis_text = llm_summary["raw_analysis"]
            else:
                # 否则转为JSON
                analysis_text = json.dumps(llm_summary, indent=2, ensure_ascii=False)
            
            if is_concise:
                # 简洁模式：只输出分析内容 + 强制执行指令
                prompt_data = analysis_text + f"""

IMPORTANT: Based on the analysis above, you MUST now call `replace_python_method` (preferred) or `edit_file` to modify `{dir_path}/ai_service.py` to implement these improvements. Do not just plan, ACT NOW.

## CRITICAL CODING & PERFORMANCE WARNINGS (READ CAREFULLY):

1. **NESTED FUNCTIONS & SCOPE**:
   - If you define a helper function (like `minimax` or `evaluate`) inside `select_best_move`, **DO NOT** call it with `self.`. Call it directly.
   - **WRONG**: `self.minimax(...)` (raises AttributeError)
   - **RIGHT**: `minimax(...)`

2. **PERFORMANCE (TIMEOUT PREVENTION)**:
   - **MAX DEPTH**: Python is slow. Do NOT use depth > 3 for Minimax unless you have highly optimized pruning. Depth 5 WILL TIMEOUT (>10s).
   - **EVALUATION**: Keep evaluation simple. Do not scan the entire board (15x15) at every leaf node.

3. **RECURSION LOGIC**:
   - If your `check_win` function needs the last move coordinates (x, y), make sure your recursive `minimax` passes them along or calculates them correctly.
   - **Common Bug**: Using `x, y` from the outer loop inside a recursive function where `x, y` should be the *current* move being evaluated.
"""
        else:
            print("\n[WARNING] LLM分析失败，使用原始数据引用方式...")
            if is_concise:
                prompt_data = f"Analysis failed. Please check logs: {last_round_info}"
            else:
                prompt_data += f"\n##Tournament Data (Analyze This)\n- Report: {last_round_info}\n- History: {last_round_log_dir}\n- Previous code: {last_round_dir}\n"
        
        # 添加执行指令（footer）
        if not is_concise:
            prompt_data += prompt_footer

    # 添加语言要求
    if language and not is_concise:
        prompt_data += f"\n{language} is the language you should use to develop your AI service."

    return prompt_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default="gpt_4_1")
    parser.add_argument("--language", type=str, default="")
    parser.add_argument("--game_env", type=str, default="gomoku")
    parser.add_argument("--game_suffix", type=str, default="gomoku")
    parser.add_argument("--game_server", type=str, default="http://127.0.0.1:9000")
    parser.add_argument("--dir_path", type=str, default="./gomoku/AI_develop")

    # 循环赛轮次
    parser.add_argument("--round_num", type=int, default=1)
    # round > 1时需要提供上一轮的日志和code
    parser.add_argument("--log_path", type=str, default=None)
    parser.add_argument("--last_round_dir", type=str, default=None)

    # LLM相关参数
    parser.add_argument("--llm_api_url", type=str, default="https://az.gptplus5.com/v1/chat/completions", help="LLM API的URL")
    parser.add_argument("--llm_api_key", type=str, default="sk-2p51ZI79J5X4OL6S343c17F08f3c432395C711608b2eB0D5", help="LLM API的密钥")
    parser.add_argument("--llm_model", type=str, default="gpt-4o", help="使用的LLM模型")
    parser.add_argument("--summary_output_path", type=str, default="./llm_summary/last_round_summary.json", help="LLM总结输出路径")
    parser.add_argument("--concise", action="store_true", help="是否只输出简洁的分析内容（不包含指令模板）")


    args = parser.parse_args()

    print(generate_prompt_with_llm(
        model_name=args.model_name,
        language=args.language,
        game_env=args.game_env,
        game_suffix=args.game_suffix,
        game_server=args.game_server,
        dir_path=args.dir_path,
        round_num=args.round_num,
        log_path=args.log_path,
        last_round_dir=args.last_round_dir,
        llm_api_url=args.llm_api_url,
        llm_api_key=args.llm_api_key,
        llm_model=args.llm_model,
        summary_output_path=args.summary_output_path,
        is_concise=args.concise
    ))

