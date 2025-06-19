# pong_worker.py

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import argparse
import uuid
import time
import threading

# State game akan disimpan di sini, diakses oleh semua request
games = {}
games_lock = threading.Lock()

# Konstanta Game
PADDLE_HEIGHT, PADDLE_WIDTH = 100, 20
BALL_RADIUS = 10
WIDTH, HEIGHT = 800, 600

def reset_ball(game):
    game['ball'].update({'x': WIDTH / 2, 'y': HEIGHT / 2, 'vx': 0, 'vy': 0})
    game['next_serve_time'] = time.time() + 2

def start_ball_movement(game):
    import random
    game['ball']['vx'] = random.choice([-1, 1])
    game['ball']['vy'] = random.choice([-1, 1])

def update_game_state(game_id):
    with games_lock:
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
        p1 = game['paddles']['1']; p2 = game['paddles']['2']
        if (game['ball']['vx'] < 0 and p1['x'] <= game['ball']['x'] - BALL_RADIUS <= p1['x'] + PADDLE_WIDTH and p1['y'] <= game['ball']['y'] <= p1['y'] + PADDLE_HEIGHT):
            game['ball']['vx'] *= -1.1; game['ball']['x'] = p1['x'] + PADDLE_WIDTH + BALL_RADIUS
        if (game['ball']['vx'] > 0 and p2['x'] <= game['ball']['x'] + BALL_RADIUS <= p2['x'] + PADDLE_WIDTH and p2['y'] <= game['ball']['y'] <= p2['y'] + PADDLE_HEIGHT):
            game['ball']['vx'] *= -1.1; game['ball']['x'] = p2['x'] - BALL_RADIUS
        if game['ball']['x'] - BALL_RADIUS < 0: game['scores']['2'] += 1; reset_ball(game)
        elif game['ball']['x'] + BALL_RADIUS > WIDTH: game['scores']['1'] += 1; reset_ball(game)

class WorkerHandler(BaseHTTPRequestHandler):
    def _send_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_GET(self):
        if self.path.startswith('/state/'):
            game_id = self.path.split('/')[-1]
            update_game_state(game_id)
            with games_lock:
                if game_id in games:
                    self._send_response(200, games[game_id])
                else:
                    self._send_response(404, {"error": "Game not found"})
        else:
            self._send_response(404, {"error": "Endpoint not found"})

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        with games_lock:
            if self.path == '/new_game':
                game_id = str(uuid.uuid4())
                games[game_id] = {'paddles': {'1': {'x': 10, 'y': 250}, '2': {'x': 770, 'y': 250}},'ball': {'x': 400, 'y': 300, 'vx': 0, 'vy': 0},'scores': {'1': 0, '2': 0}, 'players': 0, 'ready': False, 'last_update': time.time()}
                reset_ball(games[game_id])
                self._send_response(200, {"status": "ok", "game_id": game_id})
            
            elif self.path.startswith('/join_game/'):
                game_id = self.path.split('/')[-1]
                if game_id in games:
                    game = games[game_id]
                    game['players'] += 1
                    player_id = str(game['players'])
                    if game['players'] == 2: game['ready'] = True
                    self._send_response(200, {"status": "ok", "player_id": player_id})
                else:
                    self._send_response(404, {"error": "Game not found"})
            
            elif self.path == '/move':
                data = json.loads(post_data)
                game_id = data.get('game_id')
                if game_id in games:
                    games[game_id]['paddles'][data['player_id']]['y'] = data['y']
                    self._send_response(200, {"status": "ok"})
                else:
                    self._send_response(404, {"error": "Game not found"})
            else:
                self._send_response(404, {"error": "Endpoint not found"})

def run_worker(host, port):
    server_address = (host, port)
    httpd = HTTPServer(server_address, WorkerHandler)
    print(f"Pong Worker running on {host}:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pong Worker Server")
    parser.add_argument('--port', type=int, default=8001, help='Port for the worker')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to run on')
    args = parser.parse_args()
    run_worker(args.host, args.port)
