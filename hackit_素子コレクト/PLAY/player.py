import math, pygame, sys, json, random
from COMMON.audio import audio_manager
from COMMON.config import *
from PLAY.move import Move
from PLAY.menu import Menu
from PLAY.dougu import Dougu
from PLAY.element import Element
from PLAY.formation import Formation
from PLAY.synthesis import Synthesis
from PLAY.battle import Battle
from PLAY.character_repository import load_characters, load_owned_characters, load_party_characters
from PLAY.event import Event
from save_load import SaveDataError, save_game as write_game_save

class Player:
    BATTLE_CURTAIN_FRAMES = max(1, int(FPS * 0.70))
    BATTLE_CURTAIN_COLUMNS = 10
    BATTLE_CURTAIN_ROWS = 8
    BATTLE_CURTAIN_COLUMN_STAGGER = 0.15
    RESPAWN_SAFE_STEPS = 8
    def __init__(
        self,
        name,
        map_num,
        x,
        y,
        save_slot=1,
        tutorial_stage=None,
        party_status=None,
        checkpoint=None,
    ):
        self.state = MOVE
        self.save_slot = int(save_slot)
        self.name = name
        self.money = 1000
        self.hand = []
        self.rng = random.Random()
        self.encounter_safe_steps = 0
        checkpoint_data = checkpoint if isinstance(checkpoint, dict) else {}
        checkpoint_direction = str(checkpoint_data.get("direction", FRONT))
        if checkpoint_direction not in (FRONT, BACK, LEFT, RIGHT):
            checkpoint_direction = FRONT
        self.checkpoint = {
            "map_num": int(checkpoint_data.get("map_num", map_num)),
            "x": int(checkpoint_data.get("x", x)),
            "y": int(checkpoint_data.get("y", y)),
            "direction": checkpoint_direction,
        }
        self.tutorial_stage = (
            int(tutorial_stage)
            if tutorial_stage is not None
            else (0 if int(map_num) == 1 else 3)
        )
        self.tutorial_battle_active = False
        self.tutorial_victory_stage = None
        self.move = Move(map_num, x, y)
        self.menu = Menu(self.hand, self.money)
        self.dougu = Dougu(self.hand, self.money)
        self.character_masters = load_characters()
        self.owned_characters = load_owned_characters()
        self.element = Element(self.hand, self.money, self.owned_characters)
        self.formation = Formation(self.hand, self.money, self.owned_characters)
        self.synthesis = Synthesis()
        self.party_status = []
        self._sync_party_status(source_statuses=party_status)
        self.battle = None
        self.battle_transition = None
        self.battle_transition_frame = 0
        self.curtain_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.page = 0
        self.talk = None
        self.message = None
        self.tutorial_font = pygame.font.SysFont("msgothic", 18, bold=True)
        self.canvas = pygame.Surface((WIDTH, HEIGHT/3), pygame.SRCALPHA)
        self.canvas.fill((0,0,0,200)) 
        try:
            with open(resource_path("INFO", "event.json"), "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except:
            self.data = []
        self.load_event()
        self.load_move_event(map_num)

    def load_event(self):
        self.events = []
        for i in range(len(self.data)):
            n = self.data[i]
            self.events.append(Event(n["x"],n["y"],n["img"],n["wall"],n["type"],n["data"],n["num"]))
    
    def load_move_event(self, num):
        for event in self.events:
            if event.num != num:
                continue
            self.move.event.append(event)

    def show_message(self, text):
        self.move.clear_input()
        self.state = SPEAK
        self.talk = None
        self.message = FONT.render(str(text), True, WHITE)

    def change_map(self, map_num, x, y):
        self.move.clear_input()
        self.move = Move(int(map_num), int(x), int(y))
        self.load_move_event(int(map_num))
        self.state = MOVE
        self.talk = None
        self.message = None

    def register_checkpoint(self):
        self.checkpoint = {
            "map_num": int(self.move.name),
            "x": int(self.move.rect.x),
            "y": int(self.move.rect.y),
            "direction": str(self.move.direction),
        }

    def return_to_checkpoint(self):
        self.full_restore_party()
        checkpoint = self.checkpoint
        self.change_map(
            checkpoint["map_num"],
            checkpoint["x"],
            checkpoint["y"],
        )
        self.move.direction = checkpoint["direction"]
        self.encounter_safe_steps = max(
            self.encounter_safe_steps,
            self.RESPAWN_SAFE_STEPS,
        )
    def handle_event(self, event, mx, my):
        if event.type != pygame.KEYDOWN:
            return
        elif event.key == pygame.K_SPACE and self.state in (MOVE, SPEAK) and not self.move.moving:
            self.move.clear_input()
            if self.state == SPEAK and self.talk is None:
                self.state = MOVE
                self.message = None
            else:
                self.is_event()
        if event.key == pygame.K_m and self.state != BATTLE and not self.move.moving:
            if self.state == MOVE:
                self.move.clear_input()
            elif self.state == SYNTHESIS:
                self.refresh_owned_characters()
            self.state = MENU if self.state == MOVE else MOVE

    def is_event(self):
        ex = self.move.rect.x // TILE
        ey = self.move.rect.y // TILE
        if self.move.direction == FRONT:
            ey -= 1
        elif self.move.direction == BACK:
            ey += 1
        elif self.move.direction == LEFT:
            ex -= 1
        elif self.move.direction == RIGHT:
            ex += 1
        for event in self.move.event:
            if event.x == ex and event.y == ey:
                event.interact(self)
                break

    def refresh_owned_characters(self):
        self.owned_characters = load_owned_characters()
        self.element.characters = list(self.owned_characters)
        self.formation.characters = list(self.owned_characters)

    @staticmethod
    def _status_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    def _sync_party_status(self, party=None, source_statuses=None):
        party = list(party if party is not None else load_party_characters())[:4]
        status_source = self.party_status if source_statuses is None else source_statuses
        previous = [
            status
            for status in list(status_source or [])
            if isinstance(status, dict)
        ]
        used_indices = set()
        synced = []
        for character in party:
            match_index = None
            for index, status in enumerate(previous):
                if index in used_indices:
                    continue
                if self._status_int(status.get("character_id"), -1) == character.id:
                    match_index = index
                    break
            if match_index is None:
                hp = character.hp
                sp = 100
            else:
                used_indices.add(match_index)
                status = previous[match_index]
                hp = self._status_int(status.get("hp"), character.hp)
                sp = self._status_int(status.get("sp"), 100)
            synced.append(
                {
                    "character_id": character.id,
                    "hp": max(0, min(character.hp, hp)),
                    "sp": max(0, min(100, sp)),
                }
            )
        self.party_status = synced
        return party

    def full_restore_party(self):
        party = list(load_party_characters())[:4]
        self.party_status = [
            {"character_id": character.id, "hp": character.hp, "sp": 100}
            for character in party
        ]
        return bool(party)

    def save_game(self):
        self._sync_party_status()
        try:
            data = write_game_save(self)
        except (SaveDataError, OSError, ValueError) as error:
            self.menu.message = f"セーブ失敗: {error}"
            return False
        self.menu.message = f"セーブ{self.save_slot}に保存しました  {data.saved_at}"
        return True

    def open_synthesis(self):
        self.move.clear_input()
        self.synthesis.open()
        self.state = SYNTHESIS

    def start_battle(self, enemy_ids):
        masters = {character.id: character for character in self.character_masters}
        enemies = [masters[enemy_id] for enemy_id in enemy_ids if enemy_id in masters]
        party = self._sync_party_status(load_party_characters())
        if not enemies or not party:
            return False
        if not any(status["hp"] > 0 for status in self.party_status):
            self.show_message("\u6226\u3048\u308b\u7d20\u5b50\u304c\u3044\u307e\u305b\u3093\u3002\u30bb\u30fc\u30d6\u7aef\u672b\u3067\u56de\u5fa9\u3057\u3066\u304f\u3060\u3055\u3044")
            return False
        self.move.clear_input()
        self.battle = Battle(
            party[:4],
            enemies[:4],
            self.rng,
            ally_statuses=self.party_status,
        )
        self.state = BATTLE
        self.battle_transition = "enter_curtain_close"
        self.battle_transition_frame = 0
        audio_manager.play_bgm("battle")
        return True

    def start_tutorial_battle(self, enemy_ids, victory_stage):
        started = self.start_battle(enemy_ids)
        if not started:
            return False
        self.tutorial_battle_active = True
        self.tutorial_victory_stage = int(victory_stage)
        return True
    def _begin_battle_exit_transition(self):
        if self.battle_transition is not None:
            return
        self.move.clear_input()
        self.state = BATTLE
        self.battle_transition = "exit_curtain_close"
        self.battle_transition_frame = 0

    def _finish_battle_exit(self):
        battle_outcome = self.battle.outcome if self.battle is not None else None
        if self.battle is not None:
            self.party_status = self.battle.export_ally_statuses()
        if self.tutorial_battle_active:
            if battle_outcome == "victory" and self.tutorial_victory_stage is not None:
                self.tutorial_stage = max(
                    self.tutorial_stage,
                    self.tutorial_victory_stage,
                )
            self.tutorial_battle_active = False
            self.tutorial_victory_stage = None
        self.battle = None
        if battle_outcome == "defeat":
            self.return_to_checkpoint()
        else:
            self.state = MOVE
        self.refresh_owned_characters()
        self.dougu.refresh()
        audio_manager.play_bgm("field")
    def _tick_battle_transition(self):
        self.battle_transition_frame += 1
        if self.battle_transition_frame < self.BATTLE_CURTAIN_FRAMES:
            return

        if self.battle_transition == "enter_curtain_close":
            self.battle_transition = "enter_curtain_open"
            self.battle_transition_frame = 0
        elif self.battle_transition == "enter_curtain_open":
            self.battle_transition = None
            self.battle_transition_frame = 0
        elif self.battle_transition == "exit_curtain_close":
            self._finish_battle_exit()
            self.battle_transition = "exit_curtain_open"
            self.battle_transition_frame = 0
        elif self.battle_transition == "exit_curtain_open":
            self.battle_transition = None
            self.battle_transition_frame = 0

    def _battle_curtain_progress(self):
        progress = min(
            1.0,
            self.battle_transition_frame / self.BATTLE_CURTAIN_FRAMES,
        )
        if self.battle_transition in (
            "enter_curtain_close",
            "exit_curtain_close",
        ):
            return progress
        return 1.0 - progress

    @staticmethod
    def _smooth_step(progress):
        progress = max(0.0, min(1.0, progress))
        return progress * progress * (3.0 - 2.0 * progress)

    def _draw_battle_curtain(self, screen, progress):
        self.curtain_surface.fill((0, 0, 0, 0))
        max_delay = (
            self.BATTLE_CURTAIN_ROWS - 1
            + self.BATTLE_CURTAIN_COLUMN_STAGGER
        )
        timeline = max_delay + 1.0

        for row in range(self.BATTLE_CURTAIN_ROWS):
            top = row * HEIGHT // self.BATTLE_CURTAIN_ROWS
            bottom = (row + 1) * HEIGHT // self.BATTLE_CURTAIN_ROWS
            cell_height = bottom - top
            for column in range(self.BATTLE_CURTAIN_COLUMNS):
                left = column * WIDTH // self.BATTLE_CURTAIN_COLUMNS
                right = (column + 1) * WIDTH // self.BATTLE_CURTAIN_COLUMNS
                cell_width = right - left
                delay = row + (
                    column % 2
                ) * self.BATTLE_CURTAIN_COLUMN_STAGGER
                local_progress = progress * timeline - delay
                scale = self._smooth_step(local_progress)
                if scale <= 0:
                    continue
                square_width = min(cell_width, math.ceil(cell_width * scale))
                square_height = min(cell_height, math.ceil(cell_height * scale))
                x = left + (cell_width - square_width) // 2
                y = top + (cell_height - square_height) // 2
                pygame.draw.rect(
                    self.curtain_surface,
                    BLACK,
                    (x, y, square_width, square_height),
                )
        screen.blit(self.curtain_surface, (0, 0))

    def _draw_battle_transition(self, screen, mx, my):
        if self.battle_transition in (
            "enter_curtain_close",
            "exit_curtain_open",
        ):
            self.move.draw(screen)
        elif self.battle is not None:
            self.battle.draw(screen, mx, my)
        else:
            self.move.draw(screen)

        self._draw_battle_curtain(
            screen,
            self._battle_curtain_progress(),
        )

    def _try_encounter(self, completed_step):
        if self.encounter_safe_steps > 0:
            self.encounter_safe_steps -= 1
            return False

        grid_x, grid_y = completed_step
        tile = self.move.tile_data(grid_x, grid_y)
        if not tile or tile.get("type") != "encounter":
            return False
        encounter_rate = float(tile.get("encounter_rate", 0))
        if self.rng.random() >= encounter_rate:
            return False
        enemy_ids = [int(enemy_id) for enemy_id in tile.get("enemy_ids", [])]
        if not enemy_ids:
            return False
        minimum = max(1, int(tile.get("enemy_min", 1)))
        maximum = max(minimum, int(tile.get("enemy_max", minimum)))
        count = min(len(enemy_ids), self.rng.randint(minimum, maximum))
        selected_ids = self.rng.sample(enemy_ids, count)
        encountered = self.start_battle(selected_ids)
        if encountered:
            self.encounter_safe_steps = max(0, int(tile.get("safe_steps", 0)))
        return encountered

    def _prepare_state(self, next_state):
        if next_state == self.state:
            return next_state
        if next_state == ELEMENT:
            self.element.open()
        elif next_state == FORMATION:
            self.formation.open()
        elif next_state == SAVE:
            self.save_game()
            return MENU
        return next_state


    def update(self, mx, my):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if self.battle_transition is not None:
                continue
            self.handle_event(event, mx, my)
            if self.state == MENU:
                next_state = self.menu.update(event, mx, my)
                self.state = self._prepare_state(next_state)
            elif self.state == DOUGU:
                self.state = self._prepare_state(self.dougu.update(event, mx, my))
            elif self.state == ELEMENT:
                self.state = self._prepare_state(self.element.update(event, mx, my))
            elif self.state == FORMATION:
                self.state = self._prepare_state(self.formation.update(event, mx, my))
            elif self.state == SYNTHESIS:
                next_state = self.synthesis.update(event, mx, my)
                if next_state == MOVE:
                    self.refresh_owned_characters()
                self.state = next_state
            elif self.state == BATTLE and self.battle is not None:
                next_state = self.battle.update(event, mx, my)
                if next_state == MOVE:
                    self._begin_battle_exit_transition()
                else:
                    self.state = next_state
            elif self.state == MOVE:
                self.move.handle_event(event)
        if self.battle_transition is not None:
            self._tick_battle_transition()
            return
        if self.state == BATTLE and self.battle is not None:
            self.battle.tick()
        elif self.state == MOVE:
            self.move.update()
            completed_step = self.move.consume_completed_step()
            if completed_step is not None:
                self._try_encounter(completed_step)


    def _tutorial_objective(self):
        if int(self.move.name) != 1:
            return ""
        if self.tutorial_stage <= 0:
            return "\u76ee\u7684: \u5317\u3078\u9032\u307f\u3001\u300c! \u30de\u30a8\u30c0\u300d\u306b\u8a71\u3057\u304b\u3051\u308b"
        if self.tutorial_stage == 1:
            return "\u76ee\u7684: \u53f3\u4e0a\u306e\u8a13\u7df4\u5834\u3067\u300c! \u30e4\u30de\u30b6\u30ad\u300d\u306b\u8a71\u3057\u304b\u3051\u308b"
        if self.tutorial_stage == 2:
            return "\u76ee\u7684: \u30de\u30a8\u30c0\u306b\u52dd\u5229\u3092\u5831\u544a\u3059\u308b"
        return "\u76ee\u7684: \u30de\u30c3\u30d7\u6700\u4e0a\u90e8\u4e2d\u592e\u306e\u300c\u5317\u30b2\u30fc\u30c8\u300d\u3078\u5411\u304b\u3046"

    def _draw_tutorial_objective(self, screen):
        objective = self._tutorial_objective()
        if not objective:
            return
        panel = pygame.Surface((760, 38), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 205))
        panel_rect = panel.get_rect(center=(WIDTH // 2, 27))
        screen.blit(panel, panel_rect)
        pygame.draw.rect(screen, (205, 210, 220), panel_rect, 2)
        text = self.tutorial_font.render(objective, True, (235, 235, 190))
        screen.blit(text, text.get_rect(center=panel_rect.center))
    def draw(self, screen, mx, my):
        if self.battle_transition is not None:
            self._draw_battle_transition(screen, mx, my)
            return
        if self.state == BATTLE and self.battle is not None:
            self.battle.draw(screen, mx, my)
            return
        self.move.draw(screen)
        self._draw_tutorial_objective(screen)
        if self.state == MENU: self.menu.draw(screen, mx, my)
        if self.state == DOUGU: self.dougu.draw(screen, mx, my)
        if self.state == ELEMENT: self.element.draw(screen, mx, my)
        if self.state == FORMATION: self.formation.draw(screen, mx, my)
        if self.state == SYNTHESIS: self.synthesis.draw(screen, mx, my)
        if self.state == SPEAK:
            screen.blit(self.canvas, (0, HEIGHT*2/3))
            pygame.draw.rect(screen, WHITE, (0, HEIGHT*2/3, WIDTH, HEIGHT/3), 1)
            if self.talk:
                screen.blit(self.talk.name, (10, HEIGHT*2/3+10))
                for i, text in enumerate(self.talk.pages[self.talk.page]):
                    screen.blit(text,(10,HEIGHT*2/3+50+i*28))
            elif self.message:
                screen.blit(self.message, (10, HEIGHT*2/3+10))