from cocos.sprite import Sprite
from cocos.euclid import Vector2
from cocos.collision_model import CollisionManagerGrid, AARectShape
from cocos.layer import Layer
from cocos.director import director
from cocos.scene import Scene
from cocos.text import Label
from pyglet.window import key
from pyglet.image import load as iload, ImageGrid, Animation
from pyglet.media import load as mload, Player
from random import random

shoot_sfx = mload('sfx/shoot.wav', streaming=False)
kill_sfx = mload("sfx/invaderkilled.wav", streaming=False)
die_sfx = mload('sfx/explosion.wav', streaming=False)
bg_music = mload('sfx/level1.ogg', streaming=False)


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
        super().__init__(image)

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
        super().__init__("img/cannon.png", x, y)

        self.speed = Vector2(200, 0)

    def collide(self, other: Actor):
        other.kill()  # this causes an error for some reason
        # self.kill()  # this is handled in the respawn method
        self.parent.respawn_player()  # calling respawn from here on collision

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

        is_firing = keyboard[key.SPACE] or keyboard[key.UP]
        if PlayerShoot.ACTIVE_SHOOT is None and is_firing:
            self.parent.add(PlayerShoot(self.x, self.y + 50))
            shoot_sfx.play()

        # if self.parent.collide_check(self):
        #     self.parent.respawn_player()


class PlayerShoot(Actor):
    ACTIVE_SHOOT = None

    def __init__(self, x, y):
        super().__init__(load_animation('img/missile2.png', fr=0.2), x, y)

        self.speed = Vector2(0, 400)
        PlayerShoot.ACTIVE_SHOOT = self

    def on_exit(self):
        super().on_exit()
        PlayerShoot.ACTIVE_SHOOT = None

    def collide(self, other):
        # print(f"collision: {str(other)}")
        if isinstance(other, Alien):
            self.parent.add_points(other.points)  # add the alien's assigned number of points
            # self.parent.remove(PlayerShoot.ACTIVE_SHOOT)
            # remove the alien and missile instances
            self.kill()
            other.kill()
            kill_sfx.play()

    def update(self, delta_time):
        self.move(self.speed * delta_time)


class Alien(Actor):
    def __init__(self, img, x, y, points, column=None):
        super().__init__(img, x, y)

        self.points = points
        self.column = column

    def on_exit(self):  # part of a superclass, called when removed from scene
        super().on_exit()
        if self.column:
            self.column.remove(self)

    @staticmethod
    def from_type(x, y, alien_type, column):
        animation, points = SPECIES[alien_type]
        return Alien(animation, x, y, points, column)

    def collide(self, other):
        self.kill()


class AlienShoot(Actor):
    def __init__(self, x, y):
        super().__init__('img/shoot.png', x, y)

        self.speed = Vector2(0, -400)

    def update(self, delta_time):
        self.move(self.speed * delta_time)


class AlienColumn:
    def __init__(self, x: int, y: int, swarm):
        alien_types = enumerate(['3', '3', '2', '2', '1'])

        self.swarm = swarm

        self.aliens = [
            Alien.from_type(x, y + i * 60, alien_type, self) for i, alien_type in alien_types
        ]

    def remove(self, alien: Alien):  # called by alien objects when they exit the scene
        self.aliens.remove(alien)  # remove record from list

    def danger_close(self, direction: int):
        if len(self.aliens) == 0:
            self.swarm.remove(self)
            return False

        alien = self.aliens[0]
        # i don't understand why `width` is window width instead of sprite width
        # never mind, the parent isn't the superclass, it's the actual obj parent in the display
        # the only parent of these 'sprites' is the window
        x, width = alien.x, alien.parent.width

        return x >= width - 50 and direction == 1 \
            or x <= 50 and direction == -1

    def shoot(self):
        if len(self.aliens) > 0 and random() < self.swarm.shoot_probability:  # 5% probability per second
            x, y = self.aliens[0].position
            return AlienShoot(x, y - 50)  # shoot 50px below origin
        else:
            return None


