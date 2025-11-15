import requests
import json
import os
import shutil
import time
import glob
import argparse

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
parser.add_argument("--llm_model", type=str, default="gpt-4o-mini", help="使用的LLM模型")
parser.add_argument("--summary_output_path", type=str, default="./last_round_summary.json", help="LLM总结输出路径")


args = parser.parse_args()

dir_path = args.dir_path
model_name = args.model_name
language = args.language
game_env = args.game_env
game_suffix = args.game_suffix
round_num = args.round_num
game_server = args.game_server
log_path = args.log_path
last_round_dir = args.last_round_dir
llm_api_url = args.llm_api_url
llm_api_key = args.llm_api_key
llm_model = args.llm_model
summary_output_path = args.summary_output_path


game_env_path = f'./{game_env}'


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
                    "content": "你是一个五子棋游戏AI策略分析专家，擅长分析对局数据并提炼出关键的战术和策略要点。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        response = requests.post(api_url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except Exception as e:
        print(f"LLM API调用失败: {e}")
        return None


def analyze_tournament_data(csv_path, history_path, code_dir):
    """
    读取并分析上一轮的比赛数据
    
    Args:
        csv_path: CSV报告路径
        history_path: 历史JSON文件路径
        code_dir: 上一轮所有AI的代码目录
    
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
        with open(csv_path, 'r', encoding='utf-8') as f:
            csv_content = f.read()
            data_summary["csv_report"] = csv_content
            print(f"  - CSV报告大小: {len(csv_content)} 字符")
    except Exception as e:
        print(f"读取CSV报告失败: {e}")
    
    # 读取完整的历史JSON数据
    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
            data_summary["history_data"] = history_data
            total_games = history_data.get('total_games', 0)
            print(f"  - 历史记录总局数: {total_games}")
    except Exception as e:
        print(f"读取历史JSON失败: {e}")
    
    # 读取上一轮所有AI的代码
    try:
        if os.path.exists(code_dir):
            print(f"  - 扫描代码目录: {code_dir}")
            # 遍历code_dir下的所有AI目录
            for ai_name in os.listdir(code_dir):
                ai_path = os.path.join(code_dir, ai_name)
                if os.path.isdir(ai_path):
                    ai_code_files = {}
                    # 读取该AI的主要代码文件
                    for root, dirs, files in os.walk(ai_path):
                        for file in files:
                            # 只读取Python文件和shell脚本
                            if file.endswith(('.py', '.sh')):
                                file_path = os.path.join(root, file)
                                rel_path = os.path.relpath(file_path, ai_path)
                                try:
                                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        content = f.read()
                                        # 限制单个文件大小，避免过大
                                        if len(content) < 50000:  # 50KB限制
                                            ai_code_files[rel_path] = content
                                except Exception as e:
                                    print(f"    警告: 无法读取 {file_path}: {e}")
                    
                    if ai_code_files:
                        data_summary["ai_codes"][ai_name] = ai_code_files
                        print(f"    - {ai_name}: {len(ai_code_files)} 个代码文件")
        else:
            print(f"  - 代码目录不存在: {code_dir}")
    except Exception as e:
        print(f"读取AI代码失败: {e}")
    
    return data_summary


def create_llm_analysis_prompt(data_summary):
    """
    创建用于LLM分析的提示词
    
    Args:
        data_summary: 数据摘要字典
    
    Returns:
        提示词字符串
    """
    prompt = """# 五子棋AI对战数据分析任务

你是一个五子棋游戏AI策略分析专家。请分析以下上一轮五子棋AI对战的完整数据，并提炼出关键的战术、策略要点和改进建议。

## 1. 对战报告总览（CSV格式）

这是所有AI选手的胜负统计和性能数据：

"""
    
    if data_summary.get("csv_report"):
        prompt += f"```csv\n{data_summary['csv_report']}\n```\n\n"
    
    prompt += """## 2. 完整对局历史记录

以下是本轮所有对局的详细历史记录（包含每一步落子、游戏状态等）：

"""
    
    if data_summary.get("history_data"):
        # 将完整的历史数据转为JSON字符串
        history_json = json.dumps(data_summary['history_data'], indent=2, ensure_ascii=False)
        prompt += f"```json\n{history_json}\n```\n\n"
    
    prompt += """## 3. 上一轮各AI的代码实现

以下是上一轮所有AI选手的代码实现（包含策略逻辑、算法实现等）：

"""
    
    if data_summary.get("ai_codes"):
        for ai_name, code_files in data_summary["ai_codes"].items():
            prompt += f"\n### AI: {ai_name}\n\n"
            for file_path, content in code_files.items():
                prompt += f"#### 文件: {file_path}\n"
                prompt += f"```python\n{content}\n```\n\n"
    
    prompt += """## 分析要求

请从以下几个维度进行分析并输出JSON格式的结构化总结：

