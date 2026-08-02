"""素子同士のバトル画面と、最大4人分のターン行動予約。"""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import random

import pygame

from COMMON.audio import audio_manager
from COMMON.config import *
from PLAY.character_repository import (
    ElementCharacter,
    Technique,
    apply_character_amount_changes,
    load_item_masters,
)


@dataclass
class Combatant:
    character: ElementCharacter
    side: str
    current_hp: int
    current_sp: int = 100
    atk_bonus: float = 1.0
    damage_multiplier: float = 1.0
    ko_animation_frame: int = 0
    ko_animation_active: bool = False
    ko_animation_complete: bool = False

    @property
    def alive(self):
        return self.current_hp > 0

    @property
    def max_hp(self):
        return max(1, self.character.hp)


@dataclass
class PendingAction:
    actor: Combatant
    technique: Technique
    targets: list[Combatant]


class Battle:
    """敵を左、味方を右へ縦に4人まで表示するバトル。"""

    MAX_MEMBERS = 4
    UI_TOP = 390
    LEFT_PANEL = pygame.Rect(0, UI_TOP, 230, HEIGHT - UI_TOP)
    CENTER_PANEL = pygame.Rect(230, UI_TOP, 340, HEIGHT - UI_TOP)
    RIGHT_PANEL = pygame.Rect(570, UI_TOP, 230, HEIGHT - UI_TOP)
    ROW_HEIGHT = 38
    VISIBLE_ALLIES = 4
    PLANNED_COLOR = (70, 210, 255)
    ATTACK_FRAMES = 10
    IMPACT_FRAMES = 14
    KO_FRAMES = max(1, int(FPS * 0.75))
    KO_DROP_DISTANCE = 72
    MESSAGE_FRAMES = int(FPS * 1.5)
    ACTION_MESSAGE_RECT = pygame.Rect(18, 195, 764, 187)
    SOCKET_ITEM_ID = 3
    SOCKET_MIN_CAPTURE_RATE = 0.25
    SOCKET_MAX_CAPTURE_RATE = 0.90
    BATTERY_HEAL_RATES = {1: 0.40, 2: 0.70, 4: 0.20}
    CAPTURE_THROW_FRAMES = max(1, int(FPS * 0.55))
    CAPTURE_SHAKE_FRAMES = max(1, int(FPS * 1.35))
    CAPTURE_RESULT_FRAMES = max(1, int(FPS * 1.10))

    def __init__(
        self,
        allies,
        enemies,
        rng=None,
        item_data=None,
        item_path=None,
        character_inventory_path=None,
        party_path=None,
        ally_statuses=None,
    ):
        self.rng = rng or random.Random()
        ally_list = list(allies)[:self.MAX_MEMBERS]
        status_list = list(ally_statuses or [])
        self.allies = []
        for index, character in enumerate(ally_list):
            status = status_list[index] if index < len(status_list) else {}
            status_matches = int(status.get("character_id", character.id)) == character.id
            current_hp = (
                int(status.get("hp", character.hp))
                if status_matches
                else character.hp
            )
            current_sp = (
                int(status.get("sp", 100))
                if status_matches
                else 100
            )
            self.allies.append(
                Combatant(
                    character,
                    "ally",
                    max(0, min(character.hp, current_hp)),
                    max(0, min(100, current_sp)),
                )
            )
        self.enemies = [
            Combatant(character, "enemy", character.hp)
            for character in list(enemies)[:self.MAX_MEMBERS]
        ]
        self.focus = "command"
        self.command_index = 0
        self.enemy_index = 0
        self.ally_index = 0
        self.skill_index = 0
        self.item_index = 0
        self.ally_scroll = 0
        self.panel_mode = "command"
        self.pending_action = None
        self.pending_item_id = None
        self.planned_actions = {}
        self.target_side = None
        self.message = "味方の素子を選び、4人分の行動を決めてください"
        self.outcome = None
        self.turn_number = 1
        self.resolving_turn = False
        self.action_queue = []
        self.current_action = None
        self.animation_phase = None
        self.animation_frame = 0
        self.animation_targets = []
        self.action_comment = ""
        self.resolved_actions = []
        self.image_cache = {}
        self.small_font = pygame.font.SysFont("msgothic", 18)
        self.tiny_font = pygame.font.SysFont("msgothic", 15)
        self.title_font = pygame.font.SysFont("msgothic", 25)
        self.item_path = (
            Path(item_path)
            if item_path is not None
            else resource_path("INFO", "dougu.json")
        )
        self.persist_item_inventory = item_data is None or item_path is not None
        self.character_inventory_path = character_inventory_path
        self.party_path = party_path
        self.item_data = (
            item_data
            if item_data is not None
            else self._load_items(self.item_path)
        )
        self.items = [
            dict(entry)
            for entry in self.item_data.get("inventory", [])
            if int(entry.get("amount", 0)) > 0
        ]
        self.item_masters = self.item_data.get("items", {})
        self.combatant_positions = {}
        self.capture_active = False
        self.capture_phase = None
        self.capture_frame = 0
        self.capture_target = None
        self.capture_rate = 0.0
        self.capture_success = False
        self.capture_result_applied = False
        self.capture_item_name = ""
        self.capture_image = self._load_capture_image()

    @staticmethod
    def _load_items(item_path=None):
        path = Path(item_path) if item_path else resource_path("INFO", "dougu.json")
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            data["items"] = load_item_masters()
            return data
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {"inventory": [], "items": load_item_masters()}

    def _write_item_inventory(self, items):
        if not self.persist_item_inventory:
            return True
        try:
            try:
                with open(self.item_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                data = {}
            data["inventory"] = items
            self.item_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.item_path.with_suffix(self.item_path.suffix + ".tmp")
            with open(temporary, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
                file.write(chr(10))
            temporary.replace(self.item_path)
            return True
        except OSError:
            return False

    def _consume_item(self, item_id):
        updated = [dict(entry) for entry in self.items]
        index = next(
            (
                index
                for index, entry in enumerate(updated)
                if int(entry.get("item_id", -1)) == int(item_id)
                and int(entry.get("amount", 0)) > 0
            ),
            None,
        )
        if index is None:
            return False
        updated[index]["amount"] = int(updated[index].get("amount", 0)) - 1
        updated = [entry for entry in updated if int(entry.get("amount", 0)) > 0]
        if not self._write_item_inventory(updated):
            return False
        self.items = updated
        self.item_index = max(0, min(self.item_index, len(self.items) - 1))
        return True

    def _item_name(self, item_id):
        master = self.item_masters.get(str(item_id), {})
        return master.get("name", "不明な道具")

    @classmethod
    def _capture_rate(cls, target):
        hp_ratio = max(0.0, min(1.0, target.current_hp / target.max_hp))
        missing_hp_ratio = 1.0 - hp_ratio
        return cls.SOCKET_MIN_CAPTURE_RATE + missing_hp_ratio * (
            cls.SOCKET_MAX_CAPTURE_RATE - cls.SOCKET_MIN_CAPTURE_RATE
        )

    @staticmethod
    def _alive(combatants):
        return [combatant for combatant in combatants if combatant.alive]

    def export_ally_statuses(self):
        return [
            {
                "character_id": combatant.character.id,
                "hp": max(0, min(combatant.max_hp, int(combatant.current_hp))),
                "sp": max(0, min(100, int(combatant.current_sp))),
            }
            for combatant in self.allies
        ]
    @staticmethod
    def _start_ko_animation(combatant):
        if combatant.ko_animation_active or combatant.ko_animation_complete:
            return
        combatant.ko_animation_frame = 0
        combatant.ko_animation_active = True

    def _tick_ko_animations(self):
        for combatant in self.allies + self.enemies:
            if not combatant.ko_animation_active:
                continue
            combatant.ko_animation_frame += 1
            if combatant.ko_animation_frame >= self.KO_FRAMES:
                combatant.ko_animation_frame = self.KO_FRAMES
                combatant.ko_animation_active = False
                combatant.ko_animation_complete = True

    def _selected_enemy(self):
        if not self.enemies:
            return None
        self.enemy_index = max(0, min(self.enemy_index, len(self.enemies) - 1))
        return self.enemies[self.enemy_index]

    def _selected_ally(self):
        if not self.allies:
            return None
        self.ally_index = max(0, min(self.ally_index, len(self.allies) - 1))
        return self.allies[self.ally_index]

    def _ensure_ally_visible(self):
        self.ally_scroll = 0

    @staticmethod
    def _move_index(index, amount, length):
        if length <= 0:
            return 0
        return (index + amount) % length

    def _techniques_for_selected_ally(self):
        ally = self._selected_ally()
        return ally.character.techniques if ally is not None else ()

    def _open_skills(self):
        ally = self._selected_ally()
        if ally is None or not ally.alive:
            self.message = "行動できる味方を選んでください"
            return
        self.pending_action = None
        self.target_side = None
        self.panel_mode = "skills"
        self.focus = "skill"
        self.skill_index = 0
        status = "（登録済み・選び直せます）" if id(ally) in self.planned_actions else ""
        self.message = f"{ally.character.name}の技を選択{status}"

    def _target_candidates(self, technique):
        code = technique.target_code
        if code in ("enemy_single", "enemy_all", "random_enemy"):
            return self._alive(self.enemies)
        if code in ("ally_single", "ally_all"):
            return self._alive(self.allies)
        if code == "self":
            actor = self._selected_ally()
            return [actor] if actor is not None and actor.alive else []
        return []

    def _choose_skill(self):
        ally = self._selected_ally()
        techniques = self._techniques_for_selected_ally()
        if ally is None or not techniques:
            self.message = "使用できる技がありません"
            return
        self.skill_index = max(0, min(self.skill_index, len(techniques) - 1))
        technique = techniques[self.skill_index]
        if ally.current_sp < technique.sp:
            self.message = f"SPが足りません（必要SP {technique.sp}）"
            return

        candidates = self._target_candidates(technique)
        if not candidates and technique.target_code != "none":
            self.message = "選択できる対象がいません"
            return

        if technique.target_code == "enemy_single":
            self.pending_action = PendingAction(ally, technique, [])
            self.target_side = "enemy"
            self.focus = "target_enemy"
            self.panel_mode = "target"
            self.enemy_index = next(
                (index for index, enemy in enumerate(self.enemies) if enemy.alive), 0
            )
            self.message = "対象にする敵を選択してください"
            return
        if technique.target_code == "ally_single":
            self.pending_action = PendingAction(ally, technique, [])
            self.target_side = "ally"
            self.focus = "target_ally"
            self.panel_mode = "target"
            self.ally_index = next(
                (index for index, target in enumerate(self.allies) if target.alive), 0
            )
            self.message = "対象にする味方を選択してください"
            return

        self.pending_action = PendingAction(ally, technique, candidates)
        self.target_side = None
        self._register_pending_action()

    def _select_target(self):
        if self.pending_action is None:
            return
        target = (
            self._selected_enemy()
            if self.focus == "target_enemy"
            else self._selected_ally()
        )
        if target is None or not target.alive:
            self.message = "行動可能な対象を選んでください"
            return
        self.pending_action.targets = [target]
        self.target_side = None
        self._register_pending_action()

    def _prediction_message(self):
        if self.pending_action is None:
            return "行動を選択してください"
        action = self.pending_action
        target_names = "、".join(target.character.name for target in action.targets)
        if action.technique.target_code == "random_enemy":
            target_names = "敵からランダム"
        elif not target_names:
            target_names = "特殊"
        return f"{action.actor.character.name} → {target_names}: {action.technique.name}"

    def _living_actors(self):
        return [ally for ally in self.allies if ally.alive]

    def _ready_count(self):
        return sum(id(ally) in self.planned_actions for ally in self._living_actors())

    def _all_actions_ready(self):
        actors = self._living_actors()
        return bool(actors) and all(id(ally) in self.planned_actions for ally in actors)

    def _open_next_unplanned(self):
        if not self.allies:
            return False
        for offset in range(1, len(self.allies) + 1):
            index = (self.ally_index + offset) % len(self.allies)
            ally = self.allies[index]
            if ally.alive and id(ally) not in self.planned_actions:
                self.ally_index = index
                self._open_skills()
                return True
        return False

    def _register_pending_action(self):
        action = self.pending_action
        if action is None:
            return
        self.planned_actions[id(action.actor)] = action
        self.pending_action = None
        self.target_side = None
        ready = self._ready_count()
        total = len(self._living_actors())
        if self._all_actions_ready():
            self.panel_mode = "command"
            self.focus = "command"
            self.command_index = 0
            self.message = f"行動準備完了 {ready}/{total}。決定でターン実行"
        elif not self._open_next_unplanned():
            self.panel_mode = "command"
            self.focus = "command"
            self.message = f"行動準備 {ready}/{total}"

    def _confirm_command(self):
        if not self._all_actions_ready():
            ready = self._ready_count()
            total = len(self._living_actors())
            self.message = f"味方を選んで行動を決めてください（{ready}/{total}）"
            return
        self._execute_turn()
    @staticmethod
    def _base_damage(attack_power, technique_power, defense_power):
        """攻撃威力² / (防御力×3 + 攻撃威力) を整数ダメージにする。"""
        attack_strength = max(0.0, float(attack_power)) * max(
            0.0, float(technique_power)
        )
        denominator = max(0.0, float(defense_power)) * 3 + attack_strength
        if attack_strength <= 0 or denominator <= 0:
            return 1
        return max(1, int(attack_strength ** 2 / denominator))

    def _damage(self, actor, target, technique):
        attack_power = (
            max(actor.character.atk, actor.character.matk) * actor.atk_bonus
        )
        defense_power = max(target.character.defense, target.character.mdef)
        base_damage = self._base_damage(
            attack_power, technique.attack, defense_power
        )
        return max(1, int(base_damage * target.damage_multiplier))

    def _teams_for(self, actor):
        if actor.side == "ally":
            return self.allies, self.enemies
        return self.enemies, self.allies

    def _targets_for_technique(self, actor, technique):
        friends, opponents = self._teams_for(actor)
        code = technique.target_code
        if code == "enemy_single":
            candidates = self._alive(opponents)
            return [self.rng.choice(candidates)] if candidates else []
        if code == "enemy_all":
            return self._alive(opponents)
        if code == "random_enemy":
            return self._alive(opponents)
        if code == "ally_single":
            candidates = self._alive(friends)
            if not candidates:
                return []
            target = min(
                candidates,
                key=lambda unit: unit.current_hp / unit.max_hp,
            )
            return [target]
        if code == "ally_all":
            return self._alive(friends)
        if code == "self":
            return [actor] if actor.alive else []
        return []

    def _choose_enemy_action(self, enemy):
        techniques = [
            technique
            for technique in enemy.character.techniques
            if enemy.current_sp >= technique.sp
        ]
        if not techniques:
            return None

        hp_ratio = enemy.current_hp / enemy.max_hp
        if hp_ratio <= 0.15:
            defense = next(
                (
                    technique
                    for technique in techniques
                    if technique.effect_code == "defend"
                ),
                None,
            )
            if defense is not None:
                return PendingAction(
                    enemy,
                    defense,
                    self._targets_for_technique(enemy, defense),
                )

        attacks = [
            technique
            for technique in techniques
            if technique.effect_code == "damage"
        ]
        if not attacks:
            return None

        weighted_attacks = []
        for technique in attacks:
            weight = 1 if technique.name == "通常攻撃" else 3
            weighted_attacks.extend([technique] * weight)
        technique = self.rng.choice(weighted_attacks)
        return PendingAction(
            enemy,
            technique,
            self._targets_for_technique(enemy, technique),
        )

    def _refresh_action_targets(self, action):
        technique = action.technique
        friends, opponents = self._teams_for(action.actor)
        if technique.target_code == "enemy_all":
            action.targets = self._alive(opponents)
        elif technique.target_code == "ally_all":
            action.targets = self._alive(friends)
        elif technique.target_code == "self":
            action.targets = [action.actor] if action.actor.alive else []
        elif technique.target_code == "enemy_single":
            alive_targets = [target for target in action.targets if target.alive]
            if not alive_targets:
                candidates = self._alive(opponents)
                alive_targets = [self.rng.choice(candidates)] if candidates else []
            action.targets = alive_targets
        elif technique.target_code == "ally_single":
            alive_targets = [target for target in action.targets if target.alive]
            if not alive_targets:
                candidates = self._alive(friends)
                alive_targets = [self.rng.choice(candidates)] if candidates else []
            action.targets = alive_targets

    def _execute_action(self, action, messages):
        impacted_targets = []
        if not action.actor.alive:
            messages.append(f"{action.actor.character.name}は行動できない")
            return impacted_targets
        technique = action.technique
        if action.actor.current_sp < technique.sp:
            messages.append(f"{action.actor.character.name}はSP不足")
            return impacted_targets
        action.actor.current_sp -= technique.sp
        self._refresh_action_targets(action)
        audio_manager.play_technique(technique)

        if technique.effect_code == "damage":
            for _ in range(max(1, technique.hit_count)):
                if technique.target_code == "random_enemy":
                    _, opponents = self._teams_for(action.actor)
                    alive = self._alive(opponents)
                    if not alive:
                        break
                    targets = [self.rng.choice(alive)]
                else:
                    targets = [target for target in action.targets if target.alive]
                if not targets:
                    messages.append(f"{action.actor.character.name}の攻撃対象がいない")
                    break
                for target in targets:
                    was_alive = target.alive
                    amount = self._damage(action.actor, target, technique)
                    target.current_hp = max(0, target.current_hp - amount)
                    messages.append(f"{target.character.name}に{amount}ダメージ")
                    if was_alive and not target.alive:
                        self._start_ko_animation(target)
                        messages.append(f"{target.character.name}は倒れた")
                    if target not in impacted_targets:
                        impacted_targets.append(target)
        elif technique.effect_code == "heal":
            targets = [target for target in action.targets if target.alive]
            for target in targets:
                amount = max(1, int(action.actor.character.matk * technique.attack))
                before = target.current_hp
                target.current_hp = min(target.max_hp, target.current_hp + amount)
                messages.append(f"{target.character.name}のHPを{target.current_hp - before}回復")
        elif technique.effect_code == "buff":
            for target in action.targets:
                if target.alive:
                    target.atk_bonus = max(target.atk_bonus, technique.attack)
                    messages.append(f"{target.character.name}の攻撃が上昇")
        elif technique.effect_code == "defend":
            targets = action.targets or [action.actor]
            multiplier = technique.attack if 0 < technique.attack < 1 else 0.5
            for target in targets:
                if target.alive:
                    target.damage_multiplier = min(
                        target.damage_multiplier, multiplier
                    )
                    messages.append(f"{target.character.name}は防御態勢")
        elif technique.effect_code == "taunt":
            messages.append(f"敵の注意が{action.actor.character.name}に集まった")
        else:
            messages.append(f"{action.actor.character.name}が{technique.name}を使用")
        return impacted_targets

    def _execute_turn(self):
        actions = [
            action
            for action in self.planned_actions.values()
            if action.actor.alive
        ]
        for enemy in self._alive(self.enemies):
            if enemy.character.techniques:
                actions.append(
                    PendingAction(enemy, enemy.character.techniques[0], [])
                )
        actions.sort(key=lambda action: -action.actor.character.spd)

        self.pending_action = None
        self.planned_actions.clear()
        self.target_side = None
        self.panel_mode = "command"
        self.focus = "command"
        self.command_index = 0
        self.action_queue = actions
        self.resolving_turn = True
        self.current_action = None
        self.animation_targets = []
        self.message = f"ターン{self.turn_number}開始"
        self._start_next_action()

    def _start_next_action(self):
        while self.action_queue:
            action = self.action_queue.pop(0)
            if not action.actor.alive:
                continue
            if action.actor.side == "enemy":
                action = self._choose_enemy_action(action.actor)
                if action is None:
                    continue
            self.current_action = action
            self.animation_phase = "attack"
            self.animation_frame = 0
            self.animation_targets = []
            self.action_comment = ""
            self.message = (
                f"{action.actor.character.name}の{action.technique.name}"
            )
            return
        self._finish_resolution()

    def _finish_resolution(self, result=None):
        for combatant in self.allies + self.enemies:
            combatant.damage_multiplier = 1.0
        self.resolving_turn = False
        self.action_queue = []
        self.current_action = None
        self.animation_phase = None
        self.animation_frame = 0
        self.animation_targets = []
        self.action_comment = ""
        self.panel_mode = "command"
        self.focus = "command"
        self.command_index = 0

        if result == "victory":
            self.outcome = "victory"
            self.message = "勝利しました。決定キーでマップへ戻ります"
            return
        if result == "defeat":
            self.outcome = "defeat"
            self.message = "全滅しました。決定キーでマップへ戻ります"
            return

        self.turn_number += 1
        self.ally_index = next(
            (index for index, ally in enumerate(self.allies) if ally.alive),
            0,
        )
        self.message = "次の行動を選択してください"

    def _begin_action_comment(self):
        self.animation_phase = "message"
        self.animation_frame = 0
        self.animation_targets = []

    def _advance_after_comment(self):
        if not self.resolving_turn or self.animation_phase != "message":
            return
        if not self._alive(self.enemies):
            self._finish_resolution("victory")
        elif not self._alive(self.allies):
            self._finish_resolution("defeat")
        else:
            self._start_next_action()

    def tick(self):
        """1フレーム分だけ、現在の技演出と行動キューを進める。"""
        self._tick_ko_animations()
        if self.capture_active:
            self._tick_capture_animation()
            return
        if not self.resolving_turn or self.current_action is None:
            return

        self.animation_frame += 1
        if (
            self.animation_phase == "attack"
            and self.animation_frame >= self.ATTACK_FRAMES
        ):
            messages = []
            action = self.current_action
            self.animation_targets = self._execute_action(action, messages)
            self.resolved_actions.append(
                (
                    self.turn_number,
                    action.actor.side,
                    action.actor.character.name,
                    action.technique.name,
                )
            )
            self.action_comment = (
                chr(10).join(messages)
                if messages
                else f"{action.technique.name}を使用した"
            )
            self.message = f"{action.actor.character.name}の{action.technique.name}"
            self.animation_phase = (
                "impact" if self.animation_targets else "message"
            )
            self.animation_frame = 0
            return

        if (
            self.animation_phase == "impact"
            and self.animation_frame >= self.IMPACT_FRAMES
        ):
            self._begin_action_comment()
            return

        if (
            self.animation_phase == "message"
            and self.animation_frame >= self.MESSAGE_FRAMES
        ):
            self._advance_after_comment()

    def _execute_pending(self):
        """旧呼び出しとの互換用。現在は登録またはターン実行を行う。"""
        self._confirm_command()

    def _open_items(self):
        self.panel_mode = "items"
        self.focus = "item"
        self.item_index = 0
        self.pending_item_id = None
        self.target_side = None
        self.message = (
            "使用する道具を選択してください"
            if self.items
            else "使用できる道具がありません"
        )

    def _use_item(self):
        if not self.items:
            self.message = "使用できる道具がありません"
            return
        self.item_index = max(0, min(self.item_index, len(self.items) - 1))
        entry = self.items[self.item_index]
        item_id = int(entry.get("item_id", -1))
        name = self._item_name(item_id)

        if item_id in self.BATTERY_HEAL_RATES:
            if not self._alive(self.allies):
                self.message = "回復できる味方がいません"
                return
            self.pending_item_id = item_id
            self.target_side = "ally"
            self.panel_mode = "item_target"
            self.focus = "target_ally"
            self.ally_index = next(
                (index for index, ally in enumerate(self.allies) if ally.alive),
                0,
            )
            self.message = f"{name}を使う味方を選択してください"
            return

        if item_id == self.SOCKET_ITEM_ID:
            if not self._alive(self.enemies):
                self.message = "捕獲できる敵がいません"
                return
            self.pending_item_id = item_id
            self.target_side = "enemy"
            self.panel_mode = "item_target"
            self.focus = "target_enemy"
            self.enemy_index = next(
                (index for index, enemy in enumerate(self.enemies) if enemy.alive),
                0,
            )
            self.message = f"{name}で捕獲する敵を選択してください"
            return

        self.message = f"{name}: 効果データが未設定です"

    def _finish_item_use(self):
        self.pending_item_id = None
        self.target_side = None
        self.panel_mode = "command"
        self.focus = "command"
        self.command_index = 0

    @staticmethod
    def _load_capture_image():
        try:
            image = pygame.image.load(
                resource_path("INFO", "RESOURCE", "normal_socket.png")
            ).convert_alpha()
            return pygame.transform.scale(image, (56, 56))
        except (FileNotFoundError, pygame.error, OSError):
            return None

    def _capture_phase_message(self):
        if self.capture_phase == "throw":
            return "\u30bd\u30b1\u30c3\u30c8\u3092\u6295\u3052\u305f"
        if self.capture_phase == "shake":
            return "\u6355\u7372\u5224\u5b9a\u4e2d..."
        return self.message

    def _start_capture_attempt(self, target, item_name, capture_rate):
        self._finish_item_use()
        self.pending_action = None
        self.planned_actions.clear()
        self.action_queue = []
        self.current_action = None
        self.animation_phase = None
        self.animation_frame = 0
        self.animation_targets = []
        self.action_comment = ""
        self.capture_active = True
        self.capture_phase = "throw"
        self.capture_frame = 0
        self.capture_target = target
        self.capture_rate = float(capture_rate)
        self.capture_success = self.rng.random() < self.capture_rate
        self.capture_result_applied = False
        self.capture_item_name = str(item_name)
        self.resolving_turn = True
        self.message = f"{item_name}\u3092\u6295\u3052\u305f"
        audio_manager.play_se("electric")

    def _apply_capture_result(self):
        if self.capture_result_applied or self.capture_target is None:
            return
        self.capture_result_applied = True
        target = self.capture_target
        capture_percent = round(self.capture_rate * 100)
        if self.capture_success:
            self.capture_success = apply_character_amount_changes(
                {target.character.id: 1},
                self.character_inventory_path,
                self.party_path,
            )
        if self.capture_success:
            target.current_hp = 0
            target.ko_animation_active = False
            target.ko_animation_complete = True
            self.message = (
                f"{target.character.name}\u3092\u6355\u7372\u3057\u307e\u3057\u305f"
                f"\uff08\u6355\u7372\u7387 {capture_percent}%\uff09"
            )
            audio_manager.play_se("light")
        else:
            self.message = (
                f"{target.character.name}\u306e\u6355\u7372\u306b\u5931\u6557\u3057\u307e\u3057\u305f"
                f"\uff08\u6355\u7372\u7387 {capture_percent}%\uff09"
            )

    def _start_enemy_only_resolution(self):
        actions = [
            PendingAction(enemy, enemy.character.techniques[0], [])
            for enemy in self._alive(self.enemies)
            if enemy.character.techniques
        ]
        actions.sort(key=lambda action: -action.actor.character.spd)
        self.pending_action = None
        self.planned_actions.clear()
        self.target_side = None
        self.panel_mode = "command"
        self.focus = "command"
        self.command_index = 0
        self.action_queue = actions
        self.resolving_turn = True
        self.current_action = None
        self.animation_phase = None
        self.animation_frame = 0
        self.animation_targets = []
        self.action_comment = ""
        self._start_next_action()

    def _finish_capture_animation(self):
        captured_name = (
            self.capture_target.character.name
            if self.capture_target is not None
            else ""
        )
        capture_success = self.capture_success
        capture_percent = round(self.capture_rate * 100)
        self.capture_active = False
        self.capture_phase = None
        self.capture_frame = 0
        self.capture_target = None
        self.capture_result_applied = False
        self.capture_item_name = ""
        if not self._alive(self.enemies):
            self._finish_resolution("victory")
            if capture_success:
                self.message = (
                    f"{captured_name}\u3092\u6355\u7372\u3057\u307e\u3057\u305f"
                    f"\uff08\u6355\u7372\u7387 {capture_percent}%\uff09\u3002"
                    "\u6c7a\u5b9a\u30ad\u30fc\u3067\u30de\u30c3\u30d7\u3078\u623b\u308a\u307e\u3059"
                )
            return
        if not self._alive(self.allies):
            self._finish_resolution("defeat")
            return
        self._start_enemy_only_resolution()

    def _tick_capture_animation(self):
        self.capture_frame += 1
        if (
            self.capture_phase == "throw"
            and self.capture_frame >= self.CAPTURE_THROW_FRAMES
        ):
            self.capture_phase = "shake"
            self.capture_frame = 0
            self.message = "\u6355\u7372\u5224\u5b9a\u4e2d..."
            return
        if (
            self.capture_phase == "shake"
            and self.capture_frame >= self.CAPTURE_SHAKE_FRAMES
        ):
            self._apply_capture_result()
            self.capture_phase = "result"
            self.capture_frame = 0
            return
        if (
            self.capture_phase == "result"
            and self.capture_frame >= self.CAPTURE_RESULT_FRAMES
        ):
            self._finish_capture_animation()
    def _use_item_on_target(self):
        item_id = self.pending_item_id
        if item_id is None:
            return
        name = self._item_name(item_id)

        if item_id in self.BATTERY_HEAL_RATES:
            target = self._selected_ally()
            if target is None or not target.alive:
                self.message = "回復できる味方を選択してください"
                return
            if target.current_hp >= target.max_hp:
                self.message = f"{target.character.name}のHPは満タンです"
                return
            if not self._consume_item(item_id):
                self.message = f"{name}を使用できませんでした"
                return
            amount = max(
                1,
                math.ceil(target.max_hp * self.BATTERY_HEAL_RATES[item_id]),
            )
            before = target.current_hp
            target.current_hp = min(target.max_hp, target.current_hp + amount)
            healed = target.current_hp - before
            audio_manager.play_se("charge")
            self._finish_item_use()
            self.message = f"{target.character.name}のHPを{healed}回復しました"
            return

        if item_id == self.SOCKET_ITEM_ID:
            target = self._selected_enemy()
            if target is None or not target.alive:
                self.message = "\u6355\u7372\u3067\u304d\u308b\u6575\u3092\u9078\u629e\u3057\u3066\u304f\u3060\u3055\u3044"
                return
            capture_rate = self._capture_rate(target)
            if not self._consume_item(item_id):
                self.message = f"{name}\u3092\u4f7f\u7528\u3067\u304d\u307e\u305b\u3093\u3067\u3057\u305f"
                return
            self._start_capture_attempt(target, name, capture_rate)
            return
    def _activate_focus(self):
        if self.outcome:
            return MOVE
        if self.focus == "command":
            if self.command_index == 0:
                self._confirm_command()
            elif self.command_index == 1:
                self._open_items()
            else:
                self.message = "バトルから逃走しました"
                return MOVE
        elif self.focus == "enemy":
            enemy = self._selected_enemy()
            if enemy:
                self.panel_mode = "enemy_detail"
                self.message = enemy.character.explain or enemy.character.property_name
        elif self.focus == "ally":
            self._open_skills()
        elif self.focus == "skill":
            self._choose_skill()
        elif self.focus in ("target_enemy", "target_ally"):
            if self.panel_mode == "item_target":
                self._use_item_on_target()
            else:
                self._select_target()
        elif self.focus == "item":
            self._use_item()
        return BATTLE

    def _cancel(self):
        if self.focus == "skill":
            self.pending_action = None
            self.target_side = None
            self.panel_mode = "command"
            self.focus = "ally"
        elif self.focus in ("target_enemy", "target_ally"):
            if self.panel_mode == "item_target":
                self.pending_item_id = None
                self.target_side = None
                self.panel_mode = "items"
                self.focus = "item"
                self.message = "使用する道具を選択してください"
            else:
                self.pending_action = None
                self.target_side = None
                self.panel_mode = "skills"
                self.focus = "skill"
                self.message = "技を選択してください"
        elif self.focus in ("item", "enemy") or self.panel_mode == "enemy_detail":
            self.panel_mode = "command"
            self.focus = "command"

    def _handle_key(self, event):
        key = event.key
        if key in (pygame.K_BACKSPACE, pygame.K_ESCAPE):
            self._cancel()
            return BATTLE
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            return self._activate_focus()

        if key in (pygame.K_UP, pygame.K_w):
            amount = -1
        elif key in (pygame.K_DOWN, pygame.K_s):
            amount = 1
        else:
            amount = 0

        if amount:
            if self.focus in ("enemy", "target_enemy"):
                self.enemy_index = self._move_index(self.enemy_index, amount, len(self.enemies))
            elif self.focus in ("ally", "target_ally"):
                self.ally_index = self._move_index(self.ally_index, amount, len(self.allies))
            elif self.focus == "command":
                self.command_index = self._move_index(self.command_index, amount, 3)
            elif self.focus == "skill":
                techniques = self._techniques_for_selected_ally()
                self.skill_index = self._move_index(self.skill_index, amount, len(techniques))
            elif self.focus == "item":
                self.item_index = self._move_index(self.item_index, amount, len(self.items))
            return BATTLE

        if key in (pygame.K_LEFT, pygame.K_a):
            if self.focus == "command":
                self.focus = "enemy"
            elif self.focus == "ally":
                self.focus = "command"
            elif self.focus == "skill":
                self.focus = "ally"
                self.panel_mode = "command"
        elif key in (pygame.K_RIGHT, pygame.K_d):
            if self.focus == "enemy":
                self.focus = "command"
            elif self.focus == "command":
                self.focus = "ally"
        return BATTLE

    def _enemy_button_rect(self, index):
        return pygame.Rect(10, 424 + index * 45, 210, self.ROW_HEIGHT)

    def _ally_button_rect(self, index):
        return pygame.Rect(580, 424 + index * 45, 210, self.ROW_HEIGHT)

    def _command_rect(self, index):
        return pygame.Rect(250, 418 + index * 58, 300, 48)

    def _context_rect(self, index):
        return pygame.Rect(245, 408 + index * 31, 310, 28)

    def _handle_mouse(self, event, mx, my):
        if event.type == pygame.MOUSEMOTION:
            for index in range(len(self.enemies)):
                if self._enemy_button_rect(index).collidepoint(mx, my):
                    if self.target_side == "ally":
                        return BATTLE
                    self.enemy_index = index
                    self.focus = "target_enemy" if self.target_side == "enemy" else "enemy"
                    return BATTLE
            for index in range(len(self.allies)):
                if self._ally_button_rect(index).collidepoint(mx, my):
                    if self.target_side == "enemy":
                        return BATTLE
                    self.ally_index = index
                    self.focus = "target_ally" if self.target_side == "ally" else "ally"
                    return BATTLE
            return BATTLE

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return BATTLE

        for index in range(len(self.enemies)):
            if self._enemy_button_rect(index).collidepoint(mx, my):
                if self.target_side == "ally":
                    return BATTLE
                self.enemy_index = index
                self.focus = "target_enemy" if self.target_side == "enemy" else "enemy"
                return self._activate_focus()
        for index in range(len(self.allies)):
            if self._ally_button_rect(index).collidepoint(mx, my):
                if self.target_side == "enemy":
                    return BATTLE
                self.ally_index = index
                self.focus = "target_ally" if self.target_side == "ally" else "ally"
                return self._activate_focus()

        if self.panel_mode == "command":
            for index in range(3):
                if self._command_rect(index).collidepoint(mx, my):
                    self.focus = "command"
                    self.command_index = index
                    return self._activate_focus()
        elif self.panel_mode == "skills":
            for index in range(min(len(self._techniques_for_selected_ally()), 6)):
                if self._context_rect(index).collidepoint(mx, my):
                    self.focus = "skill"
                    self.skill_index = index
                    return self._activate_focus()
        elif self.panel_mode == "items":
            for index in range(min(len(self.items), 5)):
                if self._context_rect(index).collidepoint(mx, my):
                    self.focus = "item"
                    self.item_index = index
                    return self._activate_focus()
        return BATTLE

    def update(self, event, mx, my):
        if self.capture_active:
            return BATTLE
        if self.resolving_turn:
            if (
                self.animation_phase == "message"
                and event.type
                in (
                    pygame.KEYDOWN,
                    pygame.MOUSEBUTTONDOWN,
                    pygame.MOUSEWHEEL,
                    pygame.JOYBUTTONDOWN,
                )
            ):
                self._advance_after_comment()
            return BATTLE
        if event.type == pygame.KEYDOWN:
            return self._handle_key(event)
        return self._handle_mouse(event, mx, my)

    def _load_image(self, character, size):
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

    @staticmethod
    def _draw_hp_bar(screen, combatant, rect):
        pygame.draw.rect(screen, (35, 35, 35), rect)
        width = int(rect.width * combatant.current_hp / combatant.max_hp)
        color = GREEN if combatant.current_hp > combatant.max_hp * 0.3 else RED
        pygame.draw.rect(screen, color, (rect.x, rect.y, width, rect.height))
        pygame.draw.rect(screen, WHITE, rect, 1)

    def _animation_offset(self, combatant):
        if combatant.ko_animation_active:
            progress = min(
                1.0,
                combatant.ko_animation_frame / self.KO_FRAMES,
            )
            amplitude = max(1, round(10 * (1.0 - progress)))
            direction = -1 if (combatant.ko_animation_frame // 2) % 2 else 1
            drop = round(self.KO_DROP_DISTANCE * progress * progress)
            return amplitude * direction, drop
        if combatant.ko_animation_complete:
            return 0, self.KO_DROP_DISTANCE
        if self.current_action is None:
            return 0, 0
        if (
            self.animation_phase == "attack"
            and self.current_action.actor is combatant
        ):
            progress = min(1.0, self.animation_frame / self.ATTACK_FRAMES)
            return 0, -round(math.sin(math.pi * progress) * 14)
        if (
            self.animation_phase == "impact"
            and combatant in self.animation_targets
        ):
            progress = min(1.0, self.animation_frame / self.IMPACT_FRAMES)
            amplitude = max(1, round(8 * (1.0 - progress)))
            direction = -1 if (self.animation_frame // 2) % 2 else 1
            return amplitude * direction, 0
        return 0, 0

    def _combatant_alpha(self, combatant):
        if self.capture_active and combatant is self.capture_target:
            if self.capture_phase == "shake":
                progress = min(
                    1.0,
                    self.capture_frame / self.CAPTURE_SHAKE_FRAMES,
                )
                return max(45, round(255 * (1.0 - progress)))
            if self.capture_phase == "result":
                return 0 if self.capture_success else 255
        if combatant.ko_animation_active:
            progress = min(
                1.0,
                combatant.ko_animation_frame / self.KO_FRAMES,
            )
            return round(255 * (1.0 - progress))
        if combatant.ko_animation_complete or not combatant.alive:
            return 0
        return 255

    def _draw_combatant(self, screen, combatant, center, size, selected=False, planned=False):
        image = self._load_image(combatant.character, size)
        rect = pygame.Rect(0, 0, *size)
        offset_x, offset_y = self._animation_offset(combatant)
        rect.center = (center[0] + offset_x, center[1] + offset_y)
        alpha = self._combatant_alpha(combatant)

        visual = pygame.Surface(size, pygame.SRCALPHA)
        if image is None:
            pygame.draw.rect(visual, (25, 25, 40), visual.get_rect())
            pygame.draw.rect(visual, LOW_YELLOW, visual.get_rect(), 2)
            mark = self.small_font.render("?", True, LOWH)
            visual.blit(mark, mark.get_rect(center=visual.get_rect().center))
        else:
            visual.blit(image, (0, 0))
        if alpha > 0:
            visual.set_alpha(alpha)
            screen.blit(visual, rect)
        if planned and alpha > 0:
            pygame.draw.rect(screen, self.PLANNED_COLOR, rect.inflate(7, 7), 2)
        if selected and alpha > 0:
            pygame.draw.rect(screen, YELLOW, rect.inflate(10, 10), 3)
        self.combatant_positions[id(combatant)] = rect.center
        return rect

    def _draw_socket_sprite(self, screen, center, angle=0, scale=1.0):
        if self.capture_image is None:
            size = max(18, round(54 * scale))
            rect = pygame.Rect(0, 0, size, size)
            rect.center = (round(center[0]), round(center[1]))
            pygame.draw.rect(screen, (28, 31, 38), rect)
            pygame.draw.rect(screen, (225, 190, 45), rect, 3)
            for offset in (-1, 1):
                pygame.draw.circle(
                    screen,
                    (255, 220, 60),
                    (rect.centerx + offset * size // 5, rect.centery),
                    max(2, size // 10),
                )
            return rect
        sprite = pygame.transform.rotozoom(
            self.capture_image,
            float(angle),
            max(0.1, float(scale)),
        )
        rect = sprite.get_rect(
            center=(round(center[0]), round(center[1]))
        )
        screen.blit(sprite, rect)
        return rect

    def _draw_capture_animation(self, screen):
        if not self.capture_active or self.capture_target is None:
            return
        target_center = self.combatant_positions.get(
            id(self.capture_target),
            (82, 75),
        )
        effect_layer = pygame.Surface((WIDTH, self.UI_TOP), pygame.SRCALPHA)

        if self.capture_phase == "throw":
            progress = min(
                1.0,
                self.capture_frame / self.CAPTURE_THROW_FRAMES,
            )
            eased = progress * progress * (3.0 - 2.0 * progress)
            start = pygame.Vector2(WIDTH - 105, self.UI_TOP - 45)
            end = pygame.Vector2(target_center)
            position = start.lerp(end, eased)
            position.y -= math.sin(math.pi * progress) * 105
            for point_index in range(1, 8):
                point_progress = max(0.0, progress - point_index * 0.035)
                if point_progress <= 0:
                    continue
                point_eased = point_progress * point_progress * (
                    3.0 - 2.0 * point_progress
                )
                point = start.lerp(end, point_eased)
                point.y -= math.sin(math.pi * point_progress) * 105
                pygame.draw.circle(
                    effect_layer,
                    (255, 215, 60, max(25, 150 - point_index * 18)),
                    (round(point.x), round(point.y)),
                    max(2, 7 - point_index),
                )
            screen.blit(effect_layer, (0, 0))
            self._draw_socket_sprite(
                screen,
                position,
                angle=-self.capture_frame * 18,
                scale=0.9,
            )
            return

        if self.capture_phase == "shake":
            progress = min(
                1.0,
                self.capture_frame / self.CAPTURE_SHAKE_FRAMES,
            )
            shake = math.sin(progress * math.pi * 6) * (12 * (1.0 - progress * 0.35))
            socket_center = (target_center[0] + shake, target_center[1] + 15)
            ring_radius = max(6, round(58 * (1.0 - progress)))
            pygame.draw.circle(
                effect_layer,
                (255, 220, 65, max(30, round(210 * (1.0 - progress)))),
                target_center,
                ring_radius,
                3,
            )
            beam_alpha = max(25, round(190 * (1.0 - progress)))
            pygame.draw.line(
                effect_layer,
                (255, 225, 85, beam_alpha),
                target_center,
                (round(socket_center[0]), round(socket_center[1])),
                5,
            )
            screen.blit(effect_layer, (0, 0))
            pulse_scale = 1.0 + 0.08 * math.sin(progress * math.pi * 6)
            self._draw_socket_sprite(
                screen,
                socket_center,
                angle=shake * 2,
                scale=pulse_scale,
            )
            return

        progress = min(
            1.0,
            self.capture_frame / self.CAPTURE_RESULT_FRAMES,
        )
        if self.capture_success:
            for ring_index in range(3):
                ring_progress = max(0.0, min(1.0, progress * 1.5 - ring_index * 0.18))
                if ring_progress <= 0:
                    continue
                radius = round(20 + ring_progress * 85)
                alpha = max(0, round(230 * (1.0 - ring_progress)))
                pygame.draw.circle(
                    effect_layer,
                    (255, 220, 60, alpha),
                    target_center,
                    radius,
                    4,
                )
            for particle_index in range(12):
                angle = particle_index * math.tau / 12 + progress * 1.5
                radius = 24 + progress * 70
                point = (
                    round(target_center[0] + math.cos(angle) * radius),
                    round(target_center[1] + math.sin(angle) * radius),
                )
                pygame.draw.circle(
                    effect_layer,
                    (255, 235, 110, max(0, round(255 * (1.0 - progress)))),
                    point,
                    4,
                )
            screen.blit(effect_layer, (0, 0))
            self._draw_socket_sprite(
                screen,
                target_center,
                scale=max(0.2, 1.0 - progress * 0.55),
            )
            result = self.small_font.render("CAPTURE!", True, (255, 230, 80))
        else:
            shake = math.sin(progress * math.pi * 8) * 7 * (1.0 - progress)
            center = (target_center[0] + shake, target_center[1] + 15)
            socket_rect = self._draw_socket_sprite(
                screen,
                center,
                angle=shake * 3,
            )
            pygame.draw.line(
                screen,
                RED,
                socket_rect.topleft,
                socket_rect.bottomright,
                5,
            )
            pygame.draw.line(
                screen,
                RED,
                socket_rect.topright,
                socket_rect.bottomleft,
                5,
            )
            result = self.small_font.render("FAILED", True, RED)
        screen.blit(
            result,
            result.get_rect(center=(target_center[0], target_center[1] - 55)),
        )
    def _draw_battlefield(self, screen):
        pygame.draw.rect(screen, (18, 24, 32), (0, 0, WIDTH, self.UI_TOP))
        pygame.draw.line(screen, LOW_YELLOW, (WIDTH // 2, 18), (WIDTH // 2, 370), 1)
        screen.blit(self.title_font.render("ENEMY", True, RED), (18, 10))
        ally_title = self.title_font.render("ALLY", True, GREEN)
        screen.blit(ally_title, ally_title.get_rect(topright=(WIDTH - 18, 10)))
        turn = self.small_font.render(f"TURN {self.turn_number}", True, YELLOW)
        screen.blit(turn, turn.get_rect(center=(WIDTH // 2, 22)))

        for index, enemy in enumerate(self.enemies):
            center = (82, 75 + index * 90)
            selected = (
                self.focus in ("enemy", "target_enemy")
                and index == self.enemy_index
            ) or (
                self.current_action is not None
                and self.current_action.actor is enemy
            )
            rect = self._draw_combatant(screen, enemy, center, (58, 58), selected)
            screen.blit(self.small_font.render(enemy.character.name, True, WHITE), (122, center[1] - 23))
            hp = self.tiny_font.render(f"HP {enemy.current_hp}/{enemy.max_hp}", True, LOWH)
            screen.blit(hp, (122, center[1] + 2))
            self._draw_hp_bar(screen, enemy, pygame.Rect(122, center[1] + 24, 150, 7))

        for index, ally in enumerate(self.allies):
            center = (718, 75 + index * 90)
            selected = (
                self.focus in ("ally", "target_ally", "skill")
                and index == self.ally_index
            ) or (
                self.pending_action is not None
                and self.pending_action.actor is ally
            ) or (
                self.current_action is not None
                and self.current_action.actor is ally
            )
            planned = id(ally) in self.planned_actions
            rect = self._draw_combatant(
                screen, ally, center, (58, 58), selected, planned
            )
            name = self.small_font.render(ally.character.name, True, WHITE)
            screen.blit(name, name.get_rect(topright=(678, center[1] - 23)))
            hp = self.tiny_font.render(
                f"HP {ally.current_hp}/{ally.max_hp}  SP {ally.current_sp}",
                True,
                LOWH,
            )
            screen.blit(hp, hp.get_rect(topright=(678, center[1] + 2)))
            self._draw_hp_bar(screen, ally, pygame.Rect(528, center[1] + 24, 150, 7))

        for action in self.planned_actions.values():
            self._draw_action_lines(screen, action, self.PLANNED_COLOR, 2)
        if self.pending_action:
            self._draw_action_lines(screen, self.pending_action, YELLOW, 3)
        if self.current_action:
            color = self._technique_color(self.current_action.technique)
            self._draw_action_lines(screen, self.current_action, color, 3)

    @staticmethod
    def _technique_color(technique):
        """属性エフェクト追加時の共通色フック。"""
        colors = {
            "熱": (255, 100, 45),
            "電気": (90, 180, 255),
            "回復": (80, 255, 130),
            "防御": (120, 220, 255),
        }
        return colors.get(technique.attribute, YELLOW)
    def _draw_action_lines(self, screen, action, color, width):
        actor_center = self.combatant_positions.get(id(action.actor))
        if not actor_center:
            return
        for target in action.targets:
            if (
                not target.alive
                or target.ko_animation_active
                or target.ko_animation_complete
            ):
                continue
            target_center = self.combatant_positions.get(id(target))
            if target_center:
                self._draw_prediction_line(screen, actor_center, target_center, color, width)

    @staticmethod
    def _draw_prediction_line(screen, start, end, color=YELLOW, width=3):
        vector = pygame.Vector2(end) - pygame.Vector2(start)
        distance = vector.length()
        if distance == 0:
            pygame.draw.circle(screen, color, start, 10, 2)
            return
        direction = vector.normalize()
        for offset in range(0, int(distance), 16):
            segment_start = pygame.Vector2(start) + direction * offset
            segment_end = pygame.Vector2(start) + direction * min(offset + 9, distance)
            pygame.draw.line(screen, color, segment_start, segment_end, width)
        pygame.draw.circle(screen, color, end, 9, 2)

    def _draw_list_button(self, screen, rect, text, selected, disabled=False, planned=False):
        pygame.draw.rect(screen, (15, 20, 35), rect)
        if disabled:
            color = GRAY
        elif selected:
            color = YELLOW
        elif planned:
            color = self.PLANNED_COLOR
        else:
            color = LOW_YELLOW
        pygame.draw.rect(screen, color, rect, 3 if selected else 1)
        font = self.small_font if self.small_font.size(text)[0] <= rect.width - 8 else self.tiny_font
        rendered = font.render(text, True, LOWH if disabled else WHITE)
        screen.blit(rendered, rendered.get_rect(center=rect.center))

    def _draw_side_panels(self, screen):
        pygame.draw.rect(screen, BLACK, self.LEFT_PANEL)
        pygame.draw.rect(screen, LOW_YELLOW, self.LEFT_PANEL, 2)
        pygame.draw.rect(screen, BLACK, self.RIGHT_PANEL)
        pygame.draw.rect(screen, LOW_YELLOW, self.RIGHT_PANEL, 2)
        screen.blit(self.small_font.render("敵", True, RED), (10, 396))
        for index, enemy in enumerate(self.enemies):
            selected = (
                self.focus in ("enemy", "target_enemy")
                and index == self.enemy_index
            ) or (
                self.current_action is not None
                and self.current_action.actor is enemy
            )
            label = f"{enemy.character.name}  {enemy.current_hp}/{enemy.max_hp}"
            self._draw_list_button(
                screen, self._enemy_button_rect(index), label, selected, not enemy.alive
            )

        ready = self._ready_count()
        total = len(self._living_actors())
        screen.blit(self.small_font.render(f"味方  行動 {ready}/{total}", True, GREEN), (580, 396))
        for index, ally in enumerate(self.allies):
            selected = self.focus in ("ally", "target_ally", "skill") and index == self.ally_index
            planned = id(ally) in self.planned_actions
            mark = "済 " if planned else ""
            label = f"{mark}{ally.character.name}  {ally.current_hp}/{ally.max_hp}"
            self._draw_list_button(
                screen,
                self._ally_button_rect(index),
                label,
                selected,
                not ally.alive,
                planned,
            )

    def _command_labels(self):
        first = "ターン実行" if self._all_actions_ready() else "決定"
        return (first, "道具", "逃走")

    def _draw_center_panel(self, screen):
        pygame.draw.rect(screen, (6, 8, 15), self.CENTER_PANEL)
        pygame.draw.rect(screen, LOW_YELLOW, self.CENTER_PANEL, 2)
        if self.capture_active:
            title = self.small_font.render("\u30bd\u30b1\u30c3\u30c8\u6355\u7372", True, YELLOW)
            screen.blit(title, title.get_rect(center=(400, 430)))
            phase = self.small_font.render(
                self._capture_phase_message(),
                True,
                WHITE,
            )
            screen.blit(phase, phase.get_rect(center=(400, 474)))
            skipped = self.tiny_font.render(
                "\u5473\u65b9\u5168\u54e1\u306e\u884c\u52d5\u3092\u30b9\u30ad\u30c3\u30d7",
                True,
                LOWH,
            )
            screen.blit(skipped, skipped.get_rect(center=(400, 514)))
        elif self.resolving_turn:
            title = self.small_font.render("行動解決中", True, YELLOW)
            screen.blit(title, title.get_rect(center=(400, 430)))
            if self.current_action:
                actor = self.current_action.actor.character.name
                technique = self.current_action.technique.name
                line = self.small_font.render(
                    f"{actor}：{technique}", True, WHITE
                )
                screen.blit(line, line.get_rect(center=(400, 474)))
            phase_names = {
                "attack": "攻撃",
                "impact": "命中",
                "message": "結果表示",
            }
            phase = phase_names.get(self.animation_phase, "")
            phase_text = self.tiny_font.render(phase, True, LOWH)
            screen.blit(phase_text, phase_text.get_rect(center=(400, 514)))
        elif self.panel_mode == "skills":
            techniques = self._techniques_for_selected_ally()
            for index, technique in enumerate(techniques[:6]):
                label = f"{technique.name} SP{technique.sp} {technique.target_name}"
                self._draw_list_button(
                    screen,
                    self._context_rect(index),
                    label,
                    self.focus == "skill" and index == self.skill_index,
                )
        elif self.panel_mode == "items":
            if not self.items:
                screen.blit(self.small_font.render("道具がありません", True, LOWH), (250, 430))
            for index, entry in enumerate(self.items[:5]):
                master = self.item_masters.get(str(entry.get("item_id")), {})
                label = f"{master.get('name', '不明な道具')} ×{entry.get('amount', 0)}"
                self._draw_list_button(
                    screen,
                    self._context_rect(index),
                    label,
                    self.focus == "item" and index == self.item_index,
                )
        elif self.panel_mode == "enemy_detail":
            enemy = self._selected_enemy()
            if enemy:
                lines = (
                    enemy.character.name,
                    f"属性: {enemy.character.property_name}",
                    f"HP: {enemy.current_hp}/{enemy.max_hp}",
                    f"ATK {enemy.character.atk}  DEF {enemy.character.defense}",
                    f"MATK {enemy.character.matk}  MDEF {enemy.character.mdef}",
                    "Backspace: 戻る",
                )
                for index, line in enumerate(lines):
                    color = YELLOW if index == 0 else WHITE
                    screen.blit(self.small_font.render(line, True, color), (248, 410 + index * 31))
        elif self.panel_mode == "item_target":
            name = self._item_name(self.pending_item_id)
            screen.blit(self.small_font.render(name, True, YELLOW), (248, 430))
            target_text = (
                "捕獲する敵を選択"
                if self.target_side == "enemy"
                else "回復する味方を選択"
            )
            screen.blit(self.tiny_font.render(target_text, True, WHITE), (248, 468))
            if self.target_side == "enemy":
                target = self._selected_enemy()
                if target is not None and target.alive:
                    capture_percent = round(self._capture_rate(target) * 100)
                    rate_text = f"現在の捕獲率: {capture_percent}%"
                    screen.blit(self.tiny_font.render(rate_text, True, GYELLOW), (248, 493))
            screen.blit(self.tiny_font.render("Backspace: 道具選択へ戻る", True, LOWH), (248, 525))
        elif self.panel_mode == "target":
            screen.blit(self.small_font.render("対象を選択", True, YELLOW), (248, 430))
            screen.blit(self.tiny_font.render("左右の一覧から決定してください", True, WHITE), (248, 468))
            screen.blit(self.tiny_font.render("Backspace: 技選択へ戻る", True, LOWH), (248, 505))
        else:
            for index, label in enumerate(self._command_labels()):
                self._draw_list_button(
                    screen,
                    self._command_rect(index),
                    label,
                    self.focus == "command" and index == self.command_index,
                )

        message_rect = pygame.Rect(238, 602, 324, 30)
        pygame.draw.rect(screen, (20, 20, 28), message_rect)
        message = "" if self.resolving_turn else self.message
        while self.tiny_font.size(message)[0] > message_rect.width - 10 and len(message) > 2:
            message = message[:-2] + "…"
        screen.blit(self.tiny_font.render(message, True, WHITE), (244, 608))

    def _wrap_action_comment(self, text, max_width):
        lines = []
        paragraphs = str(text).splitlines() or [""]
        for paragraph in paragraphs:
            if not paragraph:
                lines.append("")
                continue
            line = ""
            for character in paragraph:
                candidate = line + character
                if line and self.tiny_font.size(candidate)[0] > max_width:
                    lines.append(line)
                    line = character
                else:
                    line = candidate
            if line:
                lines.append(line)
        return lines or [""]

    def _draw_action_comment(self, screen):
        if (
            not self.resolving_turn
            or self.animation_phase != "message"
            or self.current_action is None
        ):
            return

        rect = self.ACTION_MESSAGE_RECT
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((3, 7, 16, 238))
        pygame.draw.rect(panel, YELLOW, panel.get_rect(), 3)

        action = self.current_action
        title = (
            f"{action.actor.character.name}："
            f"{action.technique.name}"
        )
        panel.blit(self.small_font.render(title, True, YELLOW), (16, 10))

        lines = self._wrap_action_comment(
            self.action_comment,
            rect.width - 32,
        )
        max_lines = 6
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            shortened = lines[-1]
            while (
                shortened
                and self.tiny_font.size(shortened + "…")[0]
                > rect.width - 32
            ):
                shortened = shortened[:-1]
            lines[-1] = shortened + "…"
        for index, line in enumerate(lines):
            panel.blit(
                self.tiny_font.render(line, True, WHITE),
                (16, 42 + index * 19),
            )

        hint = self.tiny_font.render(
            "任意のボタンで進む / 1.5秒で自動進行",
            True,
            LOWH,
        )
        panel.blit(
            hint,
            hint.get_rect(bottomright=(rect.width - 14, rect.height - 10)),
        )
        remaining = max(
            0.0,
            1.0 - self.animation_frame / self.MESSAGE_FRAMES,
        )
        pygame.draw.rect(
            panel,
            LOW_YELLOW,
            (2, rect.height - 5, int((rect.width - 4) * remaining), 3),
        )
        screen.blit(panel, rect.topleft)

    def draw(self, screen, mx, my):
        screen.fill((8, 10, 18))
        self.combatant_positions.clear()
        self._draw_battlefield(screen)
        self._draw_side_panels(screen)
        self._draw_center_panel(screen)
        self._draw_action_comment(screen)
        self._draw_capture_animation(screen)
