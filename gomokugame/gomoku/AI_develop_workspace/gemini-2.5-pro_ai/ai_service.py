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
    
    def select_best_move(self, board: List[List[int]], my_color: int, 
                            opponent_color: int) -> Tuple[int, int]:
            """
            Selects the best move using Minimax with Alpha-Beta Pruning and a highly
            detailed pattern-based evaluation heuristic.
            """
            import random
            import time
            from collections import defaultdict

            start_time = time.time()

            # --- Immediate Move Checks ---
            if self._is_empty_board(board):
                return (self.BOARD_SIZE // 2, self.BOARD_SIZE // 2)

            win_move = self._find_winning_move(board, my_color)
            if win_move:
                return win_move

            defend_move = self._find_winning_move(board, opponent_color)
            if defend_move:
                return defend_move

            # --- Advanced Evaluation & Minimax ---

            # More detailed pattern scores
            PATTERN_SCORES = {
                # My scores
                (my_color, 5, True): 1000000, # Five in a row
                (my_color, 4, True): 10000,   # Live Four
                (my_color, 4, False): 5000,  # Dead Four
                (my_color, 3, True): 1000,    # Live Three
                (my_color, 3, False): 100,   # Dead Three
                (my_color, 2, True): 50,      # Live Two
                (my_color, 2, False): 10,    # Dead Two
                # Opponent scores (negated, slightly higher for defense)
                (opponent_color, 5, True): -1200000,
                (opponent_color, 4, True): -11000,
                (opponent_color, 4, False): -5500,
                (opponent_color, 3, True): -1100, 
                (opponent_color, 3, False): -110,
                (opponent_color, 2, True): -55,
                (opponent_color, 2, False): -11,
            }

            def evaluate_board_state(board):
                """Evaluates the board by finding patterns and summing their scores."""
                score = 0
                # Directions: horizontal, vertical, diagonal, anti-diagonal
                for r in range(self.BOARD_SIZE):
                    for c in range(self.BOARD_SIZE):
                        if board[r][c] == self.EMPTY:
                            continue

                        color = board[r][c]
                        # Horizontal
                        if c <= self.BOARD_SIZE - 5:
                            score += get_pattern_score([board[r][c+i] for i in range(5)], color)
                        # Vertical
                        if r <= self.BOARD_SIZE - 5:
                            score += get_pattern_score([board[r+i][c] for i in range(5)], color)
                        # Diagonal
                        if r <= self.BOARD_SIZE - 5 and c <= self.BOARD_SIZE - 5:
                            score += get_pattern_score([board[r+i][c+i] for i in range(5)], color)
                        # Anti-diagonal
                        if r <= self.BOARD_SIZE - 5 and c >= 4:
                            score += get_pattern_score([board[r+i][c-i] for i in range(5)], color)
                return score

            def get_pattern_score(window, color):
                """Scores a single 5-stone window."""
                count = window.count(color)
                if count == 0: return 0

                opponent = opponent_color if color == my_color else my_color
                if opponent in window: return 0 # Mixed pattern has no value

                # Check for live/dead ends (by looking at a 6-stone window)
                is_live = False
                # This is a simplification; true live/dead needs context outside the window
                # But for a basic heuristic, we can check if ends are empty *within* the pattern
                if count < 5:
                    if window[0] == self.EMPTY and window[-1] == self.EMPTY:
                        is_live = True

                # A crude check for broken patterns, e.g., X_XX
                if count == 3 and window.count(self.EMPTY) == 2:
                    if window[1] == self.EMPTY or window[3] == self.EMPTY:
                        return PATTERN_SCORES.get((color, 3, False), 0) / 2 # Reduced score for broken three

                return PATTERN_SCORES.get((color, count, is_live), 0)

            def get_candidates(board):
                """Get a list of promising moves, sorted by a quick evaluation."""
                candidates = set()
                for r in range(self.BOARD_SIZE):
                    for c in range(self.BOARD_SIZE):
                        if board[r][c] == self.EMPTY:
                            # Add if there is any stone in a 2-cell radius
                            for dr in range(-2, 3):
                                for dc in range(-2, 3):
                                    if 0 <= r + dr < self.BOARD_SIZE and 0 <= c + dc < self.BOARD_SIZE and board[r+dr][c+dc] != self.EMPTY:
                                        candidates.add((r, c))
                                        break
                                else:
                                    continue
                                break
                return list(candidates) or self._get_random_empty_position(board)

            def minimax(board, depth, alpha, beta, is_maximizing):
                if depth == 0:
                    return evaluate_board_state(board)

                moves = get_candidates(board)
                if not moves: 
                    return evaluate_board_state(board)

                if is_maximizing:
                    max_eval = -float('inf')
                    for r, c in moves:
                        board[r][c] = my_color
                        # Check for a win created by this move
                        if self._check_win(board, r, c, my_color): 
                            board[r][c] = self.EMPTY; return 1000000 - (3-depth)*10

                        evaluation = minimax(board, depth - 1, alpha, beta, False)
                        board[r][c] = self.EMPTY
                        max_eval = max(max_eval, evaluation)
                        alpha = max(alpha, evaluation)
                        if beta <= alpha: break
                    return max_eval
                else: # Minimizing player
                    min_eval = float('inf')
                    for r, c in moves:
                        board[r][c] = opponent_color
                        if self._check_win(board, r, c, opponent_color):
                             board[r][c] = self.EMPTY; return -1000000 + (3-depth)*10

                        evaluation = minimax(board, depth - 1, alpha, beta, True)
                        board[r][c] = self.EMPTY
                        min_eval = min(min_eval, evaluation)
                        beta = min(beta, evaluation)
                        if beta <= alpha: break
                    return min_eval

            # --- Main Search ---
            best_move = (-1, -1)
            best_score = -float('inf')
            search_depth = 2 # Depth 2 is a good balance for performance

            candidate_moves = get_candidates(board)
            if not candidate_moves: return self._get_random_empty_position(board)

            for r, c in candidate_moves:
                 if time.time() - start_time > self.MAX_TIME - 1: # Check for timeout
                    break

                 board[r][c] = my_color
                 score = minimax(board, search_depth, -float('inf'), float('inf'), False)
                 board[r][c] = self.EMPTY

                 # Add a small positional bonus for center
                 score += (7 - abs(r - 7)) + (7 - abs(c - 7))

                 if score > best_score:
                    best_score = score
                    best_move = (r, c)

            return best_move if best_move != (-1, -1) else candidate_moves[0]
        
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