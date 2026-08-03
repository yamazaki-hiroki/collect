import sys

import pygame

from COMMON.audio import audio_manager
from COMMON.config import *
from PLAY.player import Player
from PLAY.title import CONTINUE_GAME, NEW_GAME, TitleScreen
from save_load import (
    SaveDataError,
    initial_player_data,
    load_game,
    reset_new_game_files,
)


def player_from_player_data(player_data, save_slot):
    player = Player(
        str(player_data["name"]),
        int(player_data["map_num"]),
        int(player_data["x"]),
        int(player_data["y"]),
        save_slot=save_slot,
        tutorial_stage=int(
            player_data.get(
                "tutorial_stage",
                0 if int(player_data["map_num"]) == 1 else 3,
            )
        ),
        party_status=player_data.get("party_status"),
        checkpoint=player_data.get(
            "checkpoint",
            {
                "map_num": int(player_data["map_num"]),
                "x": int(player_data["x"]),
                "y": int(player_data["y"]),
                "direction": str(player_data.get("direction", FRONT)),
            },
        ),
    )
    player.money = int(player_data["money"])
    player.menu.money = player.money
    player.dougu.money = player.money
    player.move.direction = str(player_data["direction"])
    player.encounter_safe_steps = max(
        0,
        int(player_data.get("encounter_safe_steps", 0)),
    )
    audio_manager.play_bgm("field")
    return player


def player_from_game_data(data, save_slot=1):
    return player_from_player_data(data.player, save_slot)


def main():
    pygame.init()
    audio_manager.initialize()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Hackit \u7d20\u5b50\u30b3\u30ec\u30af\u30c8")
    clock = pygame.time.Clock()

    title = TitleScreen()
    player = None

    while True:
        mx, my = pygame.mouse.get_pos()
        if player is None:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                result = title.update(event, mx, my)
                if result is None:
                    continue
                action, slot = result
                if action == NEW_GAME:
                    try:
                        reset_new_game_files()
                        player = player_from_player_data(initial_player_data(), slot)
                    except (SaveDataError, OSError, ValueError) as error:
                        title.set_message(f"\u958b\u59cb\u3067\u304d\u307e\u305b\u3093: {error}")
                elif action == CONTINUE_GAME:
                    try:
                        data = load_game(slot=slot)
                        player = player_from_game_data(data, slot)
                    except (SaveDataError, OSError, ValueError) as error:
                        title.set_message(f"\u30ed\u30fc\u30c9\u5931\u6557: {error}")
            screen.fill(BLACK)
            title.draw(screen, mx, my)
        else:
            player.update(mx, my)
            screen.fill((40, 40, 40))
            player.draw(screen, mx, my)

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()