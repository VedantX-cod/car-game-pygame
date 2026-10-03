import pygame
import random
import array
import math
import threading
import cv2

pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.init()
WIDTH, HEIGHT = 400, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Car Game")
clock = pygame.time.Clock()
title_font = pygame.font.SysFont(None, 72)
font = pygame.font.SysFont(None, 56)
small_font = pygame.font.SysFont(None, 30)
tiny_font = pygame.font.SysFont(None, 24)

THEMES = [
    {"name": "Grass",  "side": (30, 120, 40),  "road": (50, 50, 50),  "line": (240, 240, 240)},
    {"name": "Desert", "side": (214, 178, 100), "road": (70, 62, 58),  "line": (255, 230, 150)},
    {"name": "Night",  "side": (12, 18, 40),   "road": (25, 25, 35),  "line": (120, 160, 255)},
]


def load_best():
    try:
        with open("highscore.txt") as f:
            return int(f.read())
    except (FileNotFoundError, ValueError):
        return 0


def save_best(value):
    with open("highscore.txt", "w") as f:
        f.write(str(value))


def make_car(body):
    s = pygame.Surface((50, 90), pygame.SRCALPHA)
    for wx, wy in [(0, 12), (42, 12), (0, 58), (42, 58)]:
        pygame.draw.rect(s, (20, 20, 20), (wx, wy, 8, 20), border_radius=3)
    pygame.draw.rect(s, body, (5, 0, 40, 90), border_radius=12)
    glass = (170, 210, 240)
    pygame.draw.rect(s, glass, (11, 22, 28, 16), border_radius=4)
    pygame.draw.rect(s, glass, (11, 56, 28, 12), border_radius=4)
    pygame.draw.rect(s, (255, 240, 150), (9, 3, 8, 5), border_radius=2)
    pygame.draw.rect(s, (255, 240, 150), (33, 3, 8, 5), border_radius=2)
    return s


def make_bike(body):
    """Top-view bike: patla, do pahiye line mein, handle aur rider."""
    s = pygame.Surface((50, 90), pygame.SRCALPHA)
    pygame.draw.rect(s, (20, 20, 20), (21, 2, 8, 24), border_radius=3)    # aage ka pahiya
    pygame.draw.rect(s, (20, 20, 20), (21, 62, 8, 26), border_radius=3)   # peeche ka pahiya
    pygame.draw.rect(s, body, (16, 18, 18, 56), border_radius=8)          # body/tank
    pygame.draw.rect(s, (30, 30, 30), (6, 24, 38, 6), border_radius=3)    # handle
    pygame.draw.circle(s, (240, 200, 160), (25, 46), 8)                   # rider ka helmet
    pygame.draw.rect(s, (40, 40, 60), (18, 50, 14, 18), border_radius=6)  # rider ki body
    pygame.draw.rect(s, (255, 240, 150), (22, 0, 6, 4), border_radius=2)  # headlight
    return s


def make_crash_sound():
    try:
        n = 20000
        buf = array.array("h")
        for i in range(n):
            amp = int(12000 * (1 - i / n) ** 2)
            buf.append(random.randint(-amp, amp))
        return pygame.mixer.Sound(buffer=buf.tobytes())
    except pygame.error:
        return None


def make_beep(freq, ms):
    try:
        n = int(44100 * ms / 1000)
        buf = array.array("h")
        for i in range(n):
            amp = 8000 * (1 - i / n)
            buf.append(int(amp * math.sin(2 * math.pi * freq * i / 44100)))
        return pygame.mixer.Sound(buffer=buf.tobytes())
    except pygame.error:
        return None


def write(text, f, y, color=(255, 255, 255)):
    img = f.render(text, True, color)
    screen.blit(img, img.get_rect(center=(WIDTH // 2, y)))


def dim_screen():
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 150))
    screen.blit(shade, (0, 0))


class Webcam:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.ok = self.cap.isOpened()
        self.x = None
        self.preview = None
        self.alive = True
        self.cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if self.ok:
            threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while self.alive:
            ok, frame = self.cap.read()
            if not ok:
                continue
            frame = cv2.flip(cv2.resize(frame, (320, 240)), 1)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.cascade.detectMultiScale(gray, 1.2, 5, minSize=(50, 50))
            if len(faces):
                fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                self.x = (fx + fw / 2) / 320
                cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (0, 255, 0), 2)
            else:
                self.x = None
            small = cv2.resize(frame, (160, 120))
            self.preview = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

    def stop(self):
        self.alive = False
        self.cap.release()


