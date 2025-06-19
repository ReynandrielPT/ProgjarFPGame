# pong_loadbalancer.py

from http import HttpServer
import itertools
import socket
import json

# Konfigurasi untuk berjalan di satu mesin (localhost)
WORKER_ADDRESSES = [('127.0.0.1', 8001), ('127.0.0.1', 8002)]
game_to_worker_map = {}

class PongLoadBalancer(HttpServer):
    def __init__(self, host, port):
        super().__init__(host, port)
        self.worker_cycler = itertools.cycle(WORKER_ADDRESSES)
        print("Pong Load Balancer is ready.")

    # --- PERBAIKAN UTAMA: Override handle_client, bukan handle_request ---
    def handle_client(self, client_socket):
        try:
            # 1. Terima seluruh request mentah dari klien
            raw_request_from_client = client_socket.recv(4096)
            if not raw_request_from_client:
                return

            # Decode untuk diinspeksi (tanpa mengubahnya)
            request_str = raw_request_from_client.decode('utf-8')
            
            # 2. Parse seperlunya HANYA untuk menentukan routing
            lines = request_str.split('\r\n')
            method, path, _ = lines[0].split(' ')
            body = request_str.split('\r\n\r\n', 1)[1] if '\r\n\r\n' in request_str else ""
            
            # 3. Tentukan worker tujuan
            target_worker_addr = None
            
            # Kasus khusus: membuat game baru
            if path == '/new_game':
                chosen_worker_addr = next(self.worker_cycler)
                print(f"Assigning new game to {chosen_worker_addr}")
                
                # Teruskan request mentah ke worker terpilih
                response_from_worker = self.forward_request(chosen_worker_addr, raw_request_from_client)
                
                # Setelah game dibuat, petakan game_id ke worker
                try:
                    resp_body_str = response_from_worker.decode('utf-8').split('\r\n\r\n', 1)[1]
                    game_id = json.loads(resp_body_str).get('game_id')
                    if game_id:
                        game_to_worker_map[game_id] = chosen_worker_addr
                        print(f"Game {game_id} is now mapped to {chosen_worker_addr}")
                except Exception as e:
                    print(f"LB could not parse game_id from worker response: {e}")
                
                # Kirim balasan worker ke klien
                client_socket.sendall(response_from_worker)
                return

            # Kasus untuk game yang sudah ada
            game_id = self.get_game_id_from_path_or_body(path, body)
            if game_id and game_id in game_to_worker_map:
                target_worker_addr = game_to_worker_map[game_id]
                print(f"Forwarding request for game {game_id} to {target_worker_addr}")
                
                # Teruskan request mentah ke worker yang benar
                response = self.forward_request(target_worker_addr, raw_request_from_client)
                client_socket.sendall(response)
            else:
                # Jika game tidak ditemukan
                error_body = '{"error": "Game not found or not mapped"}'
                response = f"HTTP/1.1 404 Not Found\r\n\r\n{error_body}".encode('utf-8')
                client_socket.sendall(response)

        except Exception as e:
            print(f"Error in Load Balancer handler: {e}")
        finally:
            client_socket.close()

    def get_game_id_from_path_or_body(self, path, body):
        if path.startswith('/state/') or path.startswith('/join_game/'):
            return path.split('/')[-1]
        try:
            return json.loads(body).get('game_id') if body else None
        except (json.JSONDecodeError, AttributeError):
            return None

    def forward_request(self, addr, raw_request_bytes):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as worker_socket:
                worker_socket.connect(addr)
                worker_socket.sendall(raw_request_bytes)
                return worker_socket.recv(4096)
        except ConnectionRefusedError:
            print(f"Connection to worker {addr} refused.")
            error_body = '{"error": "Worker service unavailable"}'
            return f"HTTP/1.1 503 Service Unavailable\r\n\r\n{error_body}".encode('utf-8')

if __name__ == "__main__":
    lb = PongLoadBalancer(host='127.0.0.1', port=5000)
    lb.start()
