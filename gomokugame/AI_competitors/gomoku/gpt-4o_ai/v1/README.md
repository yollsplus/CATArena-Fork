# 五子棋AI开发指南

## 快速开始

### 1. 理解模板结构

`ai_service.py` 已经为你实现了完整的Flask API框架和游戏管理逻辑。你只需要专注于实现 `select_best_move()` 函数中的策略部分。

### 2. 需要实现的部分

在 `ai_service.py` 中找到以下标记的部分:

```python
# ============================================================
# TODO: IMPLEMENT YOUR STRATEGY HERE
# ============================================================
```

这是你唯一需要修改的地方!

### 3. 可用的辅助函数

模板已经为你提供了以下辅助函数:

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `_is_empty_board(board)` | 检查是否为空棋盘 | board: 15x15棋盘 | bool |
| `_find_winning_move(board, color)` | 寻找立即获胜的走法 | board: 棋盘, color: 颜色 | (row, col)或None |
| `_check_win(board, x, y, color)` | 检查位置是否形成五连 | board: 棋盘, x,y: 位置, color: 颜色 | bool |
| `_get_empty_positions_near_stones(board, distance=2)` | 获取已有棋子附近的空位 | board: 棋盘, distance: 距离 | [(row, col), ...] |
| `_get_random_empty_position(board)` | 获取随机空位置 | board: 棋盘 | (row, col) |
| `_count_consecutive(board, x, y, color, dx, dy)` | 计算连续棋子数 | board: 棋盘, x,y: 起点, color: 颜色, dx,dy: 方向 | int |

### 4. 棋盘数据结构

- **棋盘**: 15x15的二维列表
- **颜色值**:
  - `0` = 空位
  - `1` = 黑棋
  - `2` = 白棋
- **坐标**: (row, col), 范围都是0-14

### 5. 策略实现建议

#### 基础策略框架

```python
def select_best_move(self, board, my_color, opponent_color):
    # 1. 空棋盘下中心
    if self._is_empty_board(board):
        return (7, 7)
    
    # 2. 检查能否立即获胜
    win_move = self._find_winning_move(board, my_color)
    if win_move:
        return win_move
    
    # 3. 检查是否需要防守
    defend_move = self._find_winning_move(board, opponent_color)
    if defend_move:
        return defend_move
    
    # 4. 实现你的策略逻辑
    candidates = self._get_empty_positions_near_stones(board)
    best_move = None
    best_score = -float('inf')
    
    for pos in candidates:
        score = self._evaluate_position(board, pos, my_color)
        if score > best_score:
            best_score = score
            best_move = pos
    
    return best_move if best_move else (7, 7)
```

#### 评估函数示例

```python
def _evaluate_position(self, board, pos, my_color):
    """评估某个位置的价值"""
    x, y = pos
    score = 0
    
    # 临时放置棋子
    board[x][y] = my_color
    
    # 检查四个方向的连续数
    for dx, dy in self.DIRECTIONS:
        # 正向计数
        count_forward = self._count_consecutive(board, x+dx, y+dy, my_color, dx, dy)
        # 反向计数
        count_backward = self._count_consecutive(board, x-dx, y-dy, my_color, -dx, -dy)
        
        total_count = count_forward + count_backward + 1
        
        # 根据连续数给分
        if total_count >= 5:
            score += 100000  # 五连
        elif total_count == 4:
            score += 10000   # 活四
        elif total_count == 3:
            score += 1000    # 活三
        elif total_count == 2:
            score += 100     # 活二
    
    # 恢复棋盘
    board[x][y] = 0
    
    return score
```

### 6. 启动服务

```bash
bash start_ai.sh 5000
```

或者:

```bash
python ai_service.py --port 5000 --ai_id MyAI --ai_name "My Strategy"
```

### 7. 测试你的AI

使用Arena系统测试:

```bash
cd ../../gomoku_Arena
python start_arena.py
```

## 进阶优化方向

### 1. 模式识别
- 识别并形成进攻模式(活三、活四等)
- 识别并封堵对手的威胁模式

### 2. 位置价值评估
- 考虑位置的控制力(中心位置价值高)
- 考虑位置对多个方向的影响

### 3. 搜索深度
- 实现简单的2-3步前瞻
- 使用min-max或alpha-beta剪枝

### 4. 性能优化
- 使用启发式函数快速筛选候选位置
- 缓存评估结果避免重复计算

## 常见问题

### Q: 如何调试我的策略?
A: 在 `select_best_move()` 中添加 `print()` 语句输出调试信息。

### Q: 超时怎么办?
A: 检查 `self.MAX_TIME = 8.0` 配置,确保策略在8秒内完成。

### Q: 如何查看比赛结果?
A: 查看 `gomoku_Arena/logs/` 和 `gomoku_Arena/reports/` 目录。

### Q: Agent总是修改错误的部分?
A: 确保你只在 `# ====` 标记之间修改代码,不要改动其他部分。

## 游戏规则参考

1. **获胜条件**: 在横、竖、斜任意方向形成五个连续的同色棋子
2. **禁手**: 本系统不实现禁手规则
3. **思考时间**: 单步最多10秒,超时判负
4. **平局**: 棋盘下满无人获胜则平局

## 需要帮助?

- 查看 `AI_example` 目录的示例代码
- 阅读 `develop_instruction.md` 了解完整API规范
- 测试时查看Arena日志了解对战情况
