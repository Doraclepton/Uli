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
BROKER = "broker.emqx.io"
# Базовый путь к топику
TOPIC_PREFIX = "python/mqtt/battle2026/room_"

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
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 28)
        self.big_font = pygame.font.SysFont("Arial", 36)

        self.room_id = ""
        self.input_text = ""
        self.in_menu = True
        self.global_game_over = False

        self.players = {}
        self.food_seeds = []
        self.last_send_time = 0
        self.last_food_update = 0

        # Настройка MQTT клиента
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_message = self.on_message

    def connect_to_room(self, room_id):
        self.room_id = room_id
        self.current_topic = TOPIC_PREFIX + self.room_id

        pygame.display.set_caption(f"КОМНАТА: {self.room_id} | ВЫ: {MY_ID}")

        self.client.connect(BROKER, 1883, 60)
        self.client.subscribe(self.current_topic, qos=0)
        self.client.will_set(self.current_topic, payload=f"REMOVE:{MY_ID}", qos=0)
        self.client.loop_start()

        self.reset_player()
        self.in_menu = False

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
        if self.in_menu or self.global_game_over: return
        color_str = f"{MY_COLOR[0]},{MY_COLOR[1]},{MY_COLOR[2]}"
        payload = f"{MY_ID}:{self.my_pos[0]}:{self.my_pos[1]}:{int(self.my_size)}:{color_str}"
        self.client.publish(self.current_topic, payload, qos=0)

    def draw_menu(self):
        self.screen.fill((30, 30, 45))

        # Заголовок
        title = self.big_font.render("BATTLE ARENA 2026", True, (255, 255, 255))
        self.screen.blit(title, (WIDTH // 2 - 150, 50))

        # Кнопка Создать
        self.create_btn = pygame.Rect(WIDTH // 2 - 150, 150, 300, 60)
        pygame.draw.rect(self.screen, (46, 204, 113), self.create_btn, border_radius=10)
        txt = self.font.render("СОЗДАТЬ КОМНАТУ", True, (255, 255, 255))
        self.screen.blit(txt, (WIDTH // 2 - 115, 165))

        # Секция ввода
        instr = self.font.render("Или введите ID для входа:", True, (180, 180, 180))
        self.screen.blit(instr, (WIDTH // 2 - 140, 260))

        self.input_rect = pygame.Rect(WIDTH // 2 - 150, 300, 300, 50)
        pygame.draw.rect(self.screen, (255, 255, 255), self.input_rect, border_radius=5)
        # Текст ввода
        input_surf = self.font.render(self.input_text, True, (40, 40, 40))
        self.screen.blit(input_surf, (self.input_rect.x + 10, self.input_rect.y + 10))

        # Кнопка Войти
        self.join_btn = pygame.Rect(WIDTH // 2 - 150, 370, 300, 60)
        pygame.draw.rect(self.screen, (52, 152, 219), self.join_btn, border_radius=10)
        txt_join = self.font.render("ПРИСОЕДИНИТЬСЯ", True, (255, 255, 255))
        self.screen.blit(txt_join, (WIDTH // 2 - 110, 385))

    def run(self):
        running = True
        while running:
            self.screen.fill((20, 20, 25))

            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    if not self.in_menu:
                        self.client.publish(self.current_topic, f"REMOVE:{MY_ID}", qos=0)
                    running = False

                if self.in_menu:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_BACKSPACE:
                            self.input_text = self.input_text[:-1]
                        elif len(self.input_text) < 8:
                            self.input_text += event.unicode.upper()

                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if self.create_btn.collidepoint(event.pos):
                            new_id = str(random.randint(1000, 9999))
                            self.connect_to_room(new_id)
                        if self.join_btn.collidepoint(event.pos) and self.input_text:
                            self.connect_to_room(self.input_text)

                elif self.global_game_over:
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if hasattr(self, 'retry_btn') and self.retry_btn.collidepoint(event.pos):
                            self.reset_player()
                            self.send_data()

            if self.in_menu:
                self.draw_menu()
            else:
                self.game_loop()

            pygame.display.flip()
            self.clock.tick(FPS)

        self.client.loop_stop()
        pygame.quit()

    def game_loop(self):
        if not self.global_game_over:
            # Управление
            keys = pygame.key.get_pressed()
            speed = max(1, 5 - (self.my_size // 60))
            moved = False
            if keys[pygame.K_a]: self.my_pos[0] -= speed; moved = True
            if keys[pygame.K_d]: self.my_pos[0] += speed; moved = True
            if keys[pygame.K_w]: self.my_pos[1] -= speed; moved = True
            if keys[pygame.K_s]: self.my_pos[1] += speed; moved = True

            # Границы
            self.my_pos[0] = max(self.my_size, min(self.my_pos[0], WIDTH - self.my_size))
            self.my_pos[1] = max(self.my_size, min(self.my_pos[1], HEIGHT - self.my_size))

            # Еда (общая для комнаты через сид времени)
            cur_t = int(time.time() / 15)
            if self.last_food_update != cur_t:
                random.seed(cur_t + hash(self.room_id))  # Еда зависит от ID комнаты
                self.food_seeds = [[random.randint(30, WIDTH - 30), random.randint(30, HEIGHT - 30)] for _ in range(12)]
                self.last_food_update = cur_t

            for food in self.food_seeds[:]:
                if math.hypot(self.my_pos[0] - food[0], self.my_pos[1] - food[1]) < self.my_size:
                    if food in self.food_seeds: self.food_seeds.remove(food)
                    self.my_size += 3
                    moved = True

            # Проверка поедания других игроков
            for p_id, p in list(self.players.items()):
                dist = math.hypot(self.my_pos[0] - p.x, self.my_pos[1] - p.y)
                if dist < self.my_size and self.my_size > p.size + 10:
                    self.client.publish(self.current_topic, "GAME_STOP", qos=0)

            if moved or pygame.time.get_ticks() - self.last_send_time > 40:
                self.send_data()
                self.last_send_time = pygame.time.get_ticks()

        # Отрисовка еды
        for food in self.food_seeds:
            pygame.draw.circle(self.screen, (231, 76, 60), food, FOOD_RADIUS)

        # Отрисовка чужих игроков
        for p in list(self.players.values()):
            p.x += (p.target_x - p.x) * 0.15  # Плавное движение
            p.y += (p.target_y - p.y) * 0.15
            pygame.draw.circle(self.screen, p.color, (int(p.x), int(p.y)), int(p.size))

        # Отрисовка себя
        if not self.global_game_over:
            pygame.draw.circle(self.screen, MY_COLOR, (int(self.my_pos[0]), int(self.my_pos[1])), int(self.my_size))
            id_tag = self.font.render(f"ROOM: {self.room_id}", True, (100, 100, 100))
            self.screen.blit(id_tag, (10, 10))
        else:
            self.draw_game_over()

    def draw_game_over(self):
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        s.fill((0, 0, 0, 200))
        self.screen.blit(s, (0, 0))

        txt = self.big_font.render("АРЕНА ЗАКРЫТА: КТО-ТО ПОБЕДИЛ", True, (255, 255, 255))
        self.screen.blit(txt, (WIDTH // 2 - 250, HEIGHT // 2 - 100))

        self.retry_btn = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2, 200, 60)
        pygame.draw.rect(self.screen, (46, 204, 113), self.retry_btn, border_radius=10)
        btn_txt = self.font.render("ИГРАТЬ СНОВА", True, (255, 255, 255))
        self.screen.blit(btn_txt, (WIDTH // 2 - 80, HEIGHT // 2 + 15))


if __name__ == "__main__":
    Game().run()
