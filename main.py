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


def load_animation(image, rows=2, cols=1, fr=0.5):
    seq = ImageGrid(iload(image), rows, cols)
    return Animation.from_image_sequence(seq, fr)


SPECIES = {
    '1': (load_animation('img/alien1.png'), 40),
    '2': (load_animation('img/alien2.png'), 20),
    '3': (load_animation('img/alien3.png'), 10)
}


class Actor(Sprite):
    def __init__(self, image, x, y):
        super(Actor, self).__init__(image)

        pos = Vector2(x, y)
        self.position = pos

        self.cshape = AARectShape(pos, self.width * 0.5, self.height * 0.5)

    def move(self, offset: tuple[int, int]):
        self.position += offset
        self.cshape.center += offset

    def update(self, delta_time):  # maybe a different method name should be used
        pass  # this method will be overridden in *subclasses*

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
        # rightward is positive, leftward is negative
        horizontal_movement_direction = keyboard[key.RIGHT] - keyboard[key.LEFT]

        left_edge = self.width * 0.5
        right_edge = self.parent.width - left_edge

        magnitude = self.speed * horizontal_movement_direction * delta_time

        if (left_edge <= self.x <= right_edge) or (
                (horizontal_movement_direction > 0 and self.x < right_edge) or
                (horizontal_movement_direction < 0 and self.x > left_edge)
        ):  # can move
            self.move(magnitude)


class Alien(Actor):
    def __init__(self, img, x, y, points, column=None):
        super(Alien, self).__init__(img, x, y)

        self.points = points
        self.column = column

    def on_exit(self):  # part of a superclass, called when removed from scene
        super(Alien, self).on_exit()
        if self.column:
            self.column.remove(self)

    @staticmethod
    def from_type(x, y, alien_type, column):
        animation, points = SPECIES[alien_type]
        return Alien(animation, x, y, points, column)


class AlienColumn:
    def __init__(self, x: int, y: int):
        alien_types = enumerate(['1', '1', '2', '2', '3'])

        self.aliens = [
            Alien.from_type(x, y + i * 60, alien_type, self) for i, alien_type in alien_types
        ]

    def remove(self, alien: Alien):  # called by alien objects when they exit the scene
        self.aliens.remove(alien)  # remove record from list

    def danger_close(self, direction: int):
        if len(self.aliens) == 0:
            return False

        alien = self.aliens[0]
        # i don't understand why `width` is window width instead of sprite width
        # never mind, the parent isn't the superclass, it's the actual obj parent in the display
        # the only parent of these 'sprites' is the window
        x, width = alien.x, alien.parent.width

        return x >= width - 50 and direction == 1 \
            or x <= 50 and direction == -1


class Swarm:
    def __init__(self, x: int, y: int, game):
        """
        :type game: GameLayer
        """
        self.columns = [AlienColumn(x + i * 60, y) for i in range(10)]
        self.gl = game

        self.level = 1
        self.level_modifier = 1.0
        self.level_elapsed = 0
        self.level_period = 20

        self.base_speed = Vector2(10, 0)
        self.speed = self.base_speed * self.level_modifier
        self.direction = 1

        self.elapsed = 0.0
        self.period = 1.0

        self.increase_temp = False

    def __iter__(self):
        for col in self.columns:
            for alien in col.aliens:
                yield alien

    def side_reached(self):
        return any(map(lambda col: col.danger_close(self.direction), self.columns))

    def update(self, dt):
        self.elapsed += dt
        # loop because the ∆t may constitute more than one update in a single update() call
        # if it is longer than the period
        while self.elapsed >= self.period:
            self.elapsed -= self.period

            movement = self.direction * self.speed
            if self.side_reached():
                self.direction *= -1
                movement = Vector2(0, -10)

            for alien in self:  # use iterator and move all sub actors
                alien.move(movement)

        self.level_elapsed += dt
        while self.level_elapsed > self.level_period:
            self.level_elapsed -= self.level_period
            self.increase_difficulty()

        if not self.increase_temp and keyboard[key.DOWN]:
            self.increase_temp = True
        if not keyboard[key.DOWN] and self.increase_temp:
            self.increase_temp = False
            self.increase_difficulty()

    def increase_difficulty(self):
        self.level += 1
        self.gl.set_level(self.level)
        self.level_modifier += 0.3
        self.speed = self.base_speed * self.level_modifier


class PlayerShoot(Actor):
    ACTIVE_SHOOT = None

    def __init__(self, x, y):
        super(PlayerShoot, self).__init__('img/missile.png', x, y)

        self.speed = Vector2(0, 400)
        PlayerShoot.ACTIVE_SHOOT = self

    def collide(self, other):
        if isinstance(other, Alien):
            self.parent.update_score(other.points)


class HUD(Layer):
    def __init__(self):
        super(HUD, self).__init__()

        w, h = director.get_window_size()

        self.score_text = Label("", font_size=18, color=(230, 255, 0, 255))
        self.score_text.position = (20, h - 40)

        self.lives_text = Label("", font_size=18, italic=True, bold=True, color=(255, 0, 50, 255), anchor_x="right")
        self.lives_text.position = (w - 20, h - 40)

        self.level_text = Label("", font_size=18, color=(100, 80, 200, 255), bold=True, anchor_x="center")
        self.level_text.position = (w / 2, h - 40)

        self.add(self.score_text)
        self.add(self.lives_text)
        self.add(self.level_text)

    def update_score(self, new_score: int):
        self.score_text.element.text = f"Score: {new_score}"

    def update_lives(self, new_lives: int):
        lives_display = " ".join(["♥" for _ in range(new_lives)])
        self.lives_text.element.text = f"Lives: {lives_display}"

    def update_level(self, new_level: int):
        self.level_text.element.text = f"Lvl: {new_level}"

    def show_over(self, message):
        w, h = director.get_window_size()

        text = Label(message, font_size=50, anchor_x="center", anchor_y="center")
        text.position = (w * 0.5, h * 0.5)

        self.add(text)


class GameLayer(Layer):
    def __init__(self, hud: HUD):
        super(GameLayer, self).__init__()

        w, h = director.get_window_size()
        self.width = w  # set layer to match window size
        self.height = h

        self.hud = hud  # add reference to hud to enable external control
        self.lives = 3  # default hud values
        self.score = 0
        # set the initial score
        self.add_points()

        # create the player
        # self.player = PlayerCannon(self.width * 0.5, 50)
        self.player = None
        self.create_player()  # causes definition outside of __init__ warning
        self.swarm = None
        self.create_swarm(100, 300)

        cell = 1.25 * 50  # 50px * 125%
        self.collman = CollisionManagerGrid(0, w, 0, h, cell, cell)

        self.schedule(self.game_loop)  # schedule game_loop() to be run every frame

    def create_player(self):
        self.player = PlayerCannon(self.width * 0.5, 50)
        self.add(self.player)

        self.hud.update_lives(self.lives)

    def create_swarm(self, x, y):
        self.swarm = Swarm(x, y, self)
        for alien in self.swarm:
            self.add(alien)
        self.hud.update_level(1)

    def add_points(self, points=0):
        self.score += points
        self.hud.update_score(self.score)

    def set_level(self, level=1):
        self.hud.update_level(level)

    def game_loop(self, dt):
        self.collman.clear()

        for _, actor in self.children:
            self.collman.add(actor)
            actor.update(dt)

        self.swarm.update(dt)


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
