# 
import pygame
import socket
import json
import sys

pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Distributed Pong")
font = pygame.font.Font(None, 74)
small_font = pygame.font.Font(None, 36)
LOAD_BALANCER_ADDR = ('127.0.0.1', 8000)
WHITE, BLACK = (255, 255, 255), (0, 0, 0)

game_id, player_id = None, None

def send_request(method, path, body_dict=None):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(LOAD_BALANCER_ADDR)
            body_str = json.dumps(body_dict) if body_dict else ""
            request_line = f"{method} {path} HTTP/1.1\r\n"
            headers = f"Host: {LOAD_BALANCER_ADDR[0]}:{LOAD_BALANCER_ADDR[1]}\r\nContent-Length: {len(body_str)}\r\n\r\n"
            sock.sendall((request_line + headers + body_str).encode('utf-8'))
            response_raw = sock.recv(4096).decode('utf-8')
            return json.loads(response_raw.split('\r\n\r\n', 1)[1])
    except Exception as e:
        print(f"Connection error: {e}"); return None

def menu_screen():
    global game_id, player_id
    input_text = ''
    new_game_btn = pygame.Rect(WIDTH/2 - 100, HEIGHT/2 - 80, 200, 60)
    input_box = pygame.Rect(WIDTH/2 - 150, HEIGHT/2 + 40, 300, 50)
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if new_game_btn.collidepoint(event.pos):
                    data = send_request("POST", "/new_game")
                    if data: game_id, player_id = data['game_id'], '1'; return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and input_text:
                    data = send_request("POST", f"/join_game/{input_text}")
                    if data: game_id, player_id = input_text, data['player_id']; return
                elif event.key == pygame.K_BACKSPACE: input_text = input_text[:-1]
                else: input_text += event.unicode
        
        screen.fill(BLACK)
        pygame.draw.rect(screen, WHITE, new_game_btn, 2)
        screen.blit(small_font.render("New Game", True, WHITE), (new_game_btn.x + 45, new_game_btn.y + 15))
        screen.blit(small_font.render("Or Enter Game ID:", True, WHITE), (input_box.x, input_box.y - 30))
        pygame.draw.rect(screen, WHITE, input_box, 2)
        screen.blit(font.render(input_text, True, WHITE), (input_box.x+5, input_box.y+5))
        pygame.display.flip()

def game_loop():
    player_y = HEIGHT / 2 - 50
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return

        keys = pygame.key.get_pressed()
        new_y = player_y
        if keys[pygame.K_UP]: new_y -= 10
        if keys[pygame.K_DOWN]: new_y += 10
        new_y = max(0, min(new_y, HEIGHT - PADDLE_HEIGHT))

        if new_y != player_y:
            player_y = new_y
            send_request("POST", "/move", {"game_id": game_id, "player_id": player_id, "y": player_y})

        game_state = send_request("GET", f"/state/{game_id}")
        
        screen.fill(BLACK)
        if game_state:
            p1 = game_state['paddles']['1']; p2 = game_state['paddles']['2']
            pygame.draw.rect(screen, WHITE, (p1['x'], p1['y'], PADDLE_WIDTH, PADDLE_HEIGHT))
            pygame.draw.rect(screen, WHITE, (p2['x'], p2['y'], PADDLE_WIDTH, PADDLE_HEIGHT))
            pygame.draw.circle(screen, WHITE, (game_state['ball']['x'], game_state['ball']['y']), BALL_RADIUS)
            score1 = font.render(str(game_state['scores']['1']), True, WHITE)
            score2 = font.render(str(game_state['scores']['2']), True, WHITE)
            screen.blit(score1, (WIDTH/4, 20)); screen.blit(score2, (WIDTH * 3/4 - score2.get_width(), 20))
            if not game_state.get('ready', False):
                wait_text = small_font.render(f"Game ID: {game_id} - Waiting for Player 2...", True, WHITE)
                screen.blit(wait_text, (WIDTH/2 - wait_text.get_width()/2, 10))
        
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    menu_screen()
    if game_id and player_id:
        game_loop()
    pygame.quit()
    sys.exit()
