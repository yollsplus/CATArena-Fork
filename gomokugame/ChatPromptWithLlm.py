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
parser.add_argument("--llm_model", type=str, default="gpt-4o", help="使用的LLM模型")
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
            
            # 1. 检查是否是扁平结构（直接包含代码文件，如 AI_develop）
            # 获取目录下所有的 .py 和 .sh 文件
            root_code_files = [f for f in os.listdir(code_dir) 
                              if os.path.isfile(os.path.join(code_dir, f)) and f.endswith(('.py', '.sh'))]
            
            if root_code_files:
                print(f"    检测到扁平结构，发现 {len(root_code_files)} 个代码文件")
                ai_name = "gpt-4o_ai" # 默认作为当前正在开发的AI
                ai_code_files = {}
                
                for file in root_code_files:
                    file_path = os.path.join(code_dir, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            if len(content) < 50000:  # 50KB限制
                                ai_code_files[file] = content
                    except Exception as e:
                        print(f"    警告: 无法读取 {file_path}: {e}")
                
                if ai_code_files:
                    data_summary["ai_codes"][ai_name] = ai_code_files

            # 2. 遍历子目录 (兼容 AI_competitors 这种多AI嵌套结构)
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
    prompt = """# Gomoku AI Tournament Analysis

Analyze the previous round data and suggest improvements for gpt-4o_ai.

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
            prompt += f"\n### {ai_name}\n\n"
            for file_path, content in code_files.items():
                prompt += f"**{file_path}**:\n```python\n{content}\n```\n\n"
    
    prompt += """## Analysis Task

You are a Code Reviewer for the **gpt-4o_ai** project.
Your goal is to guide the developer (Agent) on how to refactor the code to win.

**DO NOT write the full code implementation.**
**DO NOT focus only on high-level tactics (like "play aggressively").**

Instead, analyze the **gpt-4o_ai** source code provided above and point out specific logical flaws or missing features that caused the losses.

Please structure your analysis as follows:

1. **Codebase Diagnosis**:
   - Identify which specific functions or logic blocks in `gpt-4o_ai` are responsible for the poor performance.
   - Example: "The `score_position` function fails to detect broken-4 patterns because the regex `11011` is missing."
   - Example: "The search depth in `minimax` is hardcoded to 1, which is insufficient."

2. **Architectural Suggestions**:
   - Suggest specific algorithmic improvements (e.g., "Implement Alpha-Beta pruning", "Add Zobrist hashing").
   - Explain *how* these changes should be integrated into the existing class structure.

3. **Prioritized Refactoring Plan**:
   - List 3 concrete coding tasks for the Agent to perform in the next iteration.
   - Example: "1. Modify `evaluate_board` to increase weight for opponent's open-3."
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
    
    # 4. 直接保存LLM响应文本（不解析JSON）
    try:
        # LLM返回的是自然语言分析，直接作为raw_analysis保存
        summary_data = {
            "raw_analysis": llm_response,
            "note": "LLM strategy analysis in natural language"
        }
        
        # 保存总结
        with open(summary_output_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n[SUCCESS] LLM分析完成！总结已保存到: {summary_output_path}")
        print(f"  - 分析长度: {len(llm_response)} 字符")
        print("=" * 60)
        
        return summary_data
        
    except Exception as e:
        print(f"  - 保存LLM响应失败: {e}")
        # 保存原始响应以供调试
        raw_output_path = summary_output_path.replace('.json', '_raw.txt')
        with open(raw_output_path, 'w', encoding='utf-8') as f:
            f.write(llm_response)
        print(f"  - 原始响应已保存到: {raw_output_path}")
        return None


# 构建基础提示词
# 注意: ChatPromptWithLlm.py 只在 Round 2+ 被调用 (当 use_llm_summary=true 时)
# Round 1 始终使用 ChatPrompt.py
if round_num == 1:
    raise ValueError("ChatPromptWithLlm.py should not be called for Round 1. Use ChatPrompt.py instead.")

# Round 2+: 基于上一轮优化策略
# 先占位，后面会插入LLM分析
prompt_header = f'''
# Round {round_num}: Improve Your Gomoku AI Strategy

##YOUR MISSION: 
**You MUST call `edit_file` to improve `{dir_path}/ai_service.py` based on the expert analysis below.**

'''

prompt_footer = f'''

##ACTION STEPS:

**STEP 1**: Read your current strategy
```python
read_text_file('{last_round_dir}/ai_service.py')
```

**STEP 2**: Analyze the problems identified above

**STEP 3**: Call `edit_file` NOW to implement improvements
```python
edit_file('{dir_path}/ai_service.py', {{
  "oldText": "...exact code from current strategy...",
  "newText": "...improved code based on analysis..."
}})
```

##CRITICAL REQUIREMENTS:
- You MUST call `edit_file` - don't just read files and stop
- Focus on the specific issues mentioned in the analysis
- Improve threat detection, pattern recognition, and position scoring
- Keep correct indentation (4 spaces per level)
- Use existing helper functions (don't create new ones)

## ⛔ COMMON MISTAKES TO AVOID (READ CAREFULLY)

1.  **Calling Undefined Functions**:
    - **ERROR**: `if self._detect_pattern(...)` (when `_detect_pattern` is NOT defined in the class).
    - **FIX**: You MUST define any helper function you use.
    - **HOW**: Since `replace_python_method` only replaces ONE method, you should define helper functions **inside** `select_best_move` as nested functions.
    - **Example**:
      ```python
      def select_best_move(self, board, ...):
          def _my_helper(x, y):  # Define it HERE
              return ...
          
          # Now you can use it
          val = _my_helper(1, 2)
      ```

2.  **Unreachable Code (Early Return)**:
    - **ERROR**:
      ```python
      if best_move:
          return best_move  # <--- RETURNS HERE
      
      # Minimax code below is NEVER REACHED!
      def minimax(...): ...
      ```
    - **FIX**: Remove the early return if you want to run further logic (like Minimax). Only return when you have the FINAL result.

3.  **Syntax Errors**:
    - Ensure all parentheses are closed.
    - Ensure indentation is consistent (4 spaces).

## 🛠️ TOOL USAGE TIP:
Use `replace_python_method` instead of `edit_file` for safer editing.
It automatically handles indentation for you!

Example:
```python
replace_python_method(
    path='{dir_path}/ai_service.py',
    class_name='GomokuAI',
    method_name='select_best_move',
    new_code=\'\'\'def select_best_move(self, board, my_color, opponent_color):
    # Define helpers inside
    def evaluate(x, y):
        return 0
        
    # Your logic
    # ...
    return best_move\'\'\'
)
```

**START NOW - Read the code, then call replace_python_method to improve it!**
'''.strip()

# 初始化 prompt_data（后面会插入分析内容）
prompt_data = prompt_header


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
        
        # 分析放在最前面
        prompt_data += f"\n##Expert Analysis from Last Round\n\n{analysis_text}\n"
    else:
        print("\n[WARNING] LLM分析失败，使用原始数据引用方式...")
        prompt_data += f"\n##Tournament Data (Analyze This)\n- Report: {last_round_info}\n- History: {last_round_log_dir}\n- Previous code: {last_round_dir}\n"
    
    # 添加执行指令（footer）
    prompt_data += prompt_footer

# 添加语言要求
if language:
    prompt_data += f"\n{language} is the language you should use to develop your AI service."

# 输出最终提示词
print("\n" + "=" * 60)
print("最终提示词:")
print("=" * 60)
print(prompt_data)