traffic_colors = [(60, 120, 220), (240, 190, 40), (150, 80, 200), (240, 240, 240), (40, 170, 160)]
crash_sound = make_crash_sound()
coin_sound = make_beep(880, 120)
shield_sound = make_beep(520, 250)

vehicle = "Car"          # Car / Bike
theme_i = 0
player_img = make_car((220, 40, 40))

car = pygame.Rect(0, 0, 50, 90)
car_speed = 6
traffic = []
items = []
spawn_timer = 0
item_timer = 0
score = 0
coins = 0
shield = False
best = load_best()
line_y = 0
state = "menu"          # menu / play / pause / over

cam = None
cam_on = False
cam_msg = ""


def set_vehicle(name):
    global vehicle, player_img
    vehicle = name
    player_img = make_car((220, 40, 40)) if name == "Car" else make_bike((220, 40, 40))
    pygame.display.set_caption(f"{name} Game")


def make_traffic_img():
    color = random.choice(traffic_colors)
    # Bike mode mein traffic mein bike aur car dono aayengi
    img = make_bike(color) if (vehicle == "Bike" and random.random() < 0.4) else make_car(color)
    return pygame.transform.flip(img, False, True)


def reset():
    global spawn_timer, item_timer, score, coins, shield
    car.midbottom = (WIDTH // 2, HEIGHT - 30)
    traffic.clear()
    items.clear()
    spawn_timer = 0
    item_timer = 0
    score = 0
    coins = 0
    shield = False


def toggle_cam():
    global cam, cam_on, cam_msg
    if cam_on:
        cam_on = False
        cam_msg = ""
        return
    if cam is None:
        cam = Webcam()
        if not cam.ok:
            cam = None
            cam_msg = "Camera nahi mila"
            return
    cam_on = True
    cam_msg = ""


def draw_item(it):
    cx, cy = it["rect"].center
    if it["kind"] == "coin":
        pygame.draw.circle(screen, (255, 200, 40), (cx, cy), 13)
        pygame.draw.circle(screen, (200, 140, 0), (cx, cy), 13, 3)
        pygame.draw.circle(screen, (255, 235, 130), (cx - 3, cy - 3), 4)
    else:
        pygame.draw.circle(screen, (60, 200, 240), (cx, cy), 14)
        pygame.draw.circle(screen, (255, 255, 255), (cx, cy), 14, 3)
        letter = tiny_font.render("S", True, (255, 255, 255))
        screen.blit(letter, letter.get_rect(center=(cx, cy)))


reset()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_c:
                toggle_cam()
            if state == "menu":
                if event.key == pygame.K_v:
                    set_vehicle("Bike" if vehicle == "Car" else "Car")
                elif event.key == pygame.K_t:
                    theme_i = (theme_i + 1) % len(THEMES)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    reset()
                    state = "play"
            elif state == "play" and event.key in (pygame.K_p, pygame.K_ESCAPE):
                state = "pause"
            elif state == "pause" and event.key in (pygame.K_p, pygame.K_ESCAPE):
                state = "play"
            elif state == "over":
                if event.key == pygame.K_r:
                    reset()
                    state = "play"
                elif event.key == pygame.K_m:
                    state = "menu"

    theme = THEMES[theme_i]
    level = score // 5
    traffic_speed = 6 + level
    spawn_gap = max(25, 60 - level * 5)

    if state in ("menu", "play"):
        line_y = (line_y + 8 + level) % 80

    if state == "play":
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            car.x -= car_speed
        if keys[pygame.K_RIGHT]:
            car.x += car_speed

        if cam_on and cam is not None and cam.x is not None:
            ratio = min(max((cam.x - 0.3) / 0.4, 0), 1)
            target = 54 + ratio * (WIDTH - 108 - 50)
            car.x += int((target - car.x) * 0.3)

        car.clamp_ip(pygame.Rect(54, 0, WIDTH - 108, HEIGHT))

        spawn_timer += 1
        if spawn_timer > spawn_gap:
            rect = pygame.Rect(random.randint(60, 290), -100, 50, 90)
            traffic.append({"rect": rect, "img": make_traffic_img()})
            spawn_timer = 0

        item_timer += 1
        if item_timer > 80:
            item_timer = 0
            r = pygame.Rect(random.randint(70, 300), -60, 28, 28)
            if not any(r.colliderect(t["rect"].inflate(20, 60)) for t in traffic):
                kind = "shield" if random.random() < 0.15 else "coin"
                items.append({"rect": r, "kind": kind})

        for t in traffic:
            t["rect"].y += traffic_speed
            if t["rect"].top >= HEIGHT:
                score += 1
        traffic = [t for t in traffic if t["rect"].top < HEIGHT]

        for it in items:
            it["rect"].y += traffic_speed
        items = [it for it in items if it["rect"].top < HEIGHT]

        for it in items[:]:
            if car.colliderect(it["rect"]):
                items.remove(it)
                if it["kind"] == "coin":
                    coins += 1
                    if coin_sound:
                        coin_sound.play()
                else:
                    shield = True
                    if shield_sound:
                        shield_sound.play()

        for t in traffic[:]:
            if car.inflate(-10, -10).colliderect(t["rect"].inflate(-10, -10)):
                if crash_sound:
                    crash_sound.play()
                if shield:
                    shield = False
                    traffic.remove(t)
                else:
                    state = "over"
                    if score > best:
                        best = score
                        save_best(best)
                break

    # ---------- Draw ----------
    screen.fill(theme["side"])
    pygame.draw.rect(screen, theme["road"], (50, 0, 300, HEIGHT))
    pygame.draw.rect(screen, theme["line"], (50, 0, 4, HEIGHT))
    pygame.draw.rect(screen, theme["line"], (346, 0, 4, HEIGHT))
    for y in range(-80, HEIGHT, 80):
        pygame.draw.rect(screen, theme["line"], (WIDTH // 2 - 4, y + line_y, 8, 40))
    for it in items:
        draw_item(it)
    for t in traffic:
        screen.blit(t["img"], t["rect"])
    screen.blit(player_img, car)
    if shield:
        pygame.draw.ellipse(screen, (60, 200, 240), car.inflate(24, 24), 4)

    if state != "menu":
        hud1 = small_font.render(f"Score: {score}   Best: {best}", True, (255, 255, 255))
        hud2 = small_font.render(f"Level: {level + 1}   Coins: {coins}", True, (255, 220, 80))
        screen.blit(hud1, (10, 10))
        screen.blit(hud2, (10, 36))
        if shield:
            tag = tiny_font.render("SHIELD ON", True, (60, 200, 240))
            screen.blit(tag, (10, 64))

    if cam_on and cam is not None:
        p = cam.preview
        if p is not None:
            screen.blit(pygame.surfarray.make_surface(p.swapaxes(0, 1)), (WIDTH - 165, HEIGHT - 125))
        if cam.x is None:
            warn = tiny_font.render("Chehra nahi mil raha", True, (255, 120, 120))
            screen.blit(warn, (WIDTH - 165, HEIGHT - 148))

    if state == "menu":
        dim_screen()
        write(f"{vehicle.upper()} GAME", title_font, 160, (255, 210, 60))
        write("ENTER = start", small_font, 240)
        write("<  >  steer      P = pause", small_font, 275)
        write(f"V = vehicle ({vehicle})", small_font, 320, (255, 170, 170))
        write(f"T = theme ({theme['name']})", small_font, 350, (255, 220, 150))
        write(f"C = webcam ({'ON' if cam_on else 'OFF'})", small_font, 380, (150, 220, 255))
        if cam_msg:
            write(cam_msg, tiny_font, 408, (255, 120, 120))
        write(f"Best score: {best}", small_font, 460, (170, 255, 170))
        # Menu mein chuni hui vehicle dikhe
        screen.blit(player_img, player_img.get_rect(center=(WIDTH // 2, 540)))
    elif state == "pause":
        dim_screen()
        write("Paused", font, HEIGHT // 2 - 20)
        write("Press P to resume", small_font, HEIGHT // 2 + 25)
    elif state == "over":
        dim_screen()
        write("Game Over", font, HEIGHT // 2 - 55)
        write(f"Score: {score}    Coins: {coins}", small_font, HEIGHT // 2 - 10)
        write("R = restart    M = menu", small_font, HEIGHT // 2 + 35)

    pygame.display.flip()
    clock.tick(60)

if cam is not None:
    cam.stop()
pygame.quit()