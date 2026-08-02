import json
import pygame
from COMMON.config import *
from COMMON.button import Button

dougu_inv_json = """
[
    {
        "item_id": 1,
        "amount": 5
    },
    {
        "item_id": 2,
        "amount": 1
    }
]
"""

# アイテムデータベース（マスターデータ）
dougu_json = """
{
    "1": {
        "name": "item1",
        "lore": [
            "lore1",
            "lore2"
        ]
    },
    "2": {
        "name": "item2",
        "lore": [
            "lore3",
            "lore4"
        ]
    }
}
"""

inv_list = json.loads(dougu_inv_json)
item_dict = json.loads(dougu_json)
class Dougu:
    def __init__(self, hand):
        self.canvas = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.canvas.fill((0,0,0,200)) 
        self.hand = hand
        self.button = {
            "element":Button(20, HEIGHT*2/3 + 20, 240, 80, "素子"),
            "move":Button(280, HEIGHT*2/3 + 20, 240, 80, "移動"),
            "item":Button(540, HEIGHT*2/3 + 20, 240, 80, "道具"),
            "file":Button(20, HEIGHT*2/3 + 110, 240, 80, "ファイル"),
            "save":Button(280, HEIGHT*2/3 + 110, 240, 80, "セーブ"),
            "close":Button(540, HEIGHT*2/3 + 110, 240, 80, "閉じる"),
        }
        self.mode = None

    def update(self, event, mx, my):
        if event.type != pygame.MOUSEBUTTONDOWN:
            return MENU
        if self.button["close"].is_hover(mx, my):
            return MOVE
        return MENU

    def draw(self, screen, mx, my):
        screen.blit(self.canvas, (0,0))
        pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, 30))
        pygame.draw.rect(screen, LOW_YELLOW, (0, 0, WIDTH, 30),2)
        pygame.draw.rect(screen, BLACK, (0, HEIGHT*2/3, WIDTH, HEIGHT/3))
        pygame.draw.rect(screen, LOW_YELLOW, (0, HEIGHT*2/3, WIDTH, HEIGHT/3),2)
        for _, button in self.button.items():
            button.draw(screen, mx, my)
