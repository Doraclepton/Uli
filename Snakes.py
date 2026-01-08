import pygame
import paho.mqtt.client as mqtt
import random
import uuid
import time
import math

# --- КОНФИГУРАЦИЯ 2026 ---
WIDTH, HEIGHT = 800, 600
FPS = 60
BASE_RADIUS = 20
FOOD_RADIUS = 8
TOPIC = "python/mqtt/global_stop_battle_2026"
BROKER = "broker.emqx.io"

MY_ID = str(uuid.uuid4())[:5]
MY_COLOR = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))


class RemotePlayer:
    def __init__(self, x, y, color, size):
        self.x, self.y = x, y
        self.target_x, self.target_y = x, y
        self.color = color
        self.size = size


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(f"Игрок: {MY_ID}")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 40)

        self.players = {}
        self.food_seeds = []
        self.last_send_time = 0
        self.last_food_update = 0

        self.global_game_over = False  # Флаг окончания игры для всех
        self.reset_player()

        # Настройка MQTT
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.will_set(TOPIC, payload=f"REMOVE:{MY_ID}", qos=0)
        self.client.on_connect = lambda c, u, f, rc, p=None: self.send_data()
        self.client.on_message = self.on_message
        self.client.connect(BROKER, 1883, 60)
        self.client.subscribe(TOPIC, qos=0)
        self.client.loop_start()

    def reset_player(self):
        self.my_pos = [random.randint(100, WIDTH - 100), random.randint(100, HEIGHT - 100)]
        self.my_size = BASE_RADIUS
        self.global_game_over = False

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode()
            if payload == "GAME_STOP":
                self.global_game_over = True
            elif payload.startswith("REMOVE:"):
                r_id = payload.split(":")[1]
                if r_id in self.players: del self.players[r_id]
            else:
                parts = payload.split(':')
                p_id = parts[0]
                if p_id != MY_ID:
                    x, y, size = float(parts[1]), float(parts[2]), int(parts[3])
                    color = tuple(map(int, parts[4].split(',')))
                    if p_id not in self.players:
                        self.players[p_id] = RemotePlayer(x, y, color, size)
                    else:
                        self.players[p_id].target_x, self.players[p_id].target_y = x, y
                        self.players[p_id].size = size
        except:
            pass

    def send_data(self):
        if self.global_game_over: return
        color_str = f"{MY_COLOR[0]},{MY_COLOR[1]},{MY_COLOR[2]}"
        payload = f"{MY_ID}:{self.my_pos[0]}:{self.my_pos[1]}:{int(self.my_size)}:{color_str}"
        self.client.publish(TOPIC, payload, qos=0)

    def draw_ui(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        txt = self.font.render("ИГРА ЗАКОНЧЕНА", True, (255, 255, 255))
        self.screen.blit(txt, (WIDTH // 2 - 140, HEIGHT // 2 - 100))

        self.btn_rect = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2, 200, 60)
        pygame.draw.rect(self.screen, (0, 200, 100), self.btn_rect, border_radius=10)
        btn_txt = self.font.render("ИГРАТЬ", True, (255, 255, 255))
        self.screen.blit(btn_txt, (WIDTH // 2 - 60, HEIGHT // 2 + 5))

    def run(self):
        running = True
        while running:
            self.screen.fill((20, 20, 25))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.client.publish(TOPIC, f"REMOVE:{MY_ID}", qos=0)
                    running = False
                if event.type == pygame.MOUSEBUTTONDOWN and self.global_game_over:
                    if self.btn_rect.collidepoint(event.pos):
                        self.reset_player()
                        self.send_data()

            if not self.global_game_over:
                # Движение
                keys = pygame.key.get_pressed()
                speed = max(1, 4 - (self.my_size // 50))
                moved = False
                if keys[pygame.K_a]: self.my_pos[0] -= speed; moved = True
                if keys[pygame.K_d]: self.my_pos[0] += speed; moved = True
                if keys[pygame.K_w]: self.my_pos[1] -= speed; moved = True
                if keys[pygame.K_s]: self.my_pos[1] += speed; moved = True

                self.my_pos[0] = max(self.my_size, min(self.my_pos[0], WIDTH - self.my_size))
                self.my_pos[1] = max(self.my_size, min(self.my_pos[1], HEIGHT - self.my_size))

                # Еда
                cur_t = int(time.time() / 20)
                if self.last_food_update != cur_t:
                    random.seed(cur_t)
                    self.food_seeds = [[random.randint(30, WIDTH - 30), random.randint(30, HEIGHT - 30)] for _ in
                                       range(10)]
                    self.last_food_update = cur_t

                for food in self.food_seeds[:]:
                    if math.hypot(self.my_pos[0] - food[0], self.my_pos[1] - food[1]) < self.my_size:
                        self.food_seeds.remove(food)
                        self.my_size += 5
                        moved = True

                # Столкновения и конец игры
                for p_id, p in list(self.players.items()):
                    dist = math.hypot(self.my_pos[0] - p.x, self.my_pos[1] - p.y)
                    if dist < self.my_size and self.my_size > p.size + 5:
                        # Если мы съели кого-то, объявляем стоп всем
                        self.client.publish(TOPIC, "GAME_STOP", qos=0)

                if moved or pygame.time.get_ticks() - self.last_send_time > 50:
                    self.send_data()
                    self.last_send_time = pygame.time.get_ticks()

            # Отрисовка
            for food in self.food_seeds:
                pygame.draw.circle(self.screen, (0, 150, 255), food, FOOD_RADIUS)

            for p in list(self.players.values()):
                p.x += (p.target_x - p.x) * 0.1
                p.y += (p.target_y - p.y) * 0.1
                pygame.draw.circle(self.screen, p.color, (int(p.x), int(p.y)), p.size)

            if not self.global_game_over:
                pygame.draw.circle(self.screen, MY_COLOR, (int(self.my_pos[0]), int(self.my_pos[1])), int(self.my_size))
            else:
                self.draw_ui()

            pygame.display.flip()
            self.clock.tick(FPS)

        self.client.loop_stop()
        pygame.quit()


if __name__ == "__main__":
    Game().run()
