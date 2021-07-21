from cocos.sprite import Sprite
from cocos.euclid import Vector2
from cocos.collision_model import CollisionManagerGrid, AARectShape
from cocos.layer import Layer
from cocos.director import director
from cocos.scene import Scene
from cocos.text import Label
from pyglet.window import key
from pyglet.image import load as iload, ImageGrid, Animation
from pyglet.media import load as mload
from random import random


class Actor(Sprite):
    def __init__(self, image, x, y):
        super(Actor, self).__init__(image)

        pos = Vector2(x, y)
        self.position = pos

        self.cshape = AARectShape(pos, self.width * 0.5, self.height * 0.5)

    def move(self, offset = tuple[int, int]):
        self.position += offset
        self.cshape.center += offset

    def update(self, delta_time):
        pass  # will be overridden in *subclasses*

    def collide(self, other):
        pass


class PlayerCannon(Actor):
    def __init__(self, x, y):
        super(PlayerCannon, self).__init__("img/cannon.png", x, y)

        self.speed = Vector2(200, 0)

    def collide(self, other: Actor):
        other.kill()
        self.kill()

    def update(self, delta_time):
        horizontal_movement_direction = keyboard[key.RIGHT] - keyboard[key.LEFT]

        left_edge = self.width * 0.5
        right_edge = self.parent.width - left_edge

        magnitude = self.speed * horizontal_movement_direction * delta_time

        if left_edge <= (self.x + magnitude) <= right_edge:  # can move
            self.move(magnitude)

class HUD(Layer):
    def __init__(self):
        super(HUD, self).__init__()

        w, h = director.get_window_size()

        self.score_text = Label("", font_size=18)
        self.score_text.position = (20, h - 40)

        self.lives_text = Label("", font_size=18)
        self.lives_text.position = (w - 100, h - 40)

        self.add(self.score_text)
        self.add(self.lives_text)

    def update_score(self, new_score):
        self.score_text.element.text = f"Score: {new_score}"

    def update_lives(self, new_lives):
        self.lives_text.element.text = f"Lives: {new_lives}"

    def show_over(self, message):
        w, h = director.get_window_size()

        text = Label(message, font_size=50, anchor_x="center", anchor_y="center")
        text.position = (w * 0.5, h * 0.5)

        self.add(text)


class GameLayer(Layer):
    def __init__(self, hud):
        super(GameLayer, self).__init__()

        self.hud = hud

        w, h = director.get_window_size()
        self.width = w
        self.height = h

        self.lives = 3
        self.score = 0

        # create the player and set the initial score
        self.add_points()
        self.create_player()

        cell = 1.25 * 50  # 50px * 125%
        self.collman = CollisionManagerGrid(0, w, 0, h, cell, cell)

        self.schedule(self.game_loop)

    def create_player(self):
        self.player = PlayerCannon(self.width * 0.5, 50)
        self.add(self.player)

        self.hud.update_lives(self.lives)

    def add_points(self, points=0):
        self.score += points
        self.hud.update_score(self.score)

    def game_loop(self, delta_time):

        self.collman.clear()

        for _, actor in self.children:
            self.collman.add(actor)
            actor.update(delta_time)


if __name__ == "__main__":
    director.init(caption="Gap Occupiers", width=800, height=650)

    keyboard = key.KeyStateHandler()
    director.window.push_handlers(keyboard)

    scene = Scene()

    hud_layer = HUD()
    scene.add(hud_layer, z=1)

    game_layer = GameLayer(hud_layer)
    scene.add(game_layer, z=0)

    director.run(scene)
