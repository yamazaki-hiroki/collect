import pygame
import sqlite3 as sq

class character :
    #名前、特性、HP、攻撃、防御、魔攻、魔防、素早さ、説明、画像のパス
    def __init__(self,name :str, property :str, HP :int, ATK :int, DEF :int, MATK :int, MDEF :int, SPD :int, explain :str, path :str):
        self.name: str = name
        self.property: str = property
        self.HP: int = HP
        self.ATK: int = ATK
        self.DEF: int = DEF
        self.MATK: int = MATK
        self.MDEF: int = MDEF
        self.SPD: int = SPD
        self.explain: str = explain
        self.path: str = path
        try:
            self.img = pygame.image.load(self.path)
        except:
            pass


    #パスをもとに画像の表示
    #pygameのスクリーン、幅、高さ、ｘ座標、ｙ座標
    def draw(self,screen :pygame.display, x :int, y :int, width :int = 96, height :int = 96) -> None:
        self.img = pygame.transform.scale(self.img, (width, height))
        screen.blit(self.img, (x, y))

DB_PATH = r"character.db"
conn = sq.connect(DB_PATH)
cur = conn.cursor()

def set_char(id :int) -> character:
    cur.execute("""SELECT
                characters.name,
                property.name AS property,
                characters.HP,
                characters.ATK,
                characters.DEF,
                characters.MATK,
                characters.MDEF,
                characters.SPD,
                characters.explain,
                characters.path
                FROM characters
                INNER JOIN property
                ON characters.property = property.id
                WHERE characters.id = ?;""",(id,))
    char_data :list = cur.fetchone()
    return character(*char_data)