# pong_loadbalancer.py

from http.server import BaseHTTPRequestHandler, HTTPServer
import itertools
import json
import urllib.request
import threading

# State untuk load balancer
WORKER_ADDRESSES = [ 'http://127.0.0.1:8001', 'http://127.0.0.1:8002' ]
worker_cycler = itertools.cycle(WORKER_ADDRESSES)
game_to_worker_map = {}
map_lock = threading.Lock()

class LoadBalancerHandler(BaseHTTPRequestHandler):
    def _get_game_id(self):
        if self.path.startswith('/state/') or self.path.startswith('/join_game/'):
            return self.path.split('/')[-1]
        if self.command == 'POST':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data_str = self.rfile.read(content_length).decode('utf-8')
                # Simpan body untuk diteruskan nanti
                self.post_data_bytes = post_data_str.encode('utf-8')
                return json.loads(post_data_str).get('game_id')
            except (KeyError, json.JSONDecodeError):
                return None
        return None

    def _proxy_request(self, target_worker_url):
        try:
            req = urllib.request.Request(target_worker_url, method=self.command)
            if self.command == 'POST':
                req.data = getattr(self, 'post_data_bytes', b'')
                req.add_header('Content-Type', 'application/json')

            with urllib.request.urlopen(req, timeout=5) as response:
                resp_body = response.read()
                self.send_response(response.status)
                for key, value in response.getheaders():
                    if key not in ['Content-Encoding', 'Transfer-Encoding', 'Connection']:
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(resp_body)

        except Exception as e:
            self.send_error(503, f"Worker service unavailable or failed: {e}")

    def do_GET(self):
        game_id = self._get_game_id()
        with map_lock:
            worker_url = game_to_worker_map.get(game_id)
        
        if worker_url:
            self._proxy_request(f"{worker_url}{self.path}")
        else:
            self.send_error(404, "Game not found or not mapped")

    def do_POST(self):
        if self.path == '/new_game':
            target_worker = next(worker_cycler)
            print(f"Assigning new game to {target_worker}")
            # Kita perlu memanggil proxy dan menangkap game_id dari responsnya
            try:
                req = urllib.request.Request(f"{target_worker}{self.path}", method='POST')
                with urllib.request.urlopen(req, timeout=5) as response:
                    resp_body = response.read()
                    resp_data = json.loads(resp_body)
                    game_id = resp_data.get('game_id')
                    with map_lock:
                        game_to_worker_map[game_id] = target_worker
                    print(f"Game {game_id} mapped to {target_worker}")
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(resp_body)
            except Exception as e:
                self.send_error(503, f"Worker failed to create game: {e}")
            return

        game_id = self._get_game_id()
        with map_lock:
            worker_url = game_to_worker_map.get(game_id)
        
        if worker_url:
            self._proxy_request(f"{worker_url}{self.path}")
        else:
            self.send_error(404, "Game not found or not mapped")

def run_loadbalancer(host, port):
    server_address = (host, port)
    httpd = HTTPServer(server_address, LoadBalancerHandler)
    print(f"Load Balancer running on {host}:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pong Load Balancer Server")
    parser.add_argument('--port', type=int, default=5000, help='Port for the load balancer')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to run on')
    args = parser.parse_args()
    run_loadbalancer(args.host, args.port)
