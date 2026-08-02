"""所持している素子から最大4人を選ぶ編成画面。"""

from pathlib import Path

import pygame

from COMMON.button import Button
from COMMON.config import *
from COMMON.submenu_navigation import SubMenuNavigation
from PLAY.character_repository import (
    load_character_amounts,
    load_party_ids,
    save_party_ids,
)


class Formation:
    MAX_PARTY = 4
    LIST_X = 12
    LIST_Y = 42
    LIST_WIDTH = 374
    ROW_HEIGHT = 58
    VISIBLE_ROWS = 5

    def __init__(self, hand, money=0, characters=None, party_path=None):
        self.canvas = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.canvas.fill((0, 0, 0, 220))
        self.hand = hand
        self.money = money
        self.characters = list(characters or [])
        self.party_path = Path(party_path) if party_path else resource_path("INFO", "party.json")
        self.party_ids = []
        self.focus = "roster"
        self.roster_index = 0
        self.party_index = 0
        self.scroll_offset = 0
        self.message = "Enter / Space: 編成に追加"
        self.small_font = pygame.font.SysFont("msgothic", 18)
        self.tiny_font = pygame.font.SysFont("msgothic", 15)
        self.navigation = SubMenuNavigation()
        self.image_cache = {}
        self.amounts = load_character_amounts()

        panel_y = HEIGHT * 2 // 3
        self.button = {
            "formation": Button(20, panel_y + 20, 240, 80, "編成"),
            "move": Button(280, panel_y + 20, 240, 80, "移動"),
            "item": Button(540, panel_y + 20, 240, 80, "道具"),
            "element": Button(20, panel_y + 110, 240, 80, "素子"),
            "save": Button(280, panel_y + 110, 240, 80, "セーブ"),
            "close": Button(540, panel_y + 110, 240, 80, "閉じる"),
        }
        self.open()

    def open(self):
        self.amounts = load_character_amounts()
        owned_ids = [character.id for character in self.characters]
        self.party_ids = [
            value for value in load_party_ids(self.party_path, owned_ids)
            if value in owned_ids
        ][:self.MAX_PARTY]
        self.navigation.focus_content()
        self.focus = "roster"
        self.roster_index = 0
        self.party_index = 0
        self.scroll_offset = 0
        self.message = "Enter / Space: 編成に追加"

    def _save(self):
        save_party_ids(self.party_ids, self.party_path)

    def _move_roster(self, amount):
        if not self.characters:
            return
        self.roster_index = max(0, min(len(self.characters) - 1, self.roster_index + amount))
        if self.roster_index < self.scroll_offset:
            self.scroll_offset = self.roster_index
        elif self.roster_index >= self.scroll_offset + self.VISIBLE_ROWS:
            self.scroll_offset = self.roster_index - self.VISIBLE_ROWS + 1

    def _move_party(self, amount):
        if not self.party_ids:
            self.party_index = 0
            return
        self.party_index = max(0, min(len(self.party_ids) - 1, self.party_index + amount))

    def _add_selected(self):
        if not self.characters:
            self.message = "所持している素子がありません"
            return
        character = self.characters[self.roster_index]
        if character.id in self.party_ids:
            self.message = f"{character.name}は編成済みです"
            return
        if len(self.party_ids) >= self.MAX_PARTY:
            self.message = "編成できる素子は最大4人です"
            return
        self.party_ids.append(character.id)
        self.party_index = len(self.party_ids) - 1
        self._save()
        self.message = f"{character.name}を編成に追加しました"

    def _remove_selected(self):
        if not self.party_ids:
            self.message = "編成されている素子がいません"
            return
        character_id = self.party_ids.pop(self.party_index)
        character = next((item for item in self.characters if item.id == character_id), None)
        self.party_index = max(0, min(self.party_index, len(self.party_ids) - 1))
        self._save()
        name = character.name if character else str(character_id)
        self.message = f"{name}を編成から外しました"

    def _row_rect(self, visible_row):
        return pygame.Rect(
            self.LIST_X + 8,
            self.LIST_Y + 32 + visible_row * (self.ROW_HEIGHT + 5),
            self.LIST_WIDTH - 16,
            self.ROW_HEIGHT,
        )

    @staticmethod
    def _slot_rect(index):
        return pygame.Rect(408, 74 + index * 78, 372, 68)

    def _load_image(self, character):
        key = character.path
        if key in self.image_cache:
            return self.image_cache[key]
        image = None
        if key:
            path = Path(key)
            if not path.is_absolute():
                path = resource_path(*path.parts)
            try:
                image = pygame.image.load(path).convert_alpha()
                image = pygame.transform.scale(image, (48, 48))
            except (FileNotFoundError, pygame.error, OSError):
                image = None
        self.image_cache[key] = image
        return image

    def _character_for_party(self, index):
        if not (0 <= index < len(self.party_ids)):
            return None
        character_id = self.party_ids[index]
        return next((item for item in self.characters if item.id == character_id), None)

    def update(self, event, mx, my):
        navigation_state = self.navigation.update(event, mx, my, FORMATION)
        if navigation_state is not None:
            return navigation_state

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                if self.focus == "party":
                    self.focus = "roster"
                else:
                    self.navigation.focus_back()
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.navigation.focus_content()
                self.focus = "party" if self.party_ids else "roster"
            elif event.key in (pygame.K_UP, pygame.K_w):
                if self.focus == "party":
                    self._move_party(-1)
                else:
                    self._move_roster(-1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                if self.focus == "party":
                    self._move_party(1)
                else:
                    self._move_roster(1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                if self.focus == "party":
                    self._remove_selected()
                else:
                    self._add_selected()
            return FORMATION

        if event.type == pygame.MOUSEWHEEL:
            self.navigation.focus_content()
            self.focus = "roster"
            self._move_roster(-event.y)
            return FORMATION

        if event.type == pygame.MOUSEMOTION:
            end = min(len(self.characters), self.scroll_offset + self.VISIBLE_ROWS)
            for visible, index in enumerate(range(self.scroll_offset, end)):
                if self._row_rect(visible).collidepoint(mx, my):
                    self.navigation.focus_content()
                    self.focus = "roster"
                    self.roster_index = index
                    return FORMATION
            for index in range(self.MAX_PARTY):
                if self._slot_rect(index).collidepoint(mx, my):
                    self.navigation.focus_content()
                    self.focus = "party"
                    self.party_index = min(index, max(0, len(self.party_ids) - 1))
                    return FORMATION
            return FORMATION

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return FORMATION

        if self.button["close"].is_hover(mx, my):
            return MOVE
        if self.button["element"].is_hover(mx, my):
            return ELEMENT
        if self.button["item"].is_hover(mx, my):
            return DOUGU
        if self.button["formation"].is_hover(mx, my):
            return FORMATION
        for name in ("move", "save"):
            if self.button[name].is_hover(mx, my):
                return MENU

        end = min(len(self.characters), self.scroll_offset + self.VISIBLE_ROWS)
        for visible, index in enumerate(range(self.scroll_offset, end)):
            if self._row_rect(visible).collidepoint(mx, my):
                self.focus = "roster"
                self.roster_index = index
                self._add_selected()
                return FORMATION
        for index in range(len(self.party_ids)):
            if self._slot_rect(index).collidepoint(mx, my):
                self.focus = "party"
                self.party_index = index
                self._remove_selected()
                return FORMATION
        return FORMATION

    def _draw_roster(self, screen):
        area = pygame.Rect(self.LIST_X, self.LIST_Y, self.LIST_WIDTH, 350)
        pygame.draw.rect(screen, BLACK, area)
        pygame.draw.rect(screen, LOW_YELLOW, area, 2)
        screen.blit(self.small_font.render("所持素子（決定で追加）", True, WHITE), (24, 49))
        if not self.characters:
            screen.blit(self.small_font.render("所持素子がありません", True, LOWH), (30, 90))
            return

        end = min(len(self.characters), self.scroll_offset + self.VISIBLE_ROWS)
        for visible, index in enumerate(range(self.scroll_offset, end)):
            character = self.characters[index]
            rect = self._row_rect(visible)
            selected = (
                self.focus == "roster"
                and index == self.roster_index
                and not self.navigation.back_selected
            )
            pygame.draw.rect(screen, LOW_BLUE if selected else (18, 20, 28), rect)
            pygame.draw.rect(screen, YELLOW if selected else LOW_YELLOW, rect, 3 if selected else 1)
            image = self._load_image(character)
            image_rect = pygame.Rect(rect.x + 5, rect.y + 5, 48, 48)
            if image:
                screen.blit(image, image_rect)
            else:
                pygame.draw.rect(screen, (35, 35, 45), image_rect)
                screen.blit(self.tiny_font.render("?", True, LOWH), (image_rect.x + 19, image_rect.y + 14))
            color = GYELLOW if character.id in self.party_ids else WHITE
            screen.blit(self.small_font.render(character.name, True, color), (rect.x + 62, rect.y + 7))
            amount = self.tiny_font.render(
                f"×{self.amounts.get(character.id, 0)}", True, GYELLOW
            )
            screen.blit(amount, amount.get_rect(topright=(rect.right - 8, rect.y + 9)))
            stats = f"HP {character.hp}  ATK {character.atk}  SPD {character.spd}"
            screen.blit(self.tiny_font.render(stats, True, LOWH), (rect.x + 62, rect.y + 34))

    def _draw_party(self, screen):
        area = pygame.Rect(398, self.LIST_Y, 390, 350)
        pygame.draw.rect(screen, BLACK, area)
        pygame.draw.rect(screen, LOW_YELLOW, area, 2)
        title = f"バトル編成 {len(self.party_ids)}/{self.MAX_PARTY}（決定で外す）"
        screen.blit(self.small_font.render(title, True, WHITE), (410, 49))
        for index in range(self.MAX_PARTY):
            rect = self._slot_rect(index)
            selected = (
                self.focus == "party"
                and index == self.party_index
                and not self.navigation.back_selected
            )
            pygame.draw.rect(screen, LOW_BLUE if selected else (18, 20, 28), rect)
            pygame.draw.rect(screen, YELLOW if selected else LOW_YELLOW, rect, 3 if selected else 1)
            screen.blit(self.tiny_font.render(f"{index + 1}", True, LOWH), (rect.x + 8, rect.y + 25))
            character = self._character_for_party(index)
            if character is None:
                empty = self.small_font.render("空き", True, GRAY)
                screen.blit(empty, empty.get_rect(center=rect.center))
                continue
            image = self._load_image(character)
            image_rect = pygame.Rect(rect.x + 30, rect.y + 10, 48, 48)
            if image:
                screen.blit(image, image_rect)
            screen.blit(self.small_font.render(character.name, True, WHITE), (rect.x + 88, rect.y + 11))
            line = f"{character.property_name}  HP {character.hp}  SPD {character.spd}"
            screen.blit(self.tiny_font.render(line, True, LOWH), (rect.x + 88, rect.y + 39))

    def draw(self, screen, mx, my):
        screen.blit(self.canvas, (0, 0))
        panel_y = HEIGHT * 2 // 3
        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, 30))
        pygame.draw.rect(screen, LOW_YELLOW, (0, 0, WIDTH, 30), 2)
        self.navigation.draw(screen, mx, my)
        screen.blit(FONT.render("編成", True, WHITE), (124, 2))
        guide = self.tiny_font.render("←→: 欄移動  ↑↓: 選択  Enter/Space: 追加・解除", True, WHITE)
        screen.blit(guide, guide.get_rect(topright=(WIDTH - 10, 6)))
        self._draw_roster(screen)
        self._draw_party(screen)
        message = self.small_font.render(self.message, True, YELLOW)
        screen.blit(message, (18, 399))

        pygame.draw.rect(screen, BLACK, (0, panel_y, WIDTH, HEIGHT - panel_y))
        pygame.draw.rect(screen, LOW_YELLOW, (0, panel_y, WIDTH, HEIGHT - panel_y), 2)
        for button in self.button.values():
            button.draw(screen, mx, my)
        pygame.draw.rect(screen, YELLOW, self.button["formation"].rect, 4)
