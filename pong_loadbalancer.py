# pong_loadbalancer.py

from http import HttpServer
import itertools
import socket
import json

WORKER_ADDRESSES = [('127.0.0.1', 8001), ('127.0.0.1', 8002)]
game_to_worker_map = {}

class PongLoadBalancer(HttpServer):
    # --- PERBAIKAN DIMULAI DI SINI ---
    def __init__(self, host, port):
        super().__init__(host, port)
        self.worker_cycler = itertools.cycle(WORKER_ADDRESSES)
        print("Pong Load Balancer is ready.")
    # --- PERBAIKAN SELESAI ---

    def get_game_id(self, path, body):
        if path.startswith('/state/') or path.startswith('/join_game/'):
            return path.split('/')[-1]
        try:
            return json.loads(body).get('game_id') if body else None
        except json.JSONDecodeError:
            return None

    def forward_request(self, addr, raw_request):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as worker_socket:
            worker_socket.connect(addr)
            worker_socket.sendall(raw_request)
            return worker_socket.recv(4096)

    def handle_request(self, method, path, body):
        raw_request_data = f"{method} {path} HTTP/1.1\r\n\r\n{body}".encode('utf-8')

        if path == '/new_game':
            chosen_worker_addr = next(self.worker_cycler)
            print(f"Assigning new game to {chosen_worker_addr}")
            response = self.forward_request(chosen_worker_addr, raw_request_data)
            try:
                resp_body_str = response.decode('utf-8').split('\r\n\r\n', 1)[1]
                game_id = json.loads(resp_body_str).get('game_id')
                if game_id:
                    game_to_worker_map[game_id] = chosen_worker_addr
                    print(f"Game {game_id} is now mapped to {chosen_worker_addr}")
            except (IndexError, json.JSONDecodeError) as e:
                print(f"Could not parse game_id from worker response: {e}")
            return response
        
        game_id = self.get_game_id(path, body)
        if game_id in game_to_worker_map:
            worker_addr = game_to_worker_map[game_id]
            print(f"Forwarding request for game {game_id} to {worker_addr}")
            return self.forward_request(worker_addr, raw_request_data)
        else:
            error_body = '{"error": "Game not found or not mapped to any worker"}'
            return f"HTTP/1.1 404 Not Found\r\n\r\n{error_body}".encode('utf-8')

if __name__ == "__main__":
    lb = PongLoadBalancer(host='127.0.0.1', port=8000)
    lb.start()
