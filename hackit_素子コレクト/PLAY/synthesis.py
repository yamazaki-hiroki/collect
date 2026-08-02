"""ブレッドボードイベントから開く素子合成画面。"""

from pathlib import Path

import pygame

from COMMON.button import Button
from COMMON.config import *
from PLAY.character_repository import (
    apply_character_amount_changes,
    load_character_amounts,
    load_characters,
)


RECIPES = (
    {"result_id": 7, "materials": {11: 1, 3: 3}},
    {"result_id": 8, "materials": {11: 1, 3: 3}},
    {"result_id": 9, "materials": {1: 2, 3: 1}},
    {"result_id": 10, "materials": {11: 1, 3: 3}},
    {"result_id": 11, "materials": {1: 4}},
    {"result_id": 12, "materials": {2: 1, 1: 1}},
    {"result_id": 13, "materials": {2: 1, 1: 1}},
)

if any(sum(recipe["materials"].values()) > 4 for recipe in RECIPES):
    raise ValueError("合成材料は最大4個です")


class Synthesis:
    """最大4個の所持素子を消費して、新しい素子を1個作る。"""

    RECIPE_RECT = pygame.Rect(14, 54, 238, 420)
    BOARD_RECT = pygame.Rect(270, 72, 270, 250)
    DETAIL_RECT = pygame.Rect(552, 54, 234, 420)
    ROW_HEIGHT = 48

    def __init__(self, inventory_path=None, party_path=None):
        self.inventory_path = (
            Path(inventory_path)
            if inventory_path
            else resource_path("INFO", "character_inventory.json")
        )
        self.party_path = (
            Path(party_path)
            if party_path
            else resource_path("INFO", "party.json")
        )
        self.characters = load_characters()
        self.character_by_id = {
            character.id: character for character in self.characters
        }
        self.amounts = {}
        self.selected_index = 0
        self.message = "作りたい素子を選んでください"
        self.opening_event = False
        self.image_cache = {}
        self.small_font = pygame.font.SysFont("msgothic", 18)
        self.tiny_font = pygame.font.SysFont("msgothic", 15)
        self.back_button = Button(
            8, 5, 105, 26, "← 戻る", font=self.tiny_font
        )
        self.craft_button = Button(
            566, 392, 206, 58, "合成する", font=self.small_font
        )
        try:
            image = pygame.image.load(
                resource_path("INFO", "RESOURCE", "bread.png")
            ).convert_alpha()
            self.board_image = pygame.transform.scale(image, (240, 180))
        except (FileNotFoundError, pygame.error, OSError):
            self.board_image = None
        self.refresh()

    def open(self):
        self.refresh()
        self.selected_index = 0
        self.message = "作りたい素子を選んでください"
        self.opening_event = True

    def refresh(self):
        self.amounts = load_character_amounts(self.inventory_path)

    def _recipe(self):
        return RECIPES[self.selected_index]

    def _material_units(self, recipe=None):
        recipe = recipe or self._recipe()
        units = []
        for character_id, amount in recipe["materials"].items():
            units.extend([character_id] * amount)
        return units

    def _can_craft(self, recipe=None):
        recipe = recipe or self._recipe()
        return all(
            self.amounts.get(character_id, 0) >= required
            for character_id, required in recipe["materials"].items()
        )

    def _craft(self):
        recipe = self._recipe()
        result = self.character_by_id[recipe["result_id"]]
        if not self._can_craft(recipe):
            missing = []
            for character_id, required in recipe["materials"].items():
                owned = self.amounts.get(character_id, 0)
                if owned < required:
                    name = self.character_by_id[character_id].name
                    missing.append(f"{name} {owned}/{required}")
            self.message = "材料不足: " + "、".join(missing)
            return False

        changes = {
            character_id: -required
            for character_id, required in recipe["materials"].items()
        }
        changes[recipe["result_id"]] = changes.get(recipe["result_id"], 0) + 1
        if not apply_character_amount_changes(
            changes,
            self.inventory_path,
            self.party_path,
        ):
            self.message = "材料が不足しています"
            return False

        self.refresh()
        self.message = f"{result.name}を1個合成しました"
        return True

    def _recipe_row_rect(self, index):
        return pygame.Rect(
            self.RECIPE_RECT.x + 8,
            self.RECIPE_RECT.y + 38 + index * self.ROW_HEIGHT,
            self.RECIPE_RECT.width - 16,
            self.ROW_HEIGHT - 4,
        )

    def _load_character_image(self, character, size=(48, 48)):
        key = (character.path, size)
        if key in self.image_cache:
            return self.image_cache[key]
        image = None
        if character.path:
            path = Path(character.path)
            if not path.is_absolute():
                path = resource_path(*path.parts)
            try:
                image = pygame.image.load(path).convert_alpha()
                image = pygame.transform.scale(image, size)
            except (FileNotFoundError, pygame.error, OSError):
                image = None
        self.image_cache[key] = image
        return image

    def update(self, event, mx, my):
        if self.opening_event:
            self.opening_event = False
            if (
                event.type == pygame.KEYDOWN
                and event.key == pygame.K_SPACE
            ):
                return SYNTHESIS

        if event.type == pygame.KEYDOWN:
            if event.key in (
                pygame.K_ESCAPE,
                pygame.K_m,
                pygame.K_BACKSPACE,
            ):
                return MOVE
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected_index = (
                    self.selected_index - 1
                ) % len(RECIPES)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected_index = (
                    self.selected_index + 1
                ) % len(RECIPES)
            elif event.key in (
                pygame.K_RETURN,
                pygame.K_KP_ENTER,
                pygame.K_SPACE,
            ):
                self._craft()
            return SYNTHESIS

        if event.type == pygame.MOUSEMOTION:
            for index in range(len(RECIPES)):
                if self._recipe_row_rect(index).collidepoint(mx, my):
                    self.selected_index = index
                    break
            return SYNTHESIS

        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
        ):
            if self.back_button.is_hover(mx, my):
                return MOVE
            for index in range(len(RECIPES)):
                if self._recipe_row_rect(index).collidepoint(mx, my):
                    self.selected_index = index
                    return SYNTHESIS
            if self.craft_button.is_hover(mx, my):
                self._craft()
            return SYNTHESIS
        return SYNTHESIS

    def _draw_character_icon(self, screen, character, rect):
        image = self._load_character_image(
            character, (rect.width, rect.height)
        )
        if image:
            screen.blit(image, rect)
        else:
            pygame.draw.rect(screen, (30, 34, 45), rect)
            mark = self.small_font.render("?", True, LOWH)
            screen.blit(mark, mark.get_rect(center=rect.center))

    def _draw_recipes(self, screen):
        pygame.draw.rect(screen, BLACK, self.RECIPE_RECT)
        pygame.draw.rect(screen, LOW_YELLOW, self.RECIPE_RECT, 2)
        screen.blit(
            self.small_font.render("合成レシピ", True, WHITE),
            (self.RECIPE_RECT.x + 10, self.RECIPE_RECT.y + 8),
        )
        for index, recipe in enumerate(RECIPES):
            rect = self._recipe_row_rect(index)
            selected = index == self.selected_index
            available = self._can_craft(recipe)
            pygame.draw.rect(
                screen,
                LOW_BLUE if selected else (16, 20, 29),
                rect,
            )
            pygame.draw.rect(
                screen,
                YELLOW if selected else LOW_YELLOW,
                rect,
                3 if selected else 1,
            )
            result = self.character_by_id[recipe["result_id"]]
            color = WHITE if available else GRAY
            screen.blit(
                self.small_font.render(result.name, True, color),
                (rect.x + 8, rect.y + 10),
            )

    def _draw_board(self, screen):
        pygame.draw.rect(screen, (10, 14, 22), self.BOARD_RECT)
        pygame.draw.rect(screen, LOW_YELLOW, self.BOARD_RECT, 2)
        if self.board_image:
            board_rect = self.board_image.get_rect(
                center=(self.BOARD_RECT.centerx, 178)
            )
            screen.blit(self.board_image, board_rect)
        else:
            board_rect = pygame.Rect(285, 87, 240, 180)
            pygame.draw.rect(screen, (55, 45, 30), board_rect)

        positions = (
            (294, 112),
            (444, 112),
            (294, 218),
            (444, 218),
        )
        for index, character_id in enumerate(self._material_units()):
            slot = pygame.Rect(*positions[index], 58, 58)
            pygame.draw.rect(screen, (6, 8, 14), slot)
            character = self.character_by_id[character_id]
            self._draw_character_icon(
                screen, character, slot.inflate(-10, -10)
            )
            pygame.draw.rect(screen, YELLOW, slot, 2)

        instruction = self.tiny_font.render(
            "材料は最大4個まで", True, LOWH
        )
        screen.blit(
            instruction,
            instruction.get_rect(
                center=(self.BOARD_RECT.centerx, 305)
            ),
        )

    def _draw_detail(self, screen, mx, my):
        pygame.draw.rect(screen, BLACK, self.DETAIL_RECT)
        pygame.draw.rect(screen, LOW_YELLOW, self.DETAIL_RECT, 2)
        recipe = self._recipe()
        result = self.character_by_id[recipe["result_id"]]
        screen.blit(
            self.small_font.render("完成品", True, WHITE),
            (566, 64),
        )
        result_rect = pygame.Rect(570, 96, 64, 64)
        self._draw_character_icon(screen, result, result_rect)
        screen.blit(
            self.small_font.render(result.name, True, YELLOW),
            (644, 105),
        )
        owned_result = self.amounts.get(result.id, 0)
        screen.blit(
            self.tiny_font.render(
                f"所持数 ×{owned_result}", True, LOWH
            ),
            (644, 136),
        )

        screen.blit(
            self.small_font.render("必要材料", True, WHITE),
            (566, 180),
        )
        y = 216
        for character_id, required in recipe["materials"].items():
            character = self.character_by_id[character_id]
            owned = self.amounts.get(character_id, 0)
            enough = owned >= required
            color = WHITE if enough else RED
            line = f"{character.name}  {owned}/{required}"
            screen.blit(
                self.tiny_font.render(line, True, color),
                (566, y),
            )
            y += 28

        self.craft_button.draw(
            screen,
            mx,
            my,
            selected=self._can_craft(recipe),
        )

    def draw(self, screen, mx, my):
        screen.fill((6, 9, 16))
        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, 38))
        pygame.draw.rect(screen, LOW_YELLOW, (0, 0, WIDTH, 38), 2)
        self.back_button.draw(screen, mx, my)
        title = FONT.render("ブレッドボード合成", True, WHITE)
        screen.blit(title, title.get_rect(center=(WIDTH // 2, 19)))

        self._draw_recipes(screen)
        self._draw_board(screen)
        self._draw_detail(screen, mx, my)

        message_rect = pygame.Rect(14, 492, 772, 92)
        pygame.draw.rect(screen, (10, 14, 22), message_rect)
        pygame.draw.rect(screen, LOW_YELLOW, message_rect, 2)
        screen.blit(
            self.small_font.render(self.message, True, WHITE),
            (28, 510),
        )
        guide = self.tiny_font.render(
            "W/S・↑↓: レシピ選択  Enter/Space: 合成  "
            "Esc/M/Backspace: 閉じる",
            True,
            LOWH,
        )
        screen.blit(guide, (28, 552))
