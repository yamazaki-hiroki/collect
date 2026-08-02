"""プレイヤー状態と分散JSONを複数セーブスロットへまとめる。"""

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from COMMON.config import FRONT, resource_path


SAVE_VERSION = 1
SAVE_SLOT_COUNT = 3
SAVE_DIR = resource_path("INFO", "SAVES")
LEGACY_SAVE_DATA_PATH = resource_path("INFO", "save_data.json")
STATE_FILES = {
    "items": resource_path("INFO", "dougu.json"),
    "characters": resource_path("INFO", "character_inventory.json"),
    "party": resource_path("INFO", "party.json"),
}
INITIAL_CHARACTER_ID = 4  # Hackit_story.txt: 初手にもらう素子 LED


class SaveDataError(Exception):
    """セーブデータが存在しない、または読み込めない場合。"""


@dataclass(frozen=True)
class GameData:
    version: int
    saved_at: str
    player: dict[str, Any]
    files: dict[str, dict[str, Any]]

    def to_dict(self):
        return {
            "version": self.version,
            "saved_at": self.saved_at,
            "player": self.player,
            "files": self.files,
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise SaveDataError("セーブデータの形式が正しくありません")
        version = int(data.get("version", -1))
        if version != SAVE_VERSION:
            raise SaveDataError(
                f"対応していないセーブバージョンです: {version}"
            )
        player = data.get("player")
        files = data.get("files")
        if not isinstance(player, dict) or not isinstance(files, dict):
            raise SaveDataError("プレイヤーまたは所持データがありません")
        required_player = {"name", "money", "map_num", "x", "y", "direction"}
        missing_player = sorted(required_player - set(player))
        if missing_player:
            raise SaveDataError(
                "プレイヤーデータが不足しています: "
                + ", ".join(missing_player)
            )
        missing_files = sorted(set(STATE_FILES) - set(files))
        if missing_files:
            raise SaveDataError(
                "所持データが不足しています: " + ", ".join(missing_files)
            )
        for name in STATE_FILES:
            if not isinstance(files[name], dict):
                raise SaveDataError(f"{name}の保存形式が正しくありません")
        return cls(
            version=version,
            saved_at=str(data.get("saved_at", "")),
            player=dict(player),
            files={name: dict(files[name]) for name in STATE_FILES},
        )


def _validate_slot(slot):
    slot = int(slot)
    if not 1 <= slot <= SAVE_SLOT_COUNT:
        raise SaveDataError(
            f"セーブスロットは1〜{SAVE_SLOT_COUNT}で指定してください"
        )
    return slot


def save_path_for_slot(slot, save_dir=None):
    slot = _validate_slot(slot)
    directory = Path(save_dir) if save_dir else SAVE_DIR
    return directory / f"slot_{slot}.json"


def _resolve_save_path(save_path=None, slot=None, save_dir=None):
    if save_path is not None:
        return Path(save_path)
    return save_path_for_slot(1 if slot is None else slot, save_dir)


def _atomic_write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
            file.write(chr(10))
        temporary.replace(path)
    except OSError as error:
        raise SaveDataError(f"{path.name}を書き込めませんでした") from error


def _read_json(path):
    path = Path(path)
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as error:
        raise SaveDataError(f"{path.name}が見つかりません") from error
    except (json.JSONDecodeError, OSError) as error:
        raise SaveDataError(f"{path.name}を読み込めませんでした") from error
    if not isinstance(data, dict):
        raise SaveDataError(f"{path.name}の形式が正しくありません")
    return data


def _state_paths(state_files=None):
    selected = STATE_FILES if state_files is None else state_files
    return {name: Path(path) for name, path in selected.items()}


def collect_game_data(player, state_files=None):
    paths = _state_paths(state_files)
    missing = sorted(set(STATE_FILES) - set(paths))
    if missing:
        raise SaveDataError("保存対象が不足しています: " + ", ".join(missing))
    files = {name: _read_json(paths[name]) for name in STATE_FILES}
    player_data = {
        "name": str(player.name),
        "money": int(player.money),
        "map_num": int(player.move.name),
        "x": int(player.move.rect.x),
        "y": int(player.move.rect.y),
        "direction": str(player.move.direction),
        "encounter_safe_steps": int(player.encounter_safe_steps),
        "tutorial_stage": int(getattr(player, "tutorial_stage", 3)),
        "party_status": [
            {
                "character_id": int(status["character_id"]),
                "hp": int(status["hp"]),
                "sp": int(status["sp"]),
            }
            for status in getattr(player, "party_status", [])
            if isinstance(status, dict)
            and {"character_id", "hp", "sp"}.issubset(status)
        ],
    }
    return GameData(
        version=SAVE_VERSION,
        saved_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        player=player_data,
        files=files,
    )


def data_save(data: GameData, save_path=None, slot=None, save_dir=None):
    path = _resolve_save_path(save_path, slot, save_dir)
    if not isinstance(data, GameData):
        raise TypeError("dataにはGameDataを指定してください")
    _atomic_write_json(path, data.to_dict())
    return path


def data_load(save_path=None, slot=None, save_dir=None) -> GameData:
    path = _resolve_save_path(save_path, slot, save_dir)
    return GameData.from_dict(_read_json(path))


def has_save_data(save_path=None, slot=None, save_dir=None):
    path = _resolve_save_path(save_path, slot, save_dir)
    return path.is_file()


def list_save_slots(save_dir=None):
    result = []
    for slot in range(1, SAVE_SLOT_COUNT + 1):
        path = save_path_for_slot(slot, save_dir)
        if not path.is_file():
            result.append(
                {"slot": slot, "path": path, "exists": False, "data": None, "error": ""}
            )
            continue
        try:
            data = data_load(path)
            error = ""
        except SaveDataError as load_error:
            data = None
            error = str(load_error)
        result.append(
            {"slot": slot, "path": path, "exists": True, "data": data, "error": error}
        )
    return result


def restore_game_files(data: GameData, state_files=None):
    if not isinstance(data, GameData):
        raise TypeError("dataにはGameDataを指定してください")
    paths = _state_paths(state_files)
    missing = sorted(set(STATE_FILES) - set(paths))
    if missing:
        raise SaveDataError("復元先が不足しています: " + ", ".join(missing))
    for name in STATE_FILES:
        snapshot = data.files.get(name)
        if not isinstance(snapshot, dict):
            raise SaveDataError(f"{name}の保存形式が正しくありません")
    for name in STATE_FILES:
        _atomic_write_json(paths[name], data.files[name])


def save_game(player, save_path=None, state_files=None, slot=None, save_dir=None):
    if save_path is None and slot is None:
        slot = getattr(player, "save_slot", 1)
    data = collect_game_data(player, state_files)
    data_save(data, save_path, slot, save_dir)
    return data


def load_game(save_path=None, state_files=None, slot=None, save_dir=None):
    data = data_load(save_path, slot, save_dir)
    restore_game_files(data, state_files)
    return data


def migrate_legacy_save(legacy_path=None, save_dir=None):
    legacy = Path(legacy_path) if legacy_path else LEGACY_SAVE_DATA_PATH
    slot_one = save_path_for_slot(1, save_dir)
    if slot_one.exists() or not legacy.is_file():
        return False
    data = data_load(legacy)
    data_save(data, slot=1, save_dir=save_dir)
    return True


def reset_new_game_files(state_files=None):
    """物語の初期状態: LED×1、LEDのみ編成、道具なし。"""
    paths = _state_paths(state_files)
    missing = sorted(set(STATE_FILES) - set(paths))
    if missing:
        raise SaveDataError("初期化先が不足しています: " + ", ".join(missing))

    try:
        item_data = _read_json(paths["items"])
    except SaveDataError:
        item_data = {}
    item_data["inventory"] = []
    character_data = {
        "inventory": [
            {"character_id": INITIAL_CHARACTER_ID, "amount": 1}
        ]
    }
    party_data = {
        "party": [{"character_id": INITIAL_CHARACTER_ID}]
    }
    _atomic_write_json(paths["items"], item_data)
    _atomic_write_json(paths["characters"], character_data)
    _atomic_write_json(paths["party"], party_data)


def initial_player_data():
    return {
        "name": "muto",
        "money": 1000,
        "map_num": 1,
        "x": 15 * 32,
        "y": 19 * 32,
        "direction": FRONT,
        "encounter_safe_steps": 0,
        "tutorial_stage": 0,
        "party_status": [],
    }