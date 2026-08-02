"""Title screen and three-slot save selection UI."""

from pathlib import Path

import pygame

from COMMON.config import *
from save_load import (
    SAVE_DIR,
    SAVE_SLOT_COUNT,
    SaveDataError,
    list_save_slots,
    migrate_legacy_save,
)


NEW_GAME = "new_game"
CONTINUE_GAME = "continue_game"


class TitleScreen:
    BUTTON_RECTS = (
        pygame.Rect(250, 380, 300, 70),
        pygame.Rect(250, 470, 300, 70),
    )
    SILVER = (205, 210, 220)
    BRIGHT_SILVER = (238, 242, 248)
    DARK_SILVER = (105, 110, 120)
    SLOT_RECTS = tuple(
        pygame.Rect(145, 250 + index * 92, 510, 72)
        for index in range(SAVE_SLOT_COUNT)
    )

    def __init__(self, save_dir=None):
        self.save_dir = Path(save_dir) if save_dir else SAVE_DIR
        self.mode = "main"
        self.slot_action = None
        self.selected_index = 0
        self.selected_slot_index = 0
        self.message = ""
        self.small_font = pygame.font.SysFont("msgothic", 18)
        self.medium_font = pygame.font.SysFont("msgothic", 26)
        self.button_font = pygame.font.SysFont("msgothic", 30, bold=True)
        self.background = self._load_cover("\u30bf\u30a4\u30c8\u30eb\u80cc\u666f.png", (WIDTH, HEIGHT))
        self.logo = self._load_contain("\u30bf\u30a4\u30c8\u30eb\u6587\u5b57.png", (680, 260))
        if save_dir is None:
            try:
                migrate_legacy_save()
            except SaveDataError as error:
                self.message = f"\u65e7\u30bb\u30fc\u30d6\u306e\u79fb\u884c\u5931\u6557: {error}"
        self.refresh_save_status()

    @staticmethod
    def _load_image(filename):
        path = resource_path("INFO", "RESOURCE", filename)
        return pygame.image.load(path).convert_alpha()

    @classmethod
    def _load_contain(cls, filename, size):
        source = cls._load_image(filename)
        scale = min(size[0] / source.get_width(), size[1] / source.get_height())
        scaled_size = (
            max(1, round(source.get_width() * scale)),
            max(1, round(source.get_height() * scale)),
        )
        return pygame.transform.smoothscale(source, scaled_size)

    @classmethod
    def _load_cover(cls, filename, size):
        source = cls._load_image(filename)
        scale = max(size[0] / source.get_width(), size[1] / source.get_height())
        scaled_size = (
            max(1, round(source.get_width() * scale)),
            max(1, round(source.get_height() * scale)),
        )
        scaled = pygame.transform.smoothscale(source, scaled_size)
        result = pygame.Surface(size, pygame.SRCALPHA)
        source_rect = scaled.get_rect(center=(size[0] // 2, size[1] // 2))
        result.blit(scaled, source_rect)
        return result

    def refresh_save_status(self):
        self.slot_infos = list_save_slots(self.save_dir)
        self.continue_available = any(
            info["data"] is not None for info in self.slot_infos
        )

    def set_message(self, message):
        self.message = str(message)
        self.refresh_save_status()

    @staticmethod
    def _index_at(rects, mx, my):
        for index, rect in enumerate(rects):
            if rect.collidepoint(mx, my):
                return index
        return None

    def _open_slots(self, action):
        self.refresh_save_status()
        self.mode = "slots"
        self.slot_action = action
        self.message = ""
        if action == CONTINUE_GAME:
            valid_indices = [
                index
                for index, info in enumerate(self.slot_infos)
                if info["data"] is not None
            ]
            if not valid_indices:
                self.mode = "main"
                self.message = "\u30bb\u30fc\u30d6\u30c7\u30fc\u30bf\u304c\u3042\u308a\u307e\u305b\u3093"
                return
            self.selected_slot_index = valid_indices[0]
        else:
            self.selected_slot_index = 0

    def _activate_main(self):
        if self.selected_index == 0:
            self._open_slots(NEW_GAME)
        else:
            self._open_slots(CONTINUE_GAME)
        return None

    def _activate_slot(self):
        info = self.slot_infos[self.selected_slot_index]
        slot = int(info["slot"])
        if self.slot_action == CONTINUE_GAME and info["data"] is None:
            self.message = (
                "\u3053\u306e\u30bb\u30fc\u30d6\u306f\u8aad\u307f\u8fbc\u3081\u307e\u305b\u3093"
                if info["exists"]
                else "\u3053\u306e\u30b9\u30ed\u30c3\u30c8\u306f\u7a7a\u3067\u3059"
            )
            return None
        return self.slot_action, slot

    def update(self, event, mx, my):
        if event.type == pygame.KEYDOWN:
            if self.mode == "slots" and event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.mode = "main"
                self.slot_action = None
                self.message = ""
                return None

            previous_keys = (pygame.K_UP, pygame.K_w, pygame.K_LEFT, pygame.K_a)
            next_keys = (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT, pygame.K_d)
            accept_keys = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
            if self.mode == "main":
                if event.key in previous_keys:
                    self.selected_index = (self.selected_index - 1) % 2
                elif event.key in next_keys:
                    self.selected_index = (self.selected_index + 1) % 2
                elif event.key in accept_keys:
                    return self._activate_main()
            else:
                if event.key in previous_keys:
                    self.selected_slot_index = (
                        self.selected_slot_index - 1
                    ) % SAVE_SLOT_COUNT
                elif event.key in next_keys:
                    self.selected_slot_index = (
                        self.selected_slot_index + 1
                    ) % SAVE_SLOT_COUNT
                elif event.key in accept_keys:
                    return self._activate_slot()
            return None

        if event.type == pygame.MOUSEMOTION:
            rects = self.BUTTON_RECTS if self.mode == "main" else self.SLOT_RECTS
            index = self._index_at(rects, mx, my)
            if index is not None:
                if self.mode == "main":
                    self.selected_index = index
                else:
                    self.selected_slot_index = index
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            rects = self.BUTTON_RECTS if self.mode == "main" else self.SLOT_RECTS
            index = self._index_at(rects, mx, my)
            if index is None:
                return None
            if self.mode == "main":
                self.selected_index = index
                return self._activate_main()
            self.selected_slot_index = index
            return self._activate_slot()
        return None

    def _draw_background(self, screen):
        screen.blit(self.background, (0, 0))
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 65))
        screen.blit(shade, (0, 0))
        logo_rect = self.logo.get_rect(center=(WIDTH // 2, 145 if self.mode == "slots" else 170))
        screen.blit(self.logo, logo_rect)

    def _draw_main(self, screen):
        labels = ("\u306f\u3058\u3081\u304b\u3089", "\u7d9a\u304d\u304b\u3089")
        for index, (rect, label) in enumerate(zip(self.BUTTON_RECTS, labels)):
            enabled = index == 0 or self.continue_available
            selected = index == self.selected_index
            panel = pygame.Surface(rect.size, pygame.SRCALPHA)
            panel.fill((10, 14, 20, 195 if selected else 165))
            screen.blit(panel, rect)

            border_color = (
                self.BRIGHT_SILVER
                if selected and enabled
                else self.SILVER if enabled else self.DARK_SILVER
            )
            pygame.draw.rect(screen, (0, 0, 0), rect.inflate(6, 6), 2)
            pygame.draw.rect(screen, border_color, rect, 3 if selected else 2)

            text_color = (
                self.BRIGHT_SILVER
                if selected and enabled
                else self.SILVER if enabled else self.DARK_SILVER
            )
            label_surface = self.button_font.render(label, True, text_color)
            label_y = rect.centery if enabled else rect.centery - 8
            screen.blit(
                label_surface,
                label_surface.get_rect(center=(rect.centerx, label_y)),
            )
            if not enabled:
                unavailable = self.small_font.render(
                    "\u30bb\u30fc\u30d6\u30c7\u30fc\u30bf\u306a\u3057",
                    True,
                    self.DARK_SILVER,
                )
                screen.blit(
                    unavailable,
                    unavailable.get_rect(center=(rect.centerx, rect.bottom - 13)),
                )

        guide = self.small_font.render(
            "W/S\u30fb\u77e2\u5370: \u9078\u629e  Enter/Space: \u6c7a\u5b9a",
            True,
            self.SILVER,
        )
        screen.blit(guide, guide.get_rect(center=(WIDTH // 2, 602)))

    def _slot_lines(self, info):
        data = info["data"]
        if data is None:
            if info["exists"]:
                return "\u8aad\u307f\u8fbc\u307f\u4e0d\u53ef", info["error"]
            return "\u7a7a\u304d", ""
        player = data.player
        stamp = data.saved_at.replace("T", " ")[:19]
        detail = f"MAP {player['map_num']}   ({player['x']}, {player['y']})"
        return stamp, detail

    def _draw_slots(self, screen):
        panel = pygame.Surface((570, 405), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 190))
        screen.blit(panel, (115, 208))
        heading_text = (
            "\u65b0\u3057\u304f\u59cb\u3081\u308b\u30b9\u30ed\u30c3\u30c8"
            if self.slot_action == NEW_GAME
            else "\u30ed\u30fc\u30c9\u3059\u308b\u30b9\u30ed\u30c3\u30c8"
        )
        heading = self.medium_font.render(heading_text, True, WHITE)
        screen.blit(heading, heading.get_rect(center=(WIDTH // 2, 225)))

        for index, (rect, info) in enumerate(zip(self.SLOT_RECTS, self.slot_infos)):
            selected = index == self.selected_slot_index
            pygame.draw.rect(screen, (15, 15, 15), rect)
            pygame.draw.rect(screen, YELLOW if selected else LOW_YELLOW, rect, 4 if selected else 2)
            label = self.medium_font.render(f"\u30bb\u30fc\u30d6 {info['slot']}", True, WHITE)
            screen.blit(label, (rect.x + 18, rect.y + 10))
            first, second = self._slot_lines(info)
            color = RED if info["exists"] and info["data"] is None else LOWH
            first_surface = self.small_font.render(first, True, color)
            screen.blit(first_surface, (rect.x + 170, rect.y + 11))
            if second:
                second_surface = self.small_font.render(second, True, LOWH)
                screen.blit(second_surface, (rect.x + 170, rect.y + 40))
            if self.slot_action == NEW_GAME and info["data"] is not None:
                overwrite = self.small_font.render("\u4f7f\u7528\u4e2d", True, YELLOW)
                screen.blit(overwrite, (rect.right - 80, rect.y + 40))

        guide = self.small_font.render("W/S\u30fb\u77e2\u5370: \u9078\u629e  Enter/Space: \u6c7a\u5b9a  Esc/Backspace: \u623b\u308b", True, WHITE)
        screen.blit(guide, guide.get_rect(center=(WIDTH // 2, 570)))

    def draw(self, screen, mx, my):
        self._draw_background(screen)
        if self.mode == "main":
            self._draw_main(screen)
        else:
            self._draw_slots(screen)
        if self.message:
            message = self.small_font.render(self.message, True, YELLOW)
            screen.blit(message, message.get_rect(center=(WIDTH // 2, 630)))