"""Map interaction events, including staged tutorial events."""

import pygame

from COMMON.config import *


class Event:
    DIALOGUE_TYPES = ("npc", "bord", "tutorial")

    def __init__(self, x, y, img, wall, type, data, num):
        self.wall = wall
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
        self.img = pygame.image.load(resource_path(img)).convert_alpha()
        self.type = type
        self.data = data
        self.num = num
        self.page = 0
        self.pages = []
        self.name = None
        self.world_font = pygame.font.SysFont("msgothic", 16, bold=True)
        self.marker_font = pygame.font.SysFont("msgothic", 22, bold=True)
        if self.type in ("npc", "bord"):
            self._set_dialogue(self.data.get("name", ""), self.data.get("text", ""))
        elif self.type == "save":
            self.used = False
            self.active_img = pygame.image.load(
                resource_path(self.data["active_img"])
            ).convert_alpha()
        if self.type in ("npc", "tutorial"):
            self.img = pygame.transform.scale(self.img, (48, 52))

    @staticmethod
    def make_pages(texts):
        pages = []
        page = []
        for text in texts:
            if text == "*ln":
                if page:
                    pages.append(page)
                page = []
                continue
            page.append(text)
            if len(page) >= 5:
                pages.append(page)
                page = []
        if page:
            pages.append(page)
        return pages or [[""]]

    def _set_dialogue(self, name, text):
        raw_pages = self.make_pages(str(text).split("\n"))
        self.pages = [
            [FONT.render(line, True, WHITE) for line in page]
            for page in raw_pages
        ]
        self.name = FONT.render(f"{name}:", True, WHITE)
        self.page = 0

    def page_talk(self, game):
        if game.state == MOVE:
            self.page = 0
            game.state = SPEAK
            game.talk = self
            return False
        if game.state != SPEAK:
            return False
        if self.page < len(self.pages) - 1:
            self.page += 1
            return False
        self.page = 0
        game.state = MOVE
        game.talk = None
        return True

    def message_talk(self, game):
        game.full_restore_party()
        game.register_checkpoint()
        success = game.save_game()
        if success and not self.used:
            self.used = True
            self.img = self.active_img
        text = (
            "\u5168\u54e1\u306eHP\u30fbSP\u3092\u5168\u56de\u5fa9\u3057\u3066\u30bb\u30fc\u30d6\u3057\u307e\u3057\u305f"
            if success
            else "\u5168\u54e1\u306eHP\u30fbSP\u3092\u5168\u56de\u5fa9\u3057\u307e\u3057\u305f\u304c\u3001\u30bb\u30fc\u30d6\u306b\u5931\u6557\u3057\u307e\u3057\u305f"
        )
        game.show_message(text)

    def _tutorial_entry(self, game):
        stages = self.data.get("stages", {})
        return stages.get(
            str(game.tutorial_stage),
            self.data.get("default", {}),
        )

    def tutorial_talk(self, game):
        entry = self._tutorial_entry(game)
        if game.state == MOVE:
            self._set_dialogue(
                entry.get("name", self.data.get("name", "")),
                entry.get("text", ""),
            )
        finished = self.page_talk(game)
        if not finished:
            return
        if "advance_to" in entry:
            game.tutorial_stage = max(
                game.tutorial_stage,
                int(entry["advance_to"]),
            )
        enemy_ids = [
            int(enemy_id)
            for enemy_id in entry.get("battle_enemy_ids", [])
        ]
        if enemy_ids:
            victory_stage = int(
                entry.get("victory_stage", game.tutorial_stage + 1)
            )
            if not game.start_tutorial_battle(enemy_ids, victory_stage):
                game.show_message(
                    "\u30c1\u30e5\u30fc\u30c8\u30ea\u30a2\u30eb\u6226\u3092\u958b\u59cb\u3067\u304d\u307e\u305b\u3093"
                )

    def tutorial_exit(self, game):
        required_stage = int(self.data.get("required_stage", 0))
        if game.tutorial_stage < required_stage:
            game.show_message(
                self.data.get(
                    "locked_text",
                    "\u307e\u3060\u30c1\u30e5\u30fc\u30c8\u30ea\u30a2\u30eb\u304c\u7d42\u308f\u3063\u3066\u3044\u307e\u305b\u3093",
                )
            )
            return
        game.change_map(
            int(self.data["map_num"]),
            int(self.data["x"]) * TILE,
            int(self.data["y"]) * TILE,
        )

    def interact(self, game):
        if self.type in ("npc", "bord"):
            self.page_talk(game)
        elif self.type == "tutorial":
            self.tutorial_talk(game)
        elif self.type == "tutorial_exit":
            self.tutorial_exit(game)
        elif self.type == "save":
            self.message_talk(game)
        elif self.type == "synthesis":
            game.open_synthesis()

    def _draw_world_label(self, screen, text, center_x, bottom_y, color):
        label = self.world_font.render(str(text), True, color)
        rect = label.get_rect(center=(center_x, bottom_y - label.get_height() // 2))
        background = pygame.Surface((rect.width + 10, rect.height + 4), pygame.SRCALPHA)
        background.fill((0, 0, 0, 205))
        background_rect = background.get_rect(center=rect.center)
        screen.blit(background, background_rect)
        pygame.draw.rect(screen, color, background_rect, 1)
        screen.blit(label, rect)

    def draw(self, screen, s_x, s_y):
        base_x = self.rect.x - s_x
        base_y = self.rect.y - s_y
        if self.type == "tutorial_exit":
            silver = (205, 210, 220)
            gate_rect = self.img.get_rect(topleft=(base_x, base_y))
            screen.blit(self.img, gate_rect)
            self._draw_world_label(
                screen,
                "\u5317\u30b2\u30fc\u30c8",
                gate_rect.centerx,
                gate_rect.top - 3,
                silver,
            )
            return

        if self.type in ("npc", "tutorial"):
            screen.blit(self.img, (base_x - 8, base_y - 20))
            if self.type == "tutorial":
                marker = self.marker_font.render("!", True, YELLOW)
                marker_rect = marker.get_rect(center=(base_x + TILE // 2, base_y - 35))
                screen.blit(marker, marker_rect)
                full_name = str(self.data.get("name", ""))
                short_name = full_name.split(":")[-1]
                self._draw_world_label(
                    screen,
                    short_name,
                    base_x + TILE // 2,
                    base_y - 8,
                    YELLOW,
                )
            return

        screen.blit(self.img, (base_x, base_y))