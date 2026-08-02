"""character.dbをゲーム用の読み取り専用データへ変換する。"""

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3

from COMMON.config import resource_path


DEFAULT_IMAGE_PATHS = {
    1: "INFO/RESOURCE/resistance.png",
    2: "INFO/RESOURCE/capacitor.png",
    3: "INFO/RESOURCE/transistor.png",
    4: "INFO/RESOURCE/led.png",
    6: "INFO/RESOURCE/NE555.png",
    7: "INFO/RESOURCE/AND.png",
    8: "INFO/RESOURCE/OR.png",
    9: "INFO/RESOURCE/NOT.png",
    10: "INFO/RESOURCE/EX-OR.png",
}


@dataclass(frozen=True)
class Technique:
    id: int
    name: str
    sp: int
    attack: float
    attribute: str
    target_code: str
    target_name: str
    effect_code: str
    effect_name: str
    hit_count: int
    explain: str


@dataclass(frozen=True)
class ElementCharacter:
    id: int
    name: str
    original_tech: str
    property_id: int | None
    property_name: str
    property_explain: str
    path: str | None
    hp: int
    atk: int
    defense: int
    matk: int
    mdef: int
    spd: int
    explain: str
    technique: Technique | None
    techniques: tuple[Technique, ...]


def _quote_identifier(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def _find_name(names, *expected_names):
    """旧版の改行付き識別子や単数・複数の差を吸収する。"""
    for expected in expected_names:
        for name in names:
            if name.strip() == expected:
                return name
    expected = " / ".join(repr(name) for name in expected_names)
    raise ValueError(f"character.dbに{expected}が見つかりません")


def _snapshot_connection(db_path):
    """DBをメモリへ読み込み、ゲームから元ファイルを変更できなくする。"""
    db_path = Path(db_path)
    connection = sqlite3.connect(":memory:")
    if hasattr(connection, "deserialize"):
        connection.deserialize(db_path.read_bytes())
        return connection

    connection.close()
    uri = db_path.resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _existing_image_path(character_id, configured_path):
    candidates = [configured_path, DEFAULT_IMAGE_PATHS.get(character_id)]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        resolved = path if path.is_absolute() else resource_path(*path.parts)
        if resolved.is_file():
            return str(candidate).replace("\\", "/")
    return configured_path or None


class CharacterRepository:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else resource_path("INFO", "character.db")

    def _connect(self):
        connection = _snapshot_connection(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    @staticmethod
    def _load_techniques(connection):
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tech)")}
        if "target_type_id" in columns and "effect_type_id" in columns:
            rows = connection.execute(
                """
                SELECT
                    t.id, t.name, t.sp, t.attack, t.attribute, t.hit_count,
                    t.explain,
                    target.code AS target_code,
                    target.name AS target_name,
                    effect.code AS effect_code,
                    effect.name AS effect_name
                FROM tech AS t
                JOIN target_type AS target ON target.id = t.target_type_id
                JOIN effect_type AS effect ON effect.id = t.effect_type_id
                ORDER BY t.id
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT
                    id, name, sp, attack, attribute, 1 AS hit_count, explain,
                    CASE target WHEN 1 THEN 'enemy_all' ELSE 'enemy_single' END
                        AS target_code,
                    CASE target WHEN 1 THEN '敵全体' ELSE '敵単体' END
                        AS target_name,
                    'damage' AS effect_code,
                    'ダメージ' AS effect_name
                FROM tech
                ORDER BY id
                """
            ).fetchall()
        return tuple(
            Technique(
                id=row["id"],
                name=row["name"],
                sp=int(row["sp"] or 0),
                attack=float(row["attack"] or 0),
                attribute=row["attribute"] or "なし",
                target_code=row["target_code"],
                target_name=row["target_name"],
                effect_code=row["effect_code"],
                effect_name=row["effect_name"],
                hit_count=int(row["hit_count"] or 1),
                explain=row["explain"] or "",
            )
            for row in rows
        )

    def load_techniques(self):
        connection = self._connect()
        try:
            return self._load_techniques(connection)
        finally:
            connection.close()

    def load(self):
        connection = self._connect()
        try:
            table_names = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            ]
            character_table = _find_name(table_names, "characters", "character")
            property_table = _find_name(table_names, "property")
            character_columns = [
                row[1]
                for row in connection.execute(
                    f"PRAGMA table_info({_quote_identifier(character_table)})"
                )
            ]
            property_column = _find_name(character_columns, "property")
            techniques = self._load_techniques(connection)
            techniques_by_name = {technique.name: technique for technique in techniques}
            techniques_by_id = {technique.id: technique for technique in techniques}
            basic_techniques = tuple(
                technique for technique in techniques if technique.id in (0, 9)
            )
            assigned_by_character = None
            if "character_tech" in table_names:
                assigned_by_character = {}
                assignment_rows = connection.execute(
                    """SELECT character_id, tech_id
                       FROM character_tech
                       ORDER BY character_id, sort_order, tech_id"""
                ).fetchall()
                for assignment in assignment_rows:
                    technique = techniques_by_id.get(assignment["tech_id"])
                    if technique is not None:
                        assigned_by_character.setdefault(
                            assignment["character_id"], []
                        ).append(technique)
            rows = connection.execute(
                f"""
                SELECT
                    c.id, c.name, c.original_tech,
                    c.{_quote_identifier(property_column)} AS property_id,
                    c.path, c.HP, c.ATK, c.DEF, c.MATK, c.MDEF, c.SPD,
                    c.explain,
                    p.name AS property_name,
                    p.explain AS property_explain
                FROM {_quote_identifier(character_table)} AS c
                LEFT JOIN {_quote_identifier(property_table)} AS p
                    ON p.id = c.{_quote_identifier(property_column)}
                ORDER BY c.id
                """
            ).fetchall()
            return [
                self._to_character(
                    row,
                    techniques_by_name,
                    basic_techniques,
                    (
                        assigned_by_character.get(row["id"], ())
                        if assigned_by_character is not None
                        else ()
                    ),
                    assigned_by_character is None,
                )
                for row in rows
            ]
        finally:
            connection.close()

    @staticmethod
    def _to_character(
        row,
        techniques_by_name,
        basic_techniques,
        assigned_techniques,
        use_legacy_original,
    ):
        original_name = row["original_tech"] or ""
        original = techniques_by_name.get(original_name)
        techniques = list(basic_techniques)
        techniques.extend(
            technique
            for technique in assigned_techniques
            if technique.id not in {item.id for item in techniques}
        )
        if (
            use_legacy_original
            and original is not None
            and original.id not in {tech.id for tech in techniques}
        ):
            techniques.append(original)
        return ElementCharacter(
            id=row["id"],
            name=row["name"],
            original_tech=original_name,
            property_id=row["property_id"],
            property_name=row["property_name"] or "未分類",
            property_explain=row["property_explain"] or "",
            path=_existing_image_path(row["id"], row["path"]),
            hp=int(row["HP"] or 1),
            atk=int(row["ATK"] or 0),
            defense=int(row["DEF"] or 0),
            matk=int(row["MATK"] or 0),
            mdef=int(row["MDEF"] or 0),
            spd=int(row["SPD"] or 0),
            explain=row["explain"] or "",
            technique=original,
            techniques=tuple(techniques),
        )