class Swarm:
    def __init__(self, x: int, y: int, game):
        """
        :type game: GameLayer
        """
        self.columns = [AlienColumn(x + i * 60, y, self) for i in range(10)]
        self.gl = game

        self.shoot_probability = 0.0001

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

    def remove(self, col):
        self.columns.remove(col)

    def update(self, dt):
        if len([0 for _ in self]) < 1:
            self.gl.game_finish()
            return

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

        # FIXME: temporary logic to allow manually increasing level
        if not self.increase_temp and keyboard[key.DOWN]:
            self.increase_temp = True
        if not keyboard[key.DOWN] and self.increase_temp:
            self.increase_temp = False
            self.increase_difficulty()

    def increase_difficulty(self):
        """
        Increase the speed of swarm movement and possibly other properties
        to simulate a 'harder' enemy
        """
        if self.level < 15:
            self.level += 1  # set internal reference to level
            self.gl.set_level(self.level)  # set level on scoreboard and in GameLayer

            # self.level_modifier += 0.3
            modifier_mod = -0.008
            if self.level_modifier + modifier_mod > 0:
                self.level_modifier += modifier_mod  # while step rate increases, decrease distance
            period_mod = -0.07
            if self.period + period_mod > 0:
                self.period += period_mod  # increase rate of alien movement (not distance)
            self.shoot_probability += 0.0006

            self.speed = self.base_speed * self.level_modifier  # set actual speed


class HUD(Layer):
    def __init__(self):
        super().__init__()

        w, h = director.get_window_size()

        self.score_text = Label("", font_size=18, color=(230, 255, 0, 255))
        self.score_text.position = (20, h - 40)

        self.lives_text = Label("", font_size=18, italic=True, bold=True, color=(255, 0, 50, 255), anchor_x="right")
        self.lives_text.position = (w - 20, h - 40)

        self.level_text = Label("", font_size=18, color=(100, 80, 200, 255), bold=True, anchor_x="center")
        self.level_text.position = (w / 2, h - 40)

        self.jumbo_text = None

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

    def show_jumbo(self, message, color=(169, 18, 18, 255)):
        w, h = director.get_window_size()

        text = Label(message, color=color, font_size=50, anchor_x="center", anchor_y="center", bold=True)
        text.position = (w * 0.5, h * 0.5)

        self.jumbo_text = text
        self.add(self.jumbo_text)

    def hide_jumbo(self):
        if self.jumbo_text:
            self.remove(self.jumbo_text)


