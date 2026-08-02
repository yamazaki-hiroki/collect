"""Central BGM and sound-effect playback for the game."""

from pathlib import Path

import pygame

from COMMON.config import resource_path


class AudioManager:
    BGM_FILES = {
        "field": ("INFO", "BGM", "\u6751.mp3"),
        "battle": ("INFO", "BGM", "\u30d0\u30c8\u30eb.mp3"),
    }
    BGM_VOLUMES = {"field": 0.20, "battle": 0.45}
    SE_FILES = {
        "electric": ("INFO", "DX\u52b9\u679c\u97f3", "\u96fb\u6c17.mp3"),
        "light": ("INFO", "DX\u52b9\u679c\u97f3", "\u767a\u5149.mp3"),
        "charge": ("INFO", "DX\u52b9\u679c\u97f3", "\u5145\u96fb.mp3"),
        "oscillation": ("INFO", "DX\u52b9\u679c\u97f3", "\u767a\u632f.mp3"),
        "buff": ("INFO", "DX\u52b9\u679c\u97f3", "\u30d0\u30d5.mp3"),
        "heat": ("INFO", "DX\u52b9\u679c\u97f3", "\u71b1.mp3"),
    }

    def __init__(self, bgm_volume=0.45, se_volume=0.65):
        self.bgm_volume = max(0.0, min(1.0, float(bgm_volume)))
        self.se_volume = max(0.0, min(1.0, float(se_volume)))
        self.available = False
        self.initialized = False
        self.current_bgm = None
        self.sounds = {}

    def initialize(self):
        if self.initialized:
            return self.available
        self.initialized = True
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            pygame.mixer.music.set_volume(self.bgm_volume)
            for name, parts in self.SE_FILES.items():
                path = Path(resource_path(*parts))
                if not path.is_file():
                    continue
                sound = pygame.mixer.Sound(path)
                sound.set_volume(self.se_volume)
                self.sounds[name] = sound
            self.available = True
        except (pygame.error, OSError):
            self.available = False
            self.sounds.clear()
        return self.available

    def play_bgm(self, name, loops=-1):
        if not self.initialize() or name not in self.BGM_FILES:
            return False
        if self.current_bgm == name and pygame.mixer.music.get_busy():
            return True
        path = Path(resource_path(*self.BGM_FILES[name]))
        if not path.is_file():
            return False
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(
                self.BGM_VOLUMES.get(name, self.bgm_volume)
            )
            pygame.mixer.music.play(loops=loops)
            self.current_bgm = name
            return True
        except (pygame.error, OSError):
            self.current_bgm = None
            return False

    def stop_bgm(self, fade_ms=0):
        if not self.available:
            return
        try:
            if fade_ms > 0:
                pygame.mixer.music.fadeout(int(fade_ms))
            else:
                pygame.mixer.music.stop()
        except pygame.error:
            pass
        self.current_bgm = None

    def play_se(self, name):
        if not self.initialize():
            return False
        sound = self.sounds.get(name)
        if sound is None:
            return False
        try:
            sound.play()
            return True
        except pygame.error:
            return False

    def play_technique(self, technique):
        name = str(getattr(technique, "name", ""))
        attribute = str(getattr(technique, "attribute", ""))
        effect = str(getattr(technique, "effect_code", ""))

        if name == "\u767a\u632f":
            return self.play_se("oscillation")
        if name == "\u767a\u5149":
            return self.play_se("light")
        if effect == "heal" or attribute == "\u56de\u5fa9":
            return self.play_se("charge")
        if effect in ("buff", "defend") or attribute in ("\u30d0\u30d5", "\u9632\u5fa1"):
            return self.play_se("buff")
        if attribute == "\u71b1":
            return self.play_se("heat")
        if attribute == "\u96fb\u6c17" or effect == "damage":
            return self.play_se("electric")
        return False

    def shutdown(self):
        if not self.initialized:
            return
        self.stop_bgm()
        self.sounds.clear()
        self.available = False
        self.initialized = False


audio_manager = AudioManager()