def load_characters(db_path=None):
    return CharacterRepository(db_path).load()


def load_techniques(db_path=None):
    return CharacterRepository(db_path).load_techniques()


def load_character_inventory_entries(inventory_path=None):
    """所持素子をcharacter_idとamountの一覧として読み込む。旧形式はamount=1。"""
    path = (
        Path(inventory_path)
        if inventory_path
        else resource_path("INFO", "character_inventory.json")
    )
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    amounts = {}
    order = []
    for index, entry in enumerate(data.get("inventory", [])):
        if not isinstance(entry, dict) or "character_id" not in entry:
            raise ValueError(
                f"character_inventory.jsonのinventory[{index}]にcharacter_idが必要です"
            )
        character_id = int(entry["character_id"])
        amount = int(entry.get("amount", 1))
        if amount < 0:
            raise ValueError(
                f"inventory[{index}]のamountは0以上である必要があります"
            )
        if character_id not in amounts:
            order.append(character_id)
            amounts[character_id] = 0
        amounts[character_id] += amount
    return [
        {"character_id": character_id, "amount": amounts[character_id]}
        for character_id in order
        if amounts[character_id] > 0
    ]


def load_character_inventory(inventory_path=None):
    """所持数が1以上のキャラクターIDを表示順に返す。"""
    return [
        entry["character_id"]
        for entry in load_character_inventory_entries(inventory_path)
    ]


def load_character_amounts(inventory_path=None):
    """character_idをキー、所持数を値とする辞書を返す。"""
    return {
        entry["character_id"]: entry["amount"]
        for entry in load_character_inventory_entries(inventory_path)
    }