class GameLayer(Layer):
    def __init__(self, hud: HUD, music: Player):
        super().__init__()

        self.music_player = music

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
        if self.player is not None:
            self.player.kill()
            self.player = None  # not having this caused a 'cannot find child' error before
        self.player = PlayerCannon(self.width * 0.5, 50)
        self.add(self.player)

        self.hud.update_lives(self.lives)

    def create_swarm(self, x, y):
        if self.swarm is not None:
            self.swarm = None
        self.swarm = Swarm(x, y, self)
        for alien in self.swarm:
            self.add(alien)
        self.hud.update_level(1)

    def add_points(self, points=0, oust=False):
        prev_m = self.score % 150
        if oust:
            self.score = points
        else:
            self.score += points
        self.hud.update_score(self.score)
        if prev_m > self.score % 150:
            self.swarm.increase_difficulty()

    def set_level(self, level=1):
        self.hud.update_level(level)

    def respawn_player(self):
        if self.player is not None:
            self.player.kill()
            self.player = None  # not having this caused a 'cannot find child' error before
            # it must mean that it was trying to kill the player
            # because it was 'not None' even when no player had been spawned
            die_sfx.play()
        self.lives -= 1
        if self.lives < 1:
            self.hud.update_lives(0)
            self.game_over()
        else:
            self.create_player()

    def game_over(self):
        self.unschedule(self.game_loop)
        self.music_player.pause()
        # self.music_player.delete()
        self.hud.show_jumbo('GAME OVER')
        self.schedule(listen_start)

    def game_finish(self):
        self.unschedule(self.game_loop)
        self.music_player.pause()
        # self.music_player.delete()
        self.hud.show_jumbo('MISSION COMPLETE', (0, 200, 50, 255))
        self.schedule(self.listen_next_mission)

    def collide_check(self, actor):
        """
        :param actor: who to check if colliding with something else
        :return: boolean
        """
        if actor is not None:
            for colliding_actor in self.collman.iter_colliding(actor):
                actor.collide(colliding_actor)
                return True

        return False

    def game_loop(self, dt):
        # collision checking
        # for _, actor in self.children:
        #

        # update actors and reset collision grid
        self.collman.clear()

        for _, actor in self.children:
            self.collman.add(actor)
            if not self.collman.knows(actor):
                self.remove(actor)

            actor.update(dt)

            self.collide_check(actor)

        for column in self.swarm.columns:
            shoot = column.shoot()
            if shoot is not None:
                self.add(shoot)

        self.swarm.update(dt)  # the swarm will move AFTER collision checking, do I want that?

        self.collide_check(PlayerShoot.ACTIVE_SHOOT)
        self.collide_check(self.player)

    def listen_next_mission(self, _):
        start_key_pressed = keyboard[key.ENTER] or keyboard[key.NUM_ENTER] or keyboard[key.SPACE]
        if start_key_pressed:
            self.unschedule(self.listen_next_mission)
            self.create_swarm(100, 300)
            # self.create_player()

            self.lives = 3  # default hud values
            self.hud.update_lives(self.lives)
            # self.add_points(oust=True)  # keeping score because it isn't a new game
            # self.hud.update_score(self.score)
            self.hud.hide_jumbo()
            self.music_player.play()

            self.schedule(self.game_loop)


class GameScene(Scene):
    def __init__(self):
        super().__init__()

        self.hud_layer = HUD()
        self.add(self.hud_layer, z=1)
        self.game_layer = GameLayer(self.hud_layer, player)
        self.add(self.game_layer, z=0)


class TitleScreen(Layer):
    def __init__(self):
        super().__init__()

        w, h = director.get_window_size()
        self.width = w
        self.height = h

        self.title_text = Label("GAP OCCUPIERS", font_size=50, color=(100, 80, 200, 255), bold=True, anchor_x="center")
        self.title_text.position = (w / 2, h - 130)

        self.start_instruction_text = Label("Press ENTER to begin", font_size=18, color=(255, 180, 20, 255), bold=True,
                                            anchor_x="center")
        self.start_instruction_text.position = (w / 2, h / 2)

        self.add(self.title_text)
        self.add(self.start_instruction_text)


class TitleScene(Scene):
    def __init__(self):
        super().__init__()

        self.screen = TitleScreen()
        self.add(self.screen)

        self.schedule(listen_start)


def listen_start(_):
    start_key_pressed = keyboard[key.ENTER] or keyboard[key.NUM_ENTER] or keyboard[key.SPACE]
    if start_key_pressed:
        # self.end()
        director.replace(GameScene())


if __name__ == "__main__":
    player = bg_music.play()
    player.loop = True
    director.init(caption="Gap Occupiers", width=800, height=650)

    keyboard = key.KeyStateHandler()
    director.window.push_handlers(keyboard)

    # scene = Scene()
    # t_scene = TitleScene()
    # g_scene = GameScene()

    # hud_layer = HUD()
    # scene.add(hud_layer, z=1)
    #
    # game_layer = GameLayer(hud_layer, player)
    # scene.add(game_layer, z=0)

    # director.run(scene)
    # director.push(g_scene)
    # director.push(t_scene)
    director.run(TitleScene())
