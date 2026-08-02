import pygame, json
from COMMON.config import *

class Move:
    def __init__(self, num, x, y):
        self.name = num
        self.rect = pygame.Rect(x, y, TILE, TILE)
        with open(resource_path("INFO", "test_map.json"), "r", encoding="utf-8") as f:
            maps = json.load(f)
        self.map = maps.get(str(num), maps["0"])
        with open(resource_path("INFO", "block.json"), "r", encoding="utf-8") as f:
            self.block_data = json.load(f)
        for i, block in self.block_data.items():
            self.block_data[i]["img"] = pygame.image.load(resource_path(block["img"]))
        self.event = []
        self.direction = FRONT
        self.moving = False
        self.target_x = self.rect.x
        self.target_y = self.rect.y
        self.held_keys = set()
        self.last_direction_key = None
        self.completed_step = None
        self.change_scroll()

    def change_scroll(self) -> None:
        self.scroll_x = self.rect.centerx - WIDTH // 2
        self.scroll_y = self.rect.centery - HEIGHT // 2
        self.scroll_x = max(0, min(self.scroll_x, len(self.map[0]) * TILE - WIDTH))
        self.scroll_y = max(0, min(self.scroll_y, len(self.map) * TILE - HEIGHT))

    def tile_data(self, grid_x, grid_y):
        if grid_y < 0 or grid_y >= len(self.map):
            return None
        if grid_x < 0 or grid_x >= len(self.map[0]):
            return None
        block_num = self.map[grid_y][grid_x]
        return self.block_data.get(str(block_num))

    def consume_completed_step(self):
        """移動が完了したマスを一度だけ返す。"""
        completed_step = self.completed_step
        self.completed_step = None
        return completed_step

    def move_check(self, nx, ny) -> bool:
        points = [(nx, ny), (nx + TILE - 1, ny), (nx, ny + TILE - 1), (nx + TILE - 1, ny + TILE - 1)]
        for px, py in points:
            gx = px // TILE
            gy = py // TILE
            if gy < 0 or gy >= len(self.map):
                return False
            if gx < 0 or gx >= len(self.map[0]):
                return False
            block_num = self.map[gy][gx]
            block = self.block_data[str(block_num)]
            if block["type"] == "wall":
                return False
            for event in self.event:
                if event.x == gx and event.y == gy and event.wall:
                    return False
        return True

    def _is_held(self, *keys):
        return any(key in self.held_keys for key in keys)

    def _movement_from_held_keys(self):
        horizontal = int(self._is_held(pygame.K_d, pygame.K_RIGHT))
        horizontal -= int(self._is_held(pygame.K_a, pygame.K_LEFT))
        vertical = int(self._is_held(pygame.K_s, pygame.K_DOWN))
        vertical -= int(self._is_held(pygame.K_w, pygame.K_UP))
        if horizontal == 0 and vertical == 0:
            return None

        if self.last_direction_key in (pygame.K_d, pygame.K_RIGHT) and horizontal > 0:
            direction = RIGHT
        elif self.last_direction_key in (pygame.K_a, pygame.K_LEFT) and horizontal < 0:
            direction = LEFT
        elif self.last_direction_key in (pygame.K_w, pygame.K_UP) and vertical < 0:
            direction = FRONT
        elif self.last_direction_key in (pygame.K_s, pygame.K_DOWN) and vertical > 0:
            direction = BACK
        elif horizontal > 0:
            direction = RIGHT
        elif horizontal < 0:
            direction = LEFT
        elif vertical < 0:
            direction = FRONT
        else:
            direction = BACK

        return horizontal * TILE, vertical * TILE, direction

    def _start_move(self, movement):
        dx, dy, direction = movement

        # 斜め入力は横軸・縦軸を別々に判定する。
        # 一方が壁でも、もう一方が通れるなら壁に沿って移動する。
        if dx and dy:
            if not self.move_check(self.rect.x + dx, self.rect.y):
                dx = 0
            if not self.move_check(self.rect.x, self.rect.y + dy):
                dy = 0

            if dx and dy and not self.move_check(
                self.rect.x + dx, self.rect.y + dy
            ):
                # 斜め先だけが壁なら、最後に押したキーの軸を優先する。
                if self.last_direction_key in (
                    pygame.K_d,
                    pygame.K_RIGHT,
                    pygame.K_a,
                    pygame.K_LEFT,
                ):
                    dy = 0
                else:
                    dx = 0
        elif not self.move_check(self.rect.x + dx, self.rect.y + dy):
            return False

        if dx == 0 and dy == 0:
            return False

        if dx and not dy:
            direction = RIGHT if dx > 0 else LEFT
        elif dy and not dx:
            direction = BACK if dy > 0 else FRONT

        self.direction = direction
        self.target_x = self.rect.x + dx
        self.target_y = self.rect.y + dy
        self.moving = True
        return True

    def handle_event(self, event) -> None:
        if event.type not in (pygame.KEYDOWN, pygame.KEYUP):
            return
        movement_keys = {
            pygame.K_d,
            pygame.K_RIGHT,
            pygame.K_a,
            pygame.K_LEFT,
            pygame.K_w,
            pygame.K_UP,
            pygame.K_s,
            pygame.K_DOWN,
        }
        if event.key not in movement_keys:
            return
        if event.type == pygame.KEYDOWN:
            self.held_keys.add(event.key)
            self.last_direction_key = event.key
        elif event.type == pygame.KEYUP:
            self.held_keys.discard(event.key)
            if self.moving and self.rect.x % TILE == 0 and self.rect.y % TILE == 0:
                self.moving = False
                self.target_x = self.rect.x
                self.target_y = self.rect.y
                movement = self._movement_from_held_keys()
                if movement is not None:
                    self._start_move(movement)


    def clear_input(self):
        self.held_keys.clear()
        self.last_direction_key = None

    @staticmethod
    def _approach(current, target):
        if current < target:
            return min(current + SPEED, target)
        if current > target:
            return max(current - SPEED, target)
        return current

    def update(self) -> None:
        if not self.moving:
            movement = self._movement_from_held_keys()
            if movement is None or not self._start_move(movement):
                return

        self.rect.x = self._approach(self.rect.x, self.target_x)
        self.rect.y = self._approach(self.rect.y, self.target_y)
        if self.rect.topleft != (self.target_x, self.target_y):
            return

        self.moving = False
        self.completed_step = (self.rect.x // TILE, self.rect.y // TILE)
        movement = self._movement_from_held_keys()
        if movement is not None:
            self._start_move(movement)

    def draw(self, screen):
        self.change_scroll()
        start_x = self.scroll_x // TILE
        start_y = self.scroll_y // TILE
        end_x = start_x + WIDTH // TILE + 2
        end_y = start_y + HEIGHT // TILE + 2
        for y in range(start_y, min(end_y, len(self.map))):
            for x in range(start_x, min(end_x, len(self.map[0]))):
                block_num = self.map[y][x]
                img = self.block_data[str(block_num)]["img"]
                screen.blit(img,(x * TILE - self.scroll_x, y * TILE - self.scroll_y))
        for event in self.event:
            if event.type not in ("npc", "tutorial"):
                event.draw(screen, self.scroll_x, self.scroll_y)
        pygame.draw.rect(screen,(10,10,10),(self.rect.x-self.scroll_x,self.rect.y-self.scroll_y,TILE,TILE))
        for event in self.event:
            if event.type in ("npc", "tutorial"):
                event.draw(screen, self.scroll_x, self.scroll_y)