def save_character_amounts(amounts, inventory_path=None):
    """所持数をJSONへ安全に保存する。0個の素子は一覧から除外する。"""
    path = (
        Path(inventory_path)
        if inventory_path
        else resource_path("INFO", "character_inventory.json")
    )
    normalized = {
        int(character_id): int(amount)
        for character_id, amount in amounts.items()
    }
    if any(amount < 0 for amount in normalized.values()):
        raise ValueError("素子の所持数を0未満にはできません")

    data = {
        "inventory": [
            {"character_id": character_id, "amount": amount}
            for character_id, amount in sorted(normalized.items())
            if amount > 0
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
        file.write(chr(10))
    temporary.replace(path)


def apply_character_amount_changes(changes, inventory_path=None, party_path=None):
    """複数の増減を一度に適用する。不足時は保存せずFalseを返す。"""
    amounts = load_character_amounts(inventory_path)
    updated = dict(amounts)
    for character_id, difference in changes.items():
        character_id = int(character_id)
        updated[character_id] = updated.get(character_id, 0) + int(difference)
        if updated[character_id] < 0:
            return False

    save_character_amounts(updated, inventory_path)
    current_party = load_party_ids(party_path, updated)
    available_party = [
        character_id
        for character_id in current_party
        if updated.get(character_id, 0) > 0
    ]
    if available_party != current_party:
        save_party_ids(available_party, party_path)
    return True


def load_owned_characters(db_path=None, inventory_path=None):
    """JSONの所持IDをDBのマスターデータと結合する。"""
    masters = {character.id: character for character in load_characters(db_path)}
    character_ids = load_character_inventory(inventory_path)
    missing_ids = [character_id for character_id in character_ids if character_id not in masters]
    if missing_ids:
        missing = ", ".join(map(str, missing_ids))
        raise ValueError(f"character.dbに存在しないcharacter_id: {missing}")
    return [masters[character_id] for character_id in character_ids]


def load_party_ids(party_path=None, owned_ids=None):
    """編成JSONから最大4人のIDを読み込む。未作成時は所持順の先頭4人。"""
    path = Path(party_path) if party_path else resource_path("INFO", "party.json")
    if not path.exists():
        if owned_ids is None:
            owned_ids = load_character_inventory()
        return list(dict.fromkeys(int(value) for value in owned_ids))[:4]

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    entries = data.get("party", [])
    result = []
    for index, entry in enumerate(entries):
        value = entry.get("character_id") if isinstance(entry, dict) else entry
        if value is None:
            raise ValueError(f"party.jsonのparty[{index}]にcharacter_idが必要です")
        character_id = int(value)
        if character_id not in result:
            result.append(character_id)
    if len(result) > 4:
        raise ValueError("編成できる素子は最大4人です")
    return result


def save_party_ids(character_ids, party_path=None):
    """最大4人の編成をJSONへ保存する。"""
    path = Path(party_path) if party_path else resource_path("INFO", "party.json")
    unique_ids = list(dict.fromkeys(int(value) for value in character_ids))
    if len(unique_ids) > 4:
        raise ValueError("編成できる素子は最大4人です")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"party": [{"character_id": value} for value in unique_ids]}
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
        file.write("\n")
    temporary.replace(path)


def load_party_characters(db_path=None, inventory_path=None, party_path=None):
    """所持キャラクターのうち編成JSONに並ぶ最大4人を返す。"""
    owned = load_owned_characters(db_path, inventory_path)
    owned_by_id = {character.id: character for character in owned}
    party_ids = load_party_ids(party_path, owned_by_id)
    invalid = [character_id for character_id in party_ids if character_id not in owned_by_id]
    if invalid:
        missing = ", ".join(map(str, invalid))
        raise ValueError(f"所持していないcharacter_idが編成されています: {missing}")
    return [owned_by_id[character_id] for character_id in party_ids][:4]


def load_item_masters(db_path=None):
    """DBのitemsテーブルを道具画面で使う辞書へ変換する。"""
    path = Path(db_path) if db_path else resource_path("INFO", "character.db")
    connection = _snapshot_connection(path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT id, name, explain FROM items ORDER BY id"
        ).fetchall()
        return {
            str(row["id"]): {
                "name": row["name"] or "不明な道具",
                "explain": row["explain"] or "",
                "lore": [row["explain"] or ""],
            }
            for row in rows
        }
    finally:
        connection.close()
