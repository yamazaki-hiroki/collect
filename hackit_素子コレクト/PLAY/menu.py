import pygame
from COMMON.config import *
from COMMON.button import Button

class Menu:
    def __init__(self, hand, money=0):
        self.canvas = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.canvas.fill((0,0,0,200)) 
        self.hand = hand
        self.money = money
        self.button = {
            "formation":Button(20, HEIGHT*2/3 + 20, 240, 80, "編成"),
            "move":Button(280, HEIGHT*2/3 + 20, 240, 80, "移動"),
            "item":Button(540, HEIGHT*2/3 + 20, 240, 80, "道具"),
            "element":Button(20, HEIGHT*2/3 + 110, 240, 80, "素子"),
            "save":Button(280, HEIGHT*2/3 + 110, 240, 80, "セーブ"),
            "close":Button(540, HEIGHT*2/3 + 110, 240, 80, "閉じる"),
        }
        self.mode = None
        self.message = ""
        self.button_order = tuple(self.button)
        self.selected_index = 0
        self.guide = pygame.font.SysFont("msgothic", 18).render(
            "WASD / 矢印: 選択   Enter / Space: 決定", True, WHITE
        )

    def _selected_name(self):
        return self.button_order[self.selected_index]

    def _move_selection(self, dx=0, dy=0):
        row, column = divmod(self.selected_index, 3)
        if dx:
            column = (column + dx) % 3
        if dy:
            row = (row + dy) % 2
        self.selected_index = row * 3 + column

    def _button_index_at(self, mx, my):
        for index, name in enumerate(self.button_order):
            if self.button[name].is_hover(mx, my):
                return index
        return None

    def _activate_selected(self):
        name = self._selected_name()
        if name == "close":
            return MOVE
        if name == "element":
            return ELEMENT
        if name == "item":
            return DOUGU
        if name == "formation":
            return FORMATION
        if name == "save":
            return SAVE
        return MENU

    def update(self, event, mx, my):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                return MOVE
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self._move_selection(dx=-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._move_selection(dx=1)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self._move_selection(dy=-1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._move_selection(dy=1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self._activate_selected()
            return MENU

        if event.type == pygame.MOUSEMOTION:
            index = self._button_index_at(mx, my)
            if index is not None:
                self.selected_index = index
            return MENU

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            index = self._button_index_at(mx, my)
            if index is None:
                return MENU
            self.selected_index = index
            return self._activate_selected()

        return MENU

    def draw(self, screen, mx, my):
        screen.blit(self.canvas, (0,0))
        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, 30))
        pygame.draw.rect(screen, LOW_YELLOW, (0, 0, WIDTH, 30),2)
        screen.blit(self.guide, (10, 5))
        if self.message:
            message = FONT.render(self.message, True, YELLOW)
            screen.blit(message, message.get_rect(center=(WIDTH // 2, 70)))
        money_text = FONT.render(f"所持金: {self.money}円", True, WHITE)
        screen.blit(money_text, money_text.get_rect(topright=(WIDTH-10, 2)))
        pygame.draw.rect(screen, BLACK, (0, HEIGHT*2/3, WIDTH, HEIGHT/3))
        pygame.draw.rect(screen, LOW_YELLOW, (0, HEIGHT*2/3, WIDTH, HEIGHT/3),2)
        for index, name in enumerate(self.button_order):
            self.button[name].draw(screen, mx, my, index == self.selected_index)
