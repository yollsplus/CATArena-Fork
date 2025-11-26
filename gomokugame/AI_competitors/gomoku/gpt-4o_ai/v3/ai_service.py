#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
五子棋AI服务模板
=================
此模板提供了完整的API框架和基础设施，你只需要专注于实现策略部分。

【重要】你需要实现的核心函数:
- select_best_move(): 选择最佳走法的策略逻辑

【已实现的框架】:
- Flask API服务器和所有端点 (/health, /info, /join_game, /get_move, /leave_game)
- 游戏状态管理
- 基本的辅助函数
"""

import json
import argparse
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from typing import Dict, List, Tuple, Optional

app = Flask(__name__)

class GomokuAI:
    """五子棋AI - 策略优化版本"""
    
    def __init__(self, ai_id: str, ai_name: str = "Strategy AI"):
        # AI基本信息
        self.ai_id = ai_id
        self.ai_name = ai_name
        self.version = "1.0"
        self.description = "A strategic Gomoku AI focused on winning patterns"
        self.capabilities = ["move_selection", "pattern_recognition", "threat_detection"]
        
        # 游戏管理
        self.active_games = {}
        self.lock = threading.Lock()
        
        # 游戏常量
        self.BOARD_SIZE = 15
        self.EMPTY = 0
        self.BLACK = 1
        self.WHITE = 2
        self.DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]  # 横、竖、两个斜向
        
        # AI配置 - 可根据需要调整
        self.MAX_TIME = 8.0  # 最大思考时间8秒
    
    # ========================
    # 核心策略函数 - 需要你实现
    # ========================
    
    def select_best_move(self, board: List[List[int]], my_color: int, opponent_color: int) -> Tuple[int, int]:
        """
        选择最佳走法 - 这是你需要实现的核心策略函数

        参数:
        board: 15x15的棋盘，0=空，1=黑，2=白
        my_color: 我方颜色 (1或2)
        opponent_color: 对手颜色 (1或2)

        返回:
        (row, col): 你选择的走法位置

        提示:
        - 优先考虑能立即获胜的走法
        - 其次考虑防守对手的威胁
        - 然后考虑建立自己的进攻态势
        - 可以使用下面提供的辅助函数
        """
        if self._is_empty_board(board):
            center = self.BOARD_SIZE // 2
            return (center, center)

        # Dynamic depth adjustment based on game phase
        def dynamic_depth_adjustment(board: List[List[int]]) -> int:
            stones_count = sum(row.count(my_color) + row.count(opponent_color) for row in board)
            if stones_count < 20:
                return 2  # Early game
            elif stones_count < 50:
                return 3  # Mid game
            else:
                return 4  # Late game

        # Minimax algorithm with Alpha-Beta pruning
        def minimax(board: List[List[int]], depth: int, alpha: int, beta: int, maximizing_player: bool) -> Tuple[int, Optional[Tuple[int, int]]]:
            if depth == 0 or self._is_terminal_state(board):
                return self._evaluate_board(board, my_color), None

            best_move = None
            if maximizing_player:
                max_eval = -float('inf')
                for move in self._get_empty_positions_near_stones(board):
                    x, y = move
                    board[x][y] = my_color
                    eval = minimax(board, depth - 1, alpha, beta, False)[0]
                    board[x][y] = self.EMPTY
                    if eval > max_eval:
                        max_eval = eval
                        best_move = move
                    alpha = max(alpha, eval)
                    if beta <= alpha:
                        break
                return max_eval, best_move
            else:
                min_eval = float('inf')
                for move in self._get_empty_positions_near_stones(board):
                    x, y = move
                    board[x][y] = opponent_color
                    eval = minimax(board, depth - 1, alpha, beta, True)[0]
                    board[x][y] = self.EMPTY
                    if eval < min_eval:
                        min_eval = eval
                        best_move = move
                    beta = min(beta, eval)
                    if beta <= alpha:
                        break
                return min_eval, best_move

        # Get the best move using adjusted minimax
        search_depth = dynamic_depth_adjustment(board)
        _, best_move = minimax(board, search_depth, -float('inf'), float('inf'), True)
        if best_move:
            return best_move

        # Fallback: random empty position
        return self._get_random_empty_position(board)


    # Adding pattern recognition in the evaluation

    def _evaluate_board(self, board: List[List[int]], color: int) -> int:
        score = 0
        for x in range(self.BOARD_SIZE):
            for y in range(self.BOARD_SIZE):
                if board[x][y] == color:
                    # Pattern recognition for strategic importance
                    score += self._pattern_recognition(board, x, y, color)
        return score

    def _pattern_recognition(self, board: List[List[int]], x: int, y: int, color: int) -> int:
        """Enhanced pattern recognition for strategic scoring"""
        opponent_color = self.BLACK if color == self.WHITE else self.WHITE
        score = 0
        # Recognize open-four and open-three patterns
        for dx, dy in self.DIRECTIONS:
            line = self._get_line(board, x, y, dx, dy)
            if "11110" in line:
                score += 1000  # Open four
            elif "01110" in line or "010110" in line:
                score += 500  # Open three
        return score


    def _get_line(self, board: List[List[int]], x: int, y: int, dx: int, dy: int) -> str:
        """Get a string representation of a line starting from (x, y) moving in direction (dx, dy)"""
        line = ""
        for i in range(-4, 5):  # Scan a line segment
            nx, ny = x + i*dx, y + i*dy
            if 0 <= nx < self.BOARD_SIZE and 0 <= ny < self.BOARD_SIZE:
                line += str(board[nx][ny])
            else:
                line += "#"  # Out of bounds
        return line

    def _is_terminal_state(self, board: List[List[int]]) -> bool:
        # Simplified terminal state function for demonstration
        for x in range(self.BOARD_SIZE):
            for y in range(self.BOARD_SIZE):
                if board[x][y] != self.EMPTY and self._check_win(board, x, y, board[x][y]):
                    return True
        return False


    # Add a basic board evaluation function
        def _evaluate_board(self, board: List[List[int]], color: int) -> int:
            score = 0
            # Evaluate board based on various heuristic metrics
            for x in range(self.BOARD_SIZE):
                for y in range(self.BOARD_SIZE):
                    if board[x][y] == color:
                        # Offensive evaluation
                        for dx, dy in self.DIRECTIONS:
                            count = self._count_consecutive(board, x, y, color, dx, dy)
                            score += count ** 2

                        # Defensive evaluation - consider opponent threats
                        opponent_color = self.BLACK if color == self.WHITE else self.WHITE
                        for dx, dy in self.DIRECTIONS:
                            opponent_count = self._count_consecutive(board, x, y, opponent_color, dx, dy)
                            score -= opponent_count ** 2

            return score

    def _evaluate_position(self, board: List[List[int]], x: int, y: int, my_color: int, opponent_color: int) -> int:
        """评估当前位置得分"""
        score = 0

        # Offensive potential: count own consecutive pieces
        for dx, dy in self.DIRECTIONS:
            own_count = self._count_consecutive(board, x, y, my_color, dx, dy)
            score += own_count ** 2  # Favor longer sequences

        # Defensive need: count opponent's consecutive pieces
        for dx, dy in self.DIRECTIONS:
            opponent_count = self._count_consecutive(board, x, y, opponent_color, dx, dy)
            score += opponent_count ** 2

        return score
        
        # ============================================================
        # END OF STRATEGY IMPLEMENTATION
        # ============================================================
    
    # ========================
    # 辅助函数 - 已实现，可直接使用
    # ========================
    
    def _is_empty_board(self, board: List[List[int]]) -> bool:
        """检查是否为空棋盘"""
        for row in board:
            for cell in row:
                if cell != self.EMPTY:
                    return False
        return True
    
    def _find_winning_move(self, board: List[List[int]], color: int) -> Optional[Tuple[int, int]]:
        """寻找能够立即获胜的走法"""
        for i in range(self.BOARD_SIZE):
            for j in range(self.BOARD_SIZE):
                if board[i][j] == self.EMPTY:
                    # 尝试在这个位置下棋
                    board[i][j] = color
                    if self._check_win(board, i, j, color):
                        board[i][j] = self.EMPTY
                        return (i, j)
                    board[i][j] = self.EMPTY
        return None
    
    def _check_win(self, board: List[List[int]], x: int, y: int, color: int) -> bool:
        """检查指定位置是否形成五连"""
        for dx, dy in self.DIRECTIONS:
            count = 1  # 包含当前位置
            
            # 正向计数
            nx, ny = x + dx, y + dy
            while (0 <= nx < self.BOARD_SIZE and 0 <= ny < self.BOARD_SIZE and 
                   board[nx][ny] == color):
                count += 1
                nx += dx
                ny += dy
            
            # 反向计数
            nx, ny = x - dx, y - dy
            while (0 <= nx < self.BOARD_SIZE and 0 <= ny < self.BOARD_SIZE and 
                   board[nx][ny] == color):
                count += 1
                nx -= dx
                ny -= dy
            
            if count >= 5:
                return True
        
        return False
    
    def _get_empty_positions_near_stones(self, board: List[List[int]], 
                                         distance: int = 2) -> List[Tuple[int, int]]:
        """获取已有棋子附近的空位置"""
        candidates = set()
        
        for i in range(self.BOARD_SIZE):
            for j in range(self.BOARD_SIZE):
                if board[i][j] != self.EMPTY:
                    # 检查周围distance范围内的空位
                    for di in range(-distance, distance + 1):
                        for dj in range(-distance, distance + 1):
                            ni, nj = i + di, j + dj
                            if (0 <= ni < self.BOARD_SIZE and 
                                0 <= nj < self.BOARD_SIZE and 
                                board[ni][nj] == self.EMPTY):
                                candidates.add((ni, nj))
        
        return list(candidates)
    
    def _get_random_empty_position(self, board: List[List[int]]) -> Tuple[int, int]:
        """获取一个随机的空位置"""
        import random
        empty_positions = []
        for i in range(self.BOARD_SIZE):
            for j in range(self.BOARD_SIZE):
                if board[i][j] == self.EMPTY:
                    empty_positions.append((i, j))
        
        return random.choice(empty_positions) if empty_positions else (7, 7)
    
    def _count_consecutive(self, board: List[List[int]], x: int, y: int, 
                          color: int, dx: int, dy: int) -> int:
        """计算从(x,y)开始沿(dx,dy)方向的连续棋子数"""
        count = 0
        nx, ny = x, y
        while (0 <= nx < self.BOARD_SIZE and 0 <= ny < self.BOARD_SIZE and 
               board[nx][ny] == color):
            count += 1
            nx += dx
            ny += dy
        return count
    
    # ========================
    # 游戏接口 - 已实现，无需修改
    # ========================
    
    def get_move(self, game_id: str, board: List[List[int]], current_player: str) -> Tuple[int, int]:
        """获取走法的入口函数"""
        start_time = time.time()
        
        # 转换玩家颜色
        my_color = self.BLACK if current_player == "black" else self.WHITE
        opponent_color = self.WHITE if my_color == self.BLACK else self.BLACK
        
        # 调用策略函数
        move = self.select_best_move(board, my_color, opponent_color)
        
        elapsed_time = time.time() - start_time
        print(f"[{game_id}] AI思考时间: {elapsed_time:.2f}秒, 选择位置: {move}")
        
        return move

# ========================
# Flask API 端点 - 已实现，无需修改
# ========================

ai_instance: Optional[GomokuAI] = None

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "ai_id": ai_instance.ai_id if ai_instance else "unknown",
        "active_games": len(ai_instance.active_games) if ai_instance else 0
    })

@app.route('/info', methods=['GET'])
def get_info():
    """获取AI信息端点"""
    if not ai_instance:
        return jsonify({"error": "AI not initialized"}), 500
    
    return jsonify({
        "ai_id": ai_instance.ai_id,
        "name": ai_instance.ai_name,
        "version": ai_instance.version,
        "description": ai_instance.description,
        "capabilities": ai_instance.capabilities
    })

@app.route('/join_game', methods=['POST'])
def join_game():
    """加入游戏端点"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        my_color = data.get('my_color')
        game_server_url = data.get('game_server_url')
        
        if not all([game_id, my_color, game_server_url]):
            return jsonify({"error": "Missing required parameters"}), 400
        
        if my_color not in ['black', 'white']:
            return jsonify({"error": "Invalid color"}), 400
        
        with ai_instance.lock:
            ai_instance.active_games[game_id] = {
                "my_color": my_color,
                "game_server_url": game_server_url,
                "joined_at": datetime.now().isoformat()
            }
        
        return jsonify({
            "status": "joined",
            "ai_id": ai_instance.ai_id,
            "game_id": game_id,
            "my_color": my_color
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_move', methods=['POST'])
def get_move():
    """获取AI走法端点"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        board = data.get('board')
        current_player = data.get('current_player')
        
        if not all([game_id, board is not None, current_player]):
            return jsonify({"error": "Missing required parameters"}), 400
        
        if current_player not in ['black', 'white']:
            return jsonify({"error": "Invalid current_player"}), 400
        
        # 获取最佳走法
        move = ai_instance.get_move(game_id, board, current_player)
        
        return jsonify({
            "move": list(move),
            "ai_id": ai_instance.ai_id,
            "game_id": game_id,
            "reasoning": f"Strategic move at position {move}"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/leave_game', methods=['POST'])
def leave_game():
    """离开游戏端点"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        if not game_id:
            return jsonify({"error": "Missing game_id"}), 400
        
        with ai_instance.lock:
            if game_id in ai_instance.active_games:
                del ai_instance.active_games[game_id]
        
        return jsonify({
            "status": "left",
            "ai_id": ai_instance.ai_id,
            "game_id": game_id
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# ========================
# 主程序入口 - 已实现，无需修改
# ========================

def main():
    global ai_instance
    
    parser = argparse.ArgumentParser(description='五子棋AI服务器')
    parser.add_argument('--port', type=int, required=True, help='监听端口')
    parser.add_argument('--ai_id', type=str, default='StrategyAI', help='AI ID')
    parser.add_argument('--ai_name', type=str, default='Strategy AI', help='AI名称')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    # 初始化AI实例
    ai_instance = GomokuAI(args.ai_id, args.ai_name)
    
    print(f"启动五子棋AI服务器...")
    print(f"AI ID: {args.ai_id}")
    print(f"AI名称: {args.ai_name}")
    print(f"端口: {args.port}")
    print(f"调试模式: {args.debug}")
    print(f"提示: 核心策略在 select_best_move() 函数中实现")
    
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)

if __name__ == '__main__':
    main()