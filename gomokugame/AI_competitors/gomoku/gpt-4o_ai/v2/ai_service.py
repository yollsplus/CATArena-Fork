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
    """Enhanced Gomoku AI with strategic pattern recognition and search algorithms"""
    
    def __init__(self, ai_id: str, ai_name: str = "Strategy AI"):
        self.ai_id = ai_id
        self.ai_name = ai_name
        self.version = "1.0"
        self.description = "A strategic Gomoku AI focused on winning patterns"
        self.capabilities = ["move_selection", "pattern_recognition", "threat_detection"]
        self.active_games = {}
        self.lock = threading.Lock()
        self.BOARD_SIZE = 15
        self.EMPTY = 0
        self.BLACK = 1
        self.WHITE = 2
        self.DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]
        self.MAX_TIME = 8.0

    def select_best_move(self, board: List[List[int]], my_color: int, opponent_color: int) -> Tuple[int, int]:
        if self._is_empty_board(board):
            center = self.BOARD_SIZE // 2
            return (center, center)

        win_move = self._find_winning_move(board, my_color)
        if win_move:
            return win_move

        defend_move = self._find_winning_move(board, opponent_color)
        if defend_move:
            return defend_move

        best_move = self.minimax_with_pruning(board, my_color, opponent_color, depth=3)
        return best_move if best_move else self._get_random_empty_position(board)

    def minimax_with_pruning(self, board: List[List[int]], my_color: int, opponent_color: int, depth: int) -> Optional[Tuple[int, int]]:
        best_score = -float('inf')
        best_move = None
        for move in self._get_empty_positions_near_stones(board):
            score = self._minimax(board, move, depth, my_color, opponent_color, True, -float('inf'), float('inf'))
            if score > best_score:
                best_score = score
                best_move = move
        return best_move

    def _minimax(self, board, move, depth, my_color, opponent_color, is_maximizing, alpha, beta):
        if depth == 0 or self._check_win(board, move[0], move[1], my_color) or self._check_win(board, move[0], move[1], opponent_color):
            return self._evaluate_board(board, my_color, opponent_color)
        if is_maximizing:
            best_value = -float('inf')
            for new_move in self._get_empty_positions_near_stones(board):
                board[new_move[0]][new_move[1]] = my_color
                value = self._minimax(board, new_move, depth-1, my_color, opponent_color, False, alpha, beta)
                board[new_move[0]][new_move[1]] = self.EMPTY
                best_value = max(best_value, value)
                alpha = max(alpha, best_value)
                if beta <= alpha:
                    break
            return best_value
        else:
            min_value = float('inf')
            for new_move in self._get_empty_positions_near_stones(board):
                board[new_move[0]][new_move[1]] = opponent_color
                value = self._minimax(board, new_move, depth-1, my_color, opponent_color, True, alpha, beta)
                board[new_move[0]][new_move[1]] = self.EMPTY
                min_value = min(min_value, value)
                beta = min(beta, min_value)
                if beta <= alpha:
                    break
            return min_value

    def _evaluate_board(self, board, my_color, opponent_color):
        score = 0
        for x in range(self.BOARD_SIZE):
            for y in range(self.BOARD_SIZE):
                if board[x][y] != self.EMPTY:
                    for dx, dy in self.DIRECTIONS:
                        my_count = self._count_consecutive(board, x, y, my_color, dx, dy)
                        opponent_count = self._count_consecutive(board, x, y, opponent_color, dx, dy)

                        if my_count == 5:
                            score += 10000
                        elif my_count == 4:
                            score += 100
                        elif my_count == 3:
                            score += 10

                        if opponent_count == 5:
                            score -= 10000
                        elif opponent_count == 4:
                            score -= 100
                        elif opponent_count == 3:
                            score -= 10
        return score

# Other utility functions (_is_empty_board, _find_winning_move, _check_win, _get_empty_positions_near_stones, and _get_random_empty_position) remain unchanged for this context.

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