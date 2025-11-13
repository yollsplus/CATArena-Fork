from flask import Flask, request, jsonify
import random

app = Flask(__name__)
AI_ID = "gpt-4o-mini_ai_AI"

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify(status="healthy", ai_id=AI_ID, active_games=0)

@app.route('/info', methods=['GET'])
def ai_info():
    return jsonify(ai_id=AI_ID, name="Gomoku AI", version="1.0", description="An intelligent Gomoku AI", capabilities=["get_move", "join_game", "leave_game", "health_check", "info"])

@app.route('/join_game', methods=['POST'])
def join_game():
    data = request.json
    return jsonify(status="joined", ai_id=AI_ID, game_id=data["game_id"], my_color=data["my_color"])

@app.route('/get_move', methods=['POST'])
def get_move():
    data = request.json
    board = data["board"]
    # Implement a basic strategic AI decision
    move = make_move(board, data["current_player"])
    return jsonify(move=move, ai_id=AI_ID, game_id=data["game_id"], reasoning="Chose a strategic position")

@app.route('/leave_game', methods=['POST'])
def leave_game():
    data = request.json
    return jsonify(status="left", ai_id=AI_ID, game_id=data["game_id"])

def make_move(board, current_player):
    empty_positions = [(i, j) for i in range(len(board)) for j in range(len(board[i])) if board[i][j] == 0]
    # Choose a random empty spot for now, improve this with strategies later
    return random.choice(empty_positions)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    app.run(port=args.port)