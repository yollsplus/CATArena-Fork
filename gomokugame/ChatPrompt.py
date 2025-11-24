import requests
import json
import os
import shutil
import time
# for each prompt, I should first create a session, then send the query
import argparse


def generate_prompt(model_name="gpt_4_1", language="", game_env="gomoku", game_suffix="gomoku", 
                   game_server="http://127.0.0.1:9000", dir_path="./gomoku/AI_develop", 
                   round_num=1, log_path=None, last_round_dir=None):
    
    game_env_path = f'./{game_env}'

    if round_num == 1:
        # Round 1: 基于模板开发
        prompt_data = f'''
# Round 1: Implement Gomoku AI Strategy

**CRITICAL**: You MUST use `edit_file` to modify ONLY the TODO section. DO NOT use `write_file`.

**Required steps (DO NOT skip)**:
1. Call `read_text_file('{dir_path}/ai_service.py')` - read template
2. Locate the TODO section marked with `# ====` in `select_best_move()`
3. Call `edit_file('{dir_path}/ai_service.py')` with:
   - `oldText`: The exact TODO section including markers
   - `newText`: Your strategy implementation with:
     * `candidates = self._get_empty_positions_near_stones(board)`
     * Loop through candidates and evaluate each
     * Return best move
   - Keep the fallback `return self._get_random_empty_position(board)`

**Available helper functions**:
- `_find_winning_move(board, color)` - find winning move
- `_check_win(board, x, y, color)` - check if position wins
- `_get_empty_positions_near_stones(board)` - get candidate positions
- `_count_consecutive(board, x, y, color, dx, dy)` - count consecutive stones

**FORBIDDEN**:
✗ Do NOT use `write_file` (will corrupt the file)
✗ Do NOT modify Flask endpoints or helper functions
✗ Do NOT include undefined functions in your code

**Success criteria**:
✓ Use `edit_file` with exact oldText/newText
✓ Code runs without syntax errors
✓ All functions you call are defined

**Reference**: `{dir_path}/README.md` for details'''
    else:
        # Round 2+: 基于上一轮改进
        prompt_data = f'''
# Round {round_num}: Improve Strategy Based on Tournament Results

**STEP 1**: Read your v{round_num-1} strategy
```
read_text_file('{last_round_dir}/ai_service.py')
```

**STEP 2**: Analyze tournament data below:
- Your win rate vs opponents
- Where you lost (opening/mid-game/end-game)
- What tactics won games

**STEP 3**: Call `edit_file` to enhance your strategy - DO THIS NOW

Improvements to make:
1. **Better threat detection** - recognize 4-in-a-row patterns earlier
2. **Smarter positioning** - prioritize center and key intersections
3. **Pattern recognition** - detect live-3, live-4 formations

Example enhancement:
```
edit_file('{dir_path}/ai_service.py', {{
  "oldText": "for candidate in candidates:\\n            x, y = candidate\\n            score = 0",
  "newText": "for candidate in candidates:\\n            x, y = candidate\\n            score = 0\\n            \\n            # Prioritize center positions\\n            center_dist = abs(x - 7) + abs(y - 7)\\n            score += (14 - center_dist) * 2"
}})
```

**YOU MUST CALL edit_file NOW**. Implement concrete improvements based on tournament performance.

**CODE QUALITY REQUIREMENTS**:
✓ Correct Python indentation (4 spaces)
✓ Variables declared before use
✓ Loop variables stay inside loop body
✓ No undefined function calls

**Tournament Results** (analyze win/loss patterns):
'''

    # 添加通用要求
    prompt_data += f'''

## File Requirements
- `{dir_path}/ai_service.py` - Main service (must accept `--port` argument)
- `{dir_path}/start_ai.sh` - Startup script: `bash start_ai.sh <port>`
- `{dir_path}/requirements.txt` - Dependencies (optional)
- AI_ID = "{model_name}_AI"
- No subdirectories, write files directly in {dir_path}

## Rules
- Write strategy yourself (no external engines/APIs)
- Use python3 from bash (no venv)
- Do NOT modify code in {game_env_path}
- Develop directly without asking for next steps
'''.strip()


    import glob

    if round_num  > 1:
        assert os.path.exists(last_round_dir), f"上一轮的代码不存在: {last_round_dir}"
        last_round_log_dir = glob.glob(os.path.join(log_path, f'tournament_report_history_*.json'))
        last_round_log_dir = sorted(last_round_log_dir, key=lambda x: int(x.split('_')[-1].split('.')[0]))[-1]
        last_round_info = glob.glob(os.path.join(log_path, f'*_arena_report_*.csv'))
        last_round_info = sorted(last_round_info, key=lambda x: int(x.split('_')[-1].split('.')[0]))[-1]
        assert os.path.exists(last_round_log_dir), f"上一轮的日志不存在: {last_round_log_dir}"
        
        prompt_data += f"\n\n## Tournament Data\n- Report: {last_round_info}\n- History: {last_round_log_dir}\n- Previous code: {last_round_dir}" 

    if language:
        prompt_data = prompt_data + f"\n{language} is the language you should use to develop your AI service."

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


    args = parser.parse_args()

    print(generate_prompt(
        model_name=args.model_name,
        language=args.language,
        game_env=args.game_env,
        game_suffix=args.game_suffix,
        game_server=args.game_server,
        dir_path=args.dir_path,
        round_num=args.round_num,
        log_path=args.log_path,
        last_round_dir=args.last_round_dir
    ))





