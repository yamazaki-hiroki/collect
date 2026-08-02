import pygame
from .config import *

class Button():
    def __init__(self, x, y, w, h, text = "", font=FONT, color=LOW_YELLOW, hover=YELLOW):
        self.rect = pygame.Rect(x, y, w, h)
        self.color = color
        self.hover = hover
        self.text = font.render(text, True, WHITE)
        self.text_rect = self.text.get_rect(center=self.rect.center)

    def text_change(self, text="", font=FONT, color=BLACK):
        self.text = font.render(text, True, color)
        self.text_rect = self.text.get_rect(center=self.rect.center)
        return self.text, self.text_rect

    def is_hover(self, mx, my):
        return self.rect.collidepoint(mx, my)
    
    def draw(self, screen, mx, my, selected=False):
        pygame.draw.rect(screen, LOW_BLUE, self.rect)
        border_color = self.hover if selected or self.is_hover(mx, my) else self.color
        pygame.draw.rect(screen, border_color, self.rect, 4 if selected else 2)
        screen.blit(self.text, self.text_rect)
