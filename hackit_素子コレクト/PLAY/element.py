from pathlib import Path

import pygame

from COMMON.button import Button
from COMMON.config import *
from COMMON.submenu_navigation import SubMenuNavigation
from PLAY.character_repository import load_character_amounts, load_owned_characters


class Element:
    """character.db から読み込んだ素子の一覧・詳細画面。"""

    LIST_X = 12
    LIST_Y = 42
    LIST_WIDTH = 286
    ROW_HEIGHT = 58
    VISIBLE_ROWS = 5

    def __init__(self, hand, money=0, characters=None):
        self.canvas = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.canvas.fill((0, 0, 0, 200))
        self.hand = hand
        self.money = money
        self.characters = (
            load_owned_characters() if characters is None else list(characters)
        )
        self.selected_index = 0 if self.characters else None
        self.scroll_offset = 0
        self.small_font = pygame.font.SysFont("msgothic", 18)
        self.tiny_font = pygame.font.SysFont("msgothic", 16)
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

    def open(self):
        """メニューから開いたとき、先頭の所持素子へフォーカスを戻す。"""
        self.amounts = load_character_amounts()
        self.navigation.focus_content()
        self.selected_index = 0 if self.characters else None
        self.scroll_offset = 0

    def _row_rect(self, row):
        return pygame.Rect(
            self.LIST_X + 8,
            self.LIST_Y + 10 + row * (self.ROW_HEIGHT + 6),
            self.LIST_WIDTH - 16,
            self.ROW_HEIGHT,
        )

    def _move_selection(self, amount):
        if not self.characters:
            return
        self.selected_index = max(
            0,
            min(len(self.characters) - 1, self.selected_index + amount),
        )
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= self.scroll_offset + self.VISIBLE_ROWS:
            self.scroll_offset = self.selected_index - self.VISIBLE_ROWS + 1

    def _wrap_text(self, text, max_width):
        lines = []
        line = ""
        for character in str(text):
            candidate = line + character
            if line and self.tiny_font.size(candidate)[0] > max_width:
                lines.append(line)
                line = character
            else:
                line = candidate
        if line:
            lines.append(line)
        return lines or [""]

    def _load_character_image(self, character):
        if not character.path:
            return None
        if character.path in self.image_cache:
            return self.image_cache[character.path]

        path = Path(character.path)
        if not path.is_absolute():
            path = resource_path(*path.parts)
        try:
            image = pygame.image.load(path).convert_alpha()
            image = pygame.transform.scale(image, (96, 96))
        except (FileNotFoundError, pygame.error, OSError):
            image = None
        self.image_cache[character.path] = image
        return image

    def update(self, event, mx, my):
        navigation_state = self.navigation.update(event, mx, my, ELEMENT)
        if navigation_state is not None:
            return navigation_state

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.navigation.focus_back()
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.navigation.focus_content()
            elif not self.navigation.back_selected:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self._move_selection(-1)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self._move_selection(1)
            return ELEMENT

        if event.type == pygame.MOUSEWHEEL:
            self.navigation.focus_content()
            self._move_selection(-event.y)
            return ELEMENT

        if event.type == pygame.MOUSEMOTION:
            if pygame.Rect(12, 42, 776, 350).collidepoint(mx, my):
                self.navigation.focus_content()
            return ELEMENT

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return ELEMENT

        if self.button["close"].is_hover(mx, my):
            return MOVE
        if self.button["item"].is_hover(mx, my):
            return DOUGU
        if self.button["element"].is_hover(mx, my):
            self.navigation.focus_content()
            return ELEMENT
        if self.button["formation"].is_hover(mx, my):
            return FORMATION

        for name in ("move", "save"):
            if self.button[name].is_hover(mx, my):
                return MENU

        end = min(len(self.characters), self.scroll_offset + self.VISIBLE_ROWS)
        for row, index in enumerate(range(self.scroll_offset, end)):
            if self._row_rect(row).collidepoint(mx, my):
                self.navigation.focus_content()
                self.selected_index = index
                break
        return ELEMENT

    def _draw_image(self, screen, character):
        rect = pygame.Rect(318, 54, 120, 104)
        pygame.draw.rect(screen, (18, 18, 18), rect)
        pygame.draw.rect(screen, LOW_YELLOW, rect, 2)
        image = self._load_character_image(character)
        if image is None:
            text = self.tiny_font.render("画像未設定", True, LOWH)
            screen.blit(text, text.get_rect(center=rect.center))
        else:
            screen.blit(image, image.get_rect(center=rect.center))

    def _draw_list(self, screen):
        list_area = pygame.Rect(12, 42, 286, 350)
        pygame.draw.rect(screen, BLACK, list_area)
        pygame.draw.rect(screen, LOW_YELLOW, list_area, 2)

        if not self.characters:
            screen.blit(FONT.render("所持している素子がありません", True, LOWH), (30, 62))
            return

        end = min(len(self.characters), self.scroll_offset + self.VISIBLE_ROWS)
        for row, index in enumerate(range(self.scroll_offset, end)):
            character = self.characters[index]
            rect = self._row_rect(row)
            selected = index == self.selected_index and not self.navigation.back_selected
            pygame.draw.rect(screen, LOW_BLUE if selected else (20, 20, 20), rect)
            pygame.draw.rect(screen, YELLOW if selected else LOW_YELLOW, rect, 2)
            screen.blit(FONT.render(character.name, True, WHITE), (rect.x + 10, rect.y + 5))
            amount = self.tiny_font.render(
                f"×{self.amounts.get(character.id, 0)}", True, GYELLOW
            )
            screen.blit(amount, amount.get_rect(topright=(rect.right - 8, rect.y + 8)))
            property_text = self.tiny_font.render(character.property_name, True, LOWH)
            screen.blit(property_text, (rect.x + 10, rect.y + 35))

    def _draw_detail(self, screen):
        detail_area = pygame.Rect(306, 42, 482, 350)
        pygame.draw.rect(screen, BLACK, detail_area)
        pygame.draw.rect(screen, LOW_YELLOW, detail_area, 2)
        if self.selected_index is None:
            return

        character = self.characters[self.selected_index]
        self._draw_image(screen, character)
        screen.blit(FONT.render(character.name, True, YELLOW), (450, 54))
        screen.blit(
            self.small_font.render(f"属性: {character.property_name}", True, WHITE),
            (450, 90),
        )
        technique_name = character.technique.name if character.technique else "なし"
        screen.blit(
            self.small_font.render(f"固有技: {technique_name}", True, WHITE),
            (450, 120),
        )

        stats = (
            f"HP {character.hp}   ATK {character.atk}   DEF {character.defense}",
            f"MATK {character.matk}   MDEF {character.mdef}   SPD {character.spd}",
        )
        for index, line in enumerate(stats):
            screen.blit(self.small_font.render(line, True, WHITE), (322, 174 + index * 26))

        if character.technique:
            tech = character.technique
            line = f"技威力 {tech.attack:g}   SP {tech.sp}   {tech.attribute}"
            screen.blit(self.small_font.render(line, True, GYELLOW), (322, 230))

        pygame.draw.line(screen, LOW_YELLOW, (322, 262), (772, 262), 1)
        y = 275
        for line in self._wrap_text(character.explain, 440):
            screen.blit(self.tiny_font.render(line, True, LOWH), (322, y))
            y += 22
            if y > 372:
                break

    def draw(self, screen, mx, my):
        screen.blit(self.canvas, (0, 0))
        panel_y = HEIGHT * 2 // 3
        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, 30))
        pygame.draw.rect(screen, LOW_YELLOW, (0, 0, WIDTH, 30), 2)
        self.navigation.draw(screen, mx, my)
        screen.blit(FONT.render("素子", True, WHITE), (124, 2))
        money_text = self.small_font.render(f"所持金: {self.money}円", True, WHITE)
        screen.blit(money_text, money_text.get_rect(topright=(WIDTH - 10, 4)))

        self._draw_list(screen)
        self._draw_detail(screen)
        pygame.draw.rect(screen, BLACK, (0, panel_y, WIDTH, HEIGHT - panel_y))
        pygame.draw.rect(screen, LOW_YELLOW, (0, panel_y, WIDTH, HEIGHT - panel_y), 2)
        for button in self.button.values():
            button.draw(screen, mx, my)
        pygame.draw.rect(screen, YELLOW, self.button["element"].rect, 4)
