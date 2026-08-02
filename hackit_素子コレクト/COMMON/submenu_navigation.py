import pygame

from COMMON.button import Button
from COMMON.config import *


class SubMenuNavigation:
    """サブメニュー共通の戻る・閉じる操作。"""

    def __init__(self):
        font = pygame.font.SysFont("msgothic", 16)
        self.back_button = Button(8, 3, 104, 24, "← 戻る", font=font)
        self.back_selected = False

    def focus_back(self):
        self.back_selected = True

    def focus_content(self):
        self.back_selected = False

    def update(self, event, mx, my, current_state=None):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_m):
                return MOVE
            if event.key == pygame.K_BACKSPACE:
                return MENU
            if (
                self.back_selected
                and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
            ):
                return MENU
            if (
                self.back_selected
                and event.key in (pygame.K_DOWN, pygame.K_s)
            ):
                self.focus_content()
                return current_state

        if event.type == pygame.MOUSEMOTION and self.back_button.is_hover(mx, my):
            self.focus_back()

        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.back_button.is_hover(mx, my)
        ):
            return MENU

        return None

    def draw(self, screen, mx, my):
        self.back_button.draw(screen, mx, my, self.back_selected)
