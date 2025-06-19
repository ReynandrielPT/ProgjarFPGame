# http.py

import socket
import threading

class HttpServer:
    def __init__(self, host='127.0.0.1', port=8000):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"HTTP Server listening on {self.host}:{self.port}")

    def start(self):
        try:
            while True:
                client_socket, client_address = self.server_socket.accept()
                handler_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                handler_thread.daemon = True
                handler_thread.start()
        except KeyboardInterrupt:
            print("Server shutting down.")
            self.server_socket.close()

    def handle_client(self, client_socket):
        try:
            request_data = client_socket.recv(4096).decode('utf-8')
            if not request_data:
                client_socket.close()
                return

            lines = request_data.split('\r\n')
            request_line = lines[0]
            method, path, _ = request_line.split(' ')

            body = ""
            if method == "POST":
                try:
                    body_start_index = request_data.find('\r\n\r\n') + 4
                    body = request_data[body_start_index:]
                except ValueError:
                    pass
            
            response = self.handle_request(method, path, body)
            client_socket.sendall(response)
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client_socket.close()

    def handle_request(self, method, path, body):
        response_body = "<h1>501 Not Implemented</h1>"
        response_headers = (
            "HTTP/1.1 501 Not Implemented\r\n"
            "Content-Type: text/html\r\n"
            f"Content-Length: {len(response_body)}\r\n"
            "Connection: close\r\n\r\n"
        )
        return (response_headers + response_body).encode('utf-8')
