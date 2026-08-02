import pygame
from pathlib import Path

pygame.init()

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resource_path(*parts):
    path = Path(*parts)
    if path.parts and path.parts[0] == PROJECT_ROOT.name:
        path = Path(*path.parts[1:])
    return PROJECT_ROOT / path


WIDTH = 800
HEIGHT = 640
TILE = 32

FONT = pygame.font.SysFont("msgothic", 24)

WHITE = (255,255,255)
LOWH = (180,180,180)
GRAY = (128,128,128)
LOWB = (60,60,60)
BLACK = (0,0,0)
RED = (255,0,0)
YELLOW = (255,255,0)
LOW_YELLOW = (125,125,0)
GYELLOW = (154,205,50)
GREEN = (0,255,0)
BLUE = (0,0,255)
LOW_BLUE = (0,0,50)

SPEED = 4

# move
RIGHT = "right"
LEFT = "left"
FRONT = "front"
BACK = "back"

#player_mode
MOVE = "move"
MENU = "menu"
DOUGU = "dougu"
ELEMENT = "element"
FORMATION = "formation"
SAVE = "save"
SYNTHESIS = "synthesis"
BATTLE = "battle"
SPEAK = "speak"

FPS = 60

