import json
from pathlib import Path

import pygame

from COMMON.button import Button
from COMMON.config import *
from COMMON.submenu_navigation import SubMenuNavigation
from PLAY.character_repository import load_item_masters


DOUGU_DATA_PATH = Path(__file__).resolve().parents[1] / "INFO" / "dougu.json"


def load_dougu_data(path=DOUGU_DATA_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def add_dougu_amounts(amounts, path=DOUGU_DATA_PATH):
    path = Path(path)
    try:
        try:
            data = load_dougu_data(path)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            data = {}
        totals = {}
        for entry in data.get("inventory", []):
            item_id = int(entry.get("item_id", -1))
            amount = int(entry.get("amount", 0))
            if item_id >= 0 and amount > 0:
                totals[item_id] = totals.get(item_id, 0) + amount
        for item_id, amount in amounts.items():
            item_id = int(item_id)
            amount = int(amount)
            if item_id >= 0 and amount > 0:
                totals[item_id] = totals.get(item_id, 0) + amount
        data["inventory"] = [
            {"item_id": item_id, "amount": totals[item_id]}
            for item_id in sorted(totals)
            if totals[item_id] > 0
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
            file.write("\n")
        temporary.replace(path)
        return True
    except (OSError, TypeError, ValueError):
        return False


class Dougu:
    """道具の一覧と詳細を表示するメニュー画面。"""

    LIST_X = 20
    LIST_Y = 52
    LIST_WIDTH = 330
    ROW_HEIGHT = 58
    VISIBLE_ROWS = 5

    def __init__(self, hand, money=0, data=None):
        self.canvas = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.canvas.fill((0, 0, 0, 200))
        self.hand = hand
        self.money = money
        self.data_path = DOUGU_DATA_PATH if data is None else None
        data = load_dougu_data() if data is None else data
        self.inventory = list(data.get("inventory", []))
        self.items = load_item_masters()
        self.selected_index = 0 if self.inventory else None
        self.scroll_offset = 0
        self.small_font = pygame.font.SysFont("msgothic", 20)
        self.navigation = SubMenuNavigation()

        panel_y = HEIGHT * 2 // 3
        self.button = {
            "formation": Button(20, panel_y + 20, 240, 80, "編成"),
            "move": Button(280, panel_y + 20, 240, 80, "移動"),
            "item": Button(540, panel_y + 20, 240, 80, "道具"),
            "element": Button(20, panel_y + 110, 240, 80, "素子"),
            "save": Button(280, panel_y + 110, 240, 80, "セーブ"),
            "close": Button(540, panel_y + 110, 240, 80, "閉じる"),
        }

    def refresh(self):
        if self.data_path is None:
            return
        data = load_dougu_data(self.data_path)
        self.inventory = [
            entry
            for entry in data.get("inventory", [])
            if int(entry.get("amount", 0)) > 0
        ]
        self.selected_index = 0 if self.inventory else None
        self.scroll_offset = 0
    def _row_rect(self, row):
        return pygame.Rect(
            self.LIST_X,
            self.LIST_Y + row * (self.ROW_HEIGHT + 6),
            self.LIST_WIDTH,
            self.ROW_HEIGHT,
        )

    def _ensure_selection_is_visible(self):
        if self.selected_index is None:
            return
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= self.scroll_offset + self.VISIBLE_ROWS:
            self.scroll_offset = self.selected_index - self.VISIBLE_ROWS + 1

    def _move_selection(self, amount):
        if not self.inventory:
            return
        self.selected_index = max(
            0,
            min(len(self.inventory) - 1, self.selected_index + amount),
        )
        self._ensure_selection_is_visible()

    def _selected_data(self):
        if self.selected_index is None:
            return None, None
        inventory_item = self.inventory[self.selected_index]
        item = self.items.get(str(inventory_item.get("item_id")))
        return inventory_item, item

    def _wrap_text(self, text, max_width):
        lines = []
        line = ""
        for character in str(text):
            candidate = line + character
            if line and self.small_font.size(candidate)[0] > max_width:
                lines.append(line)
                line = character
            else:
                line = candidate
        if line:
            lines.append(line)
        return lines or [""]

    def update(self, event, mx, my):
        navigation_state = self.navigation.update(event, mx, my, DOUGU)
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
            return DOUGU

        if event.type == pygame.MOUSEWHEEL:
            self.navigation.focus_content()
            self._move_selection(-event.y)
            return DOUGU

        if event.type == pygame.MOUSEMOTION:
            content_area = pygame.Rect(12, 42, 776, 350)
            if content_area.collidepoint(mx, my):
                self.navigation.focus_content()
            return DOUGU

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return DOUGU

        if self.button["close"].is_hover(mx, my):
            return MOVE
        if self.button["item"].is_hover(mx, my):
            self.navigation.focus_content()
            return DOUGU
        if self.button["element"].is_hover(mx, my):
            return ELEMENT

        if self.button["formation"].is_hover(mx, my):
            return FORMATION

        for name in ("move", "save"):
            if self.button[name].is_hover(mx, my):
                return MENU

        end = min(len(self.inventory), self.scroll_offset + self.VISIBLE_ROWS)
        for row, index in enumerate(range(self.scroll_offset, end)):
            if self._row_rect(row).collidepoint(mx, my):
                self.navigation.focus_content()
                self.selected_index = index
                break
        return DOUGU

    def _draw_inventory(self, screen):
        list_area = pygame.Rect(12, 42, 346, 350)
        detail_area = pygame.Rect(370, 42, 418, 350)
        pygame.draw.rect(screen, BLACK, list_area)
        pygame.draw.rect(screen, LOW_YELLOW, list_area, 2)
        pygame.draw.rect(screen, BLACK, detail_area)
        pygame.draw.rect(screen, LOW_YELLOW, detail_area, 2)

        if not self.inventory:
            empty_text = FONT.render("道具を持っていません", True, LOWH)
            screen.blit(empty_text, (self.LIST_X + 12, self.LIST_Y + 12))
            return

        end = min(len(self.inventory), self.scroll_offset + self.VISIBLE_ROWS)
        for row, index in enumerate(range(self.scroll_offset, end)):
            inventory_item = self.inventory[index]
            item = self.items.get(str(inventory_item.get("item_id")), {})
            rect = self._row_rect(row)
            selected = index == self.selected_index and not self.navigation.back_selected
            pygame.draw.rect(screen, LOW_BLUE if selected else (20, 20, 20), rect)
            pygame.draw.rect(screen, YELLOW if selected else LOW_YELLOW, rect, 2)
            name = FONT.render(item.get("name", "不明な道具"), True, WHITE)
            amount = self.small_font.render(
                f"× {inventory_item.get('amount', 0)}", True, WHITE
            )
            screen.blit(name, (rect.x + 12, rect.y + 8))
            screen.blit(amount, amount.get_rect(midright=(rect.right - 12, rect.centery)))

        inventory_item, item = self._selected_data()
        if item is None:
            title = FONT.render("不明な道具", True, WHITE)
            screen.blit(title, (390, 62))
            return

        title = FONT.render(item.get("name", "不明な道具"), True, YELLOW)
        amount = self.small_font.render(
            f"所持数: {inventory_item.get('amount', 0)}", True, WHITE
        )
        screen.blit(title, (390, 62))
        screen.blit(amount, (390, 100))
        pygame.draw.line(screen, LOW_YELLOW, (390, 134), (768, 134), 1)

        y = 152
        for lore in item.get("lore", []):
            for line in self._wrap_text(lore, 370):
                rendered = self.small_font.render(line, True, LOWH)
                screen.blit(rendered, (390, y))
                y += 27
            y += 5

    def draw(self, screen, mx, my):
        screen.blit(self.canvas, (0, 0))
        panel_y = HEIGHT * 2 // 3
        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, 30))
        pygame.draw.rect(screen, LOW_YELLOW, (0, 0, WIDTH, 30), 2)
        self.navigation.draw(screen, mx, my)
        title = FONT.render("道具", True, WHITE)
        screen.blit(title, (124, 2))
        money_text = self.small_font.render(f"所持金: {self.money}円", True, WHITE)
        screen.blit(money_text, money_text.get_rect(topright=(WIDTH - 10, 4)))
        self._draw_inventory(screen)
        pygame.draw.rect(screen, BLACK, (0, panel_y, WIDTH, HEIGHT - panel_y))
        pygame.draw.rect(screen, LOW_YELLOW, (0, panel_y, WIDTH, HEIGHT - panel_y), 2)
        for button in self.button.values():
            button.draw(screen, mx, my)
        pygame.draw.rect(screen, YELLOW, self.button["item"].rect, 4)
