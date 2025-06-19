# 

from http import HttpServer
import json
import argparse
import uuid
import time

games = {}

# Konstanta Game
PADDLE_HEIGHT, PADDLE_WIDTH = 100, 20
BALL_RADIUS = 10
WIDTH, HEIGHT = 800, 600

def reset_ball(game):
    game['ball']['x'] = WIDTH / 2
    game['ball']['y'] = HEIGHT / 2
    game['ball']['vx'] = 0
    game['ball']['vy'] = 0
    game['next_serve_time'] = time.time() + 2

def start_ball_movement(game):
    import random
    game['ball']['vx'] = random.choice([-1, 1])
    game['ball']['vy'] = random.choice([-1, 1])

def update_game_state(game_id):
    if game_id not in games: return
    game = games[game_id]
    current_time = time.time()
    if not game['ready']: return
    if game['ball']['vx'] == 0 and current_time > game.get('next_serve_time', 0):
        start_ball_movement(game)
        if 'next_serve_time' in game: del game['next_serve_time']
    
    dt = current_time - game.get('last_update', current_time)
    game['last_update'] = current_time
    game['ball']['x'] += game['ball']['vx'] * dt * 300
    game['ball']['y'] += game['ball']['vy'] * dt * 300

    if game['ball']['y'] - BALL_RADIUS < 0 or game['ball']['y'] + BALL_RADIUS > HEIGHT: game['ball']['vy'] *= -1
    p1 = game['paddles']['1']
    if (game['ball']['vx'] < 0 and p1['x'] <= game['ball']['x'] - BALL_RADIUS <= p1['x'] + PADDLE_WIDTH and p1['y'] <= game['ball']['y'] <= p1['y'] + PADDLE_HEIGHT):
        game['ball']['vx'] *= -1.1; game['ball']['x'] = p1['x'] + PADDLE_WIDTH + BALL_RADIUS
    p2 = game['paddles']['2']
    if (game['ball']['vx'] > 0 and p2['x'] <= game['ball']['x'] + BALL_RADIUS <= p2['x'] + PADDLE_WIDTH and p2['y'] <= game['ball']['y'] <= p2['y'] + PADDLE_HEIGHT):
        game['ball']['vx'] *= -1.1; game['ball']['x'] = p2['x'] - BALL_RADIUS
    if game['ball']['x'] - BALL_RADIUS < 0: game['scores']['2'] += 1; reset_ball(game)
    elif game['ball']['x'] + BALL_RADIUS > WIDTH: game['scores']['1'] += 1; reset_ball(game)

class PongWorker(HttpServer):
    def handle_request(self, method, path, body):
        response_body = {}
        status_code, status_text = 200, "OK"

        try:
            if method == 'POST' and path == '/new_game':
                game_id = str(uuid.uuid4())
                games[game_id] = {
                    'paddles': {
                        '1': {'x': 10, 'y': HEIGHT / 2 - PADDLE_HEIGHT / 2},
                        '2': {'x': WIDTH - 10 - PADDLE_WIDTH, 'y': HEIGHT / 2 - PADDLE_HEIGHT / 2}
                    },
                    'ball': {'x': WIDTH / 2, 'y': HEIGHT / 2, 'vx': 0, 'vy': 0},
                    'scores': {'1': 0, '2': 0}, 'players': 0, 'ready': False, 'last_update': time.time()
                }
                reset_ball(games[game_id])
                response_body = {"status": "ok", "game_id": game_id}

            elif method == 'POST' and path.startswith('/join_game/'):
                game_id = path.split('/')[-1]
                if game_id not in games: raise FileNotFoundError
                game = games[game_id]
                game['players'] += 1
                player_id = str(game['players'])
                if game['players'] == 2: game['ready'] = True; game['next_serve_time'] = time.time() + 2
                response_body = {"status": "ok", "player_id": player_id}
            
            elif method == 'POST' and path == '/move':
                data = json.loads(body)
                game_id, player_id, y = data.get('game_id'), data.get('player_id'), data.get('y')
                if game_id in games:
                    games[game_id]['paddles'][player_id]['y'] = y
                    response_body = {"status": "ok"}
                else: raise FileNotFoundError

            elif method == 'GET' and path.startswith('/state/'):
                game_id = path.split('/')[-1]
                if game_id in games:
                    update_game_state(game_id)
                    response_body = games[game_id]
                else: raise FileNotFoundError
            
            else:
                status_code, status_text = 404, "Not Found"
                response_body = {"error": "Endpoint not found"}

        except FileNotFoundError:
            status_code, status_text = 404, "Not Found"
            response_body = {"error": "Game not found"}
        except Exception as e:
            status_code, status_text = 500, "Internal Server Error"
            response_body = {"error": str(e)}

        response_body_str = json.dumps(response_body)
        response_line = f"HTTP/1.1 {status_code} {status_text}\r\n"
        headers = f"Content-Type: application/json\r\nContent-Length: {len(response_body_str)}\r\nConnection: close\r\n\r\n"
        return (response_line + headers + response_body_str).encode('utf-8')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pong Worker Server")
    parser.add_argument('--port', type=int, default=8001, help='Port for the worker')
    args = parser.parse_args()
    worker = PongWorker(host='127.0.0.1', port=args.port)
    worker.start()