1. **胜负统计分析**
   - 各AI的胜率、平局率、失败率
   - 超时次数和平均思考时间
   - 表现最好和最差的AI

2. **战术模式识别**
   - 常见的开局模式
   - 成功的进攻策略
   - 有效的防守模式
   - 致命的失误类型

3. **代码实现分析**
   - 胜率高的AI使用了什么算法？（如Minimax、Alpha-Beta剪枝、启发式评估等）
   - 优秀的代码设计模式和技巧
   - 代码中的性能优化方法
   - 值得学习的代码片段

4. **策略优缺点**
   - 胜率高的AI使用了哪些策略？
   - 失败的AI有哪些明显的弱点？
   - 什么样的策略组合更有效？

5. **改进建议**
   - 针对开局阶段的建议
   - 针对中盘阶段的建议
   - 针对残局阶段的建议
   - 性能优化建议（思考时间控制）

6. **关键洞察**
   - 从对局历史中发现的规律
   - 值得学习的优秀案例
   - 需要避免的错误案例
   - 从优秀代码中学到的技巧

请以JSON格式输出，结构如下：
```json
{
  "performance_analysis": {
    "best_performers": [],
    "worst_performers": [],
    "timeout_issues": []
  },
  "tactical_patterns": {
    "opening_strategies": [],
    "attack_patterns": [],
    "defense_patterns": [],
    "common_mistakes": []
  },
  "code_analysis": {
    "winning_algorithms": [],
    "good_design_patterns": [],
    "performance_optimizations": [],
    "code_snippets_to_learn": []
  },
  "strategy_insights": {
    "winning_strategies": [],
    "losing_strategies": [],
    "effective_combinations": []
  },
  "improvement_suggestions": {
    "opening_phase": [],
    "middle_phase": [],
    "endgame_phase": [],
    "performance_optimization": []
  },
  "key_insights": {
    "patterns_discovered": [],
    "good_examples": [],
    "bad_examples": [],
    "code_techniques": []
  }
}
```
"""
    
    return prompt


def summarize_with_llm(csv_path, history_path, code_dir, api_url, api_key, model):
    """
    使用LLM总结上一轮的比赛数据
    
    Args:
        csv_path: CSV报告路径
        history_path: 历史JSON文件路径
        code_dir: 上一轮所有AI的代码目录
        api_url: LLM API URL
        api_key: LLM API Key
        model: LLM模型名称
    
    Returns:
        结构化的总结数据（字典格式）
    """
    print("=" * 60)
    print("开始使用LLM分析上一轮比赛数据...")
    print("=" * 60)
    
    # 1. 收集并读取完整数据（包括所有AI的代码）
    print("\n[1/3] 读取完整比赛数据和AI代码...")
    data_summary = analyze_tournament_data(csv_path, history_path, code_dir)
    
    # 2. 创建分析提示词
    print("\n[2/3] 创建LLM分析提示词...")
    analysis_prompt = create_llm_analysis_prompt(data_summary)
    
    # 可选：保存提示词以供调试
    prompt_debug_path = summary_output_path.replace('.json', '_prompt.txt')
    with open(prompt_debug_path, 'w', encoding='utf-8') as f:
        f.write(analysis_prompt)
    print(f"  - 提示词已保存到: {prompt_debug_path}")
    
    # 3. 调用LLM进行分析
    print(f"\n[3/3] 调用LLM API ({model}) 进行分析...")
    llm_response = call_llm_api(analysis_prompt, api_url, api_key, model)
    
    if llm_response is None:
        print("  - LLM分析失败，返回空总结")
        return None
    
    # 4. 解析LLM响应
    try:
        # 尝试从响应中提取JSON
        # LLM可能会在JSON前后添加说明文字，需要提取
        import re
        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if json_match:
            summary_data = json.loads(json_match.group())
        else:
            # 如果没有找到JSON，将整个响应作为文本保存
            summary_data = {
                "raw_analysis": llm_response,
                "note": "LLM未返回JSON格式，这是原始分析文本"
            }
        
        # 保存总结
        with open(summary_output_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n[SUCCESS] LLM分析完成！总结已保存到: {summary_output_path}")
        print("=" * 60)
        
        return summary_data
        
    except Exception as e:
        print(f"  - 解析LLM响应失败: {e}")
        # 保存原始响应以供调试
        raw_output_path = summary_output_path.replace('.json', '_raw.txt')
        with open(raw_output_path, 'w', encoding='utf-8') as f:
            f.write(llm_response)
        print(f"  - 原始响应已保存到: {raw_output_path}")
        return None


# 构建基础提示词
prompt_data = f'''
# Game Development
There is a game project under {game_env_path}. You need to read its source code and develop a game AI. Your AI will compete against other AIs in a tournament, so please make your AI as strategic and competitive as possible.

The final AI should be provided as an HTTP service. You can refer to the guides in {game_env_path}/README.md and {game_env_path}/develop_instruction.md for development instructions.
*The content in {game_env_path}/develop_instruction.md is very important, please read it carefully!*

Please develop your AI service directly under {dir_path}. 

## Expected File Structure
Your final file structure should look like this (NO subdirectories):
```
{dir_path}/
├── ai_service.py       # Your main AI service file (MUST accept --port argument)
├── start_ai.sh         # Startup script
└── requirements.txt    # (Optional) Python dependencies
```

**CRITICAL**: Your `ai_service.py` MUST accept a `--port` command-line argument. It will be started with:
```bash
python ai_service.py --port <port_number>
```


## Script Requirements
Please implement a script to start your AI service, with the name `start_ai.sh` in {dir_path}. The script must accept exactly one argument, which is the port number to run the HTTP service. You should be able to start the AI service on a specified port by running:
```bash
bash start_ai.sh <port>
```
Your AI service should listen on the given port, and you can check its health status by running:
```bash
curl -s http://localhost:<port>/health
```
**Note:**  The script should not accept any other arguments except for the port number. Make sure your AI service uses this port for HTTP requests.


# Other Requirements
Use your model name as a prefix in the AI_ID variable inside your code, i.e., AI_ID = "{model_name}_AI".
**IMPORTANT**: Write all files directly in {dir_path}, do NOT create any subdirectories or folders.
Develop directly in {dir_path} without repeatedly asking for the next step. Report to me only after you have completed the development.

# Access the main server
You can play game of {game_env_path} in at {game_server}. You can play the games with your own AI or any other AI to improve your strategy. 
You can use bash tools to self-play to improve yourself.

# Final Remind
You should write game-play strategy by yourself, do not use any external game engine or API.
Do not set venv environment in your dir, just use python3 from bash.
You should write start_ai.sh in {dir_path} and implement the AI service in {dir_path}. DO NOT MODIFY THE CODE IN {game_env_path}.
'''.strip()


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
    
    # 将LLM总结添加到提示词中
    if llm_summary:
        prompt_data += f"\n\n# Previous Round Analysis Summary\n\n"
        prompt_data += f"The previous round (round {round_num - 1}) has been analyzed by an expert AI strategist. "
        prompt_data += f"Here is the structured summary of key insights and recommendations:\n\n"
        prompt_data += f"```json\n{json.dumps(llm_summary, indent=2, ensure_ascii=False)}\n```\n\n"
        prompt_data += f"**Important**: Please carefully study this analysis and incorporate the winning strategies "
        prompt_data += f"while avoiding the identified mistakes. The improvement suggestions are specifically "
        prompt_data += f"tailored for different game phases (opening, middle, endgame).\n\n"
        prompt_data += f"The complete raw data is available at:\n"
        prompt_data += f"  - Tournament report: {last_round_info}\n"
        prompt_data += f"  - Detailed history: {last_round_log_dir}\n"
        prompt_data += f"  - Previous AI code: {last_round_dir}\n\n"
        prompt_data += f"You may reference the raw data if you need more specific details, "
        prompt_data += f"but the summary above contains the most critical strategic insights.\n\n"
        prompt_data += f"**CRITICAL INSTRUCTION**: You MUST now read the previous code from {last_round_dir}, "
        prompt_data += f"analyze the insights above, and then IMMEDIATELY update the files in {dir_path} with improved strategies. "
        prompt_data += f"DO NOT ask 'Would you like to proceed?' - directly modify the code using edit_file or write_file tools. "
        prompt_data += f"Your task is NOT complete until you have written the improved code to {dir_path}.\n"
    else:
        # 如果LLM分析失败,回退到原始方式
        print("\n[WARNING] LLM分析失败，使用原始数据引用方式...")
        prompt_data += f"\n\nTournament report of last round is in {last_round_info} and detailed history in {last_round_log_dir}. "
        prompt_data += f"The historical records json are quite large. Please use tools `start_interactive_shell` and `run_interactive_shell` to analyze the data efficiently. "
        prompt_data += f"You can use head or tail to pre-view the data, or use python to load this json file.\n"
        prompt_data += f"\n**CRITICAL INSTRUCTION**: The code of the previous round is stored in: {last_round_dir}. "
        prompt_data += f"You MUST read the previous code, analyze the tournament results, and then IMMEDIATELY update the files in {dir_path} with improved strategies. "
        prompt_data += f"DO NOT ask for confirmation - directly modify the code files using edit_file or write_file tools. "
        prompt_data += f"Your task is NOT complete until you have written the improved code to {dir_path}.\n"

# 添加语言要求
if language:
    prompt_data += f"\n{language} is the language you should use to develop your AI service."

# 输出最终提示词
print("\n" + "=" * 60)
print("最终提示词:")
print("=" * 60)
print(prompt_data)
