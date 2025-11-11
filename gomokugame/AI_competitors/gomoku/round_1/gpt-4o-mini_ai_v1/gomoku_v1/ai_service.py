from flask import Flask, request, jsonify
import random

app = Flask(__name__)
AI_ID = "gpt-4o-mini_ai_AI"

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify(status="healthy", ai_id=AI_ID, active_games=0)

@app.route('/info', methods=['GET'])
def info():
    return jsonify(ai_id=AI_ID, name="Gomoku AI", version="1.0", description="A strategic AI for Gomoku", capabilities=["move selection", "game joining", "basic strategy"])

@app.route('/join_game', methods=['POST'])
def join_game():
    data = request.json
    # Join game logic can be added here
    return jsonify(status="joined", ai_id=AI_ID, game_id=data['game_id'], my_color=data['my_color'])

@app.route('/get_move', methods=['POST'])
def get_move():
    data = request.json
    board = data['board']
    current_player = data['current_player']
    # Implement a basic strategy for move selection
    move = random_move(board)
    return jsonify(move=move, ai_id=AI_ID, game_id=data['game_id'], reasoning="Random move chosen.")

@app.route('/leave_game', methods=['POST'])
def leave_game():
    data = request.json
    return jsonify(status="left", ai_id=AI_ID, game_id=data['game_id'])

def random_move(board):
    empty_positions = [(i, j) for i in range(len(board)) for j in range(len(board[i])) if board[i][j] == 0]
    return random.choice(empty_positions) if empty_positions else None

if __name__ == '__main__':
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Gomoku AI Service')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the service on')
    parser.add_argument('port_positional', nargs='?', type=int, help='Port (positional argument)')
    
    args = parser.parse_args()
    
    # 支持两种格式: --port 12003 或直接 12003
    port = args.port_positional if args.port_positional else args.port
    
    print(f"Starting {AI_ID} on port {port}...")
    app.run(host='0.0.0.0', port=port)