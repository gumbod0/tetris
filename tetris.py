#!/usr/bin/env python3
"""Минимальный консольный тетрис на curses..

Управление:
    ← →   — сдвиг
    ↑     — поворот
    ↓     — ускоренное падение
    Space — мгновенный сброс
    P     — пауза
    Q     — выход
"""

import curses
import random
import time

WIDTH, HEIGHT = 10, 20

# Фигуры заданы набором клеток (x, y) в исходной ориентации.
SHAPES = {
    "I": [(0, 1), (1, 1), (2, 1), (3, 1)],
    "O": [(1, 0), (2, 0), (1, 1), (2, 1)],
    "T": [(1, 0), (0, 1), (1, 1), (2, 1)],
    "S": [(1, 0), (2, 0), (0, 1), (1, 1)],
    "Z": [(0, 0), (1, 0), (1, 1), (2, 1)],
    "J": [(0, 0), (0, 1), (1, 1), (2, 1)],
    "L": [(2, 0), (0, 1), (1, 1), (2, 1)],
}
COLORS = {name: i + 1 for i, name in enumerate(SHAPES)}
LINE_SCORES = {1: 100, 2: 300, 3: 500, 4: 800}


def rotate(cells, size):
    """Поворот на 90° по часовой стрелке внутри квадрата size x size.."""
    return [(size - 1 - y, x) for x, y in cells]


class Piece:
    def __init__(self, kind):
        self.kind = kind
        self.cells = list(SHAPES[kind])
        self.x = WIDTH // 2 - 2
        self.y = -1

    def blocks(self, dx=0, dy=0, cells=None):
        cells = self.cells if cells is None else cells
        return [(self.x + cx + dx, self.y + cy + dy) for cx, cy in cells]


class Game:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.board = [[None] * WIDTH for _ in range(HEIGHT)]
        self.score = 0
        self.lines = 0
        self.over = False
        self.bag = []
        self.next_kind = self._draw_kind()
        self.piece = None
        self.spawn()

    @property
    def level(self):
        return self.lines // 10 + 1

    @property
    def fall_delay(self):
        return max(0.08, 0.8 - (self.level - 1) * 0.07)

    def _draw_kind(self):
        # «Мешок из 7»: каждая фигура выпадает ровно раз за цикл.
        if not self.bag:
            self.bag = list(SHAPES)
            self.rng.shuffle(self.bag)
        return self.bag.pop()

    def spawn(self):
        self.piece = Piece(self.next_kind)
        self.next_kind = self._draw_kind()
        if not self.fits(self.piece.blocks()):
            self.over = True

    def fits(self, blocks):
        for x, y in blocks:
            if x < 0 or x >= WIDTH or y >= HEIGHT:
                return False
            if y >= 0 and self.board[y][x] is not None:
                return False
        return True

    def move(self, dx, dy):
        if self.fits(self.piece.blocks(dx, dy)):
            self.piece.x += dx
            self.piece.y += dy
            return True
        return False

    def rotate(self):
        if self.piece.kind == "O":
            return True
        size = 4 if self.piece.kind == "I" else 3
        new_cells = rotate(self.piece.cells, size)
        # Простые «кики»: пробуем сдвинуть фигуру, если поворот упёрся в стену.
        for kick in (0, -1, 1, -2, 2):
            if self.fits(self.piece.blocks(kick, 0, new_cells)):
                self.piece.cells = new_cells
                self.piece.x += kick
                return True
        return False

    def tick(self):
        """Один шаг гравитации. Возвращает True, если фигура зафиксировалась."""
        if self.move(0, 1):
            return False
        self.lock()
        return True

    def hard_drop(self):
        dropped = 0
        while self.move(0, 1):
            dropped += 1
        self.score += dropped * 2
        self.lock()

    def lock(self):
        for x, y in self.piece.blocks():
            if y < 0:
                self.over = True
                return
            self.board[y][x] = self.piece.kind
        self.clear_lines()
        self.spawn()

    def clear_lines(self):
        remaining = [row for row in self.board if None in row]
        cleared = HEIGHT - len(remaining)
        if cleared:
            self.board = [[None] * WIDTH for _ in range(cleared)] + remaining
            self.lines += cleared
            self.score += LINE_SCORES[cleared] * self.level

    def ghost_y(self):
        dy = 0
        while self.fits(self.piece.blocks(0, dy + 1)):
            dy += 1
        return dy


def draw(scr, game, paused):
    scr.erase()
    ox, oy = 2, 1
    # Рамка стакана
    for y in range(HEIGHT):
        scr.addstr(oy + y, ox, "|")
        scr.addstr(oy + y, ox + 1 + WIDTH * 2, "|")
    scr.addstr(oy + HEIGHT, ox, "+" + "--" * WIDTH + "+")

    def cell(x, y, kind, ch="[]"):
        if 0 <= y < HEIGHT:
            scr.addstr(oy + y, ox + 1 + x * 2, ch, curses.color_pair(COLORS[kind]))

    for y, row in enumerate(game.board):
        for x, kind in enumerate(row):
            if kind:
                cell(x, y, kind)

    if not game.over:
        g = game.ghost_y()
        for x, y in game.piece.blocks(0, g):
            cell(x, y, game.piece.kind, "::")
        for x, y in game.piece.blocks():
            cell(x, y, game.piece.kind)

    # Панель справа
    px = ox + WIDTH * 2 + 5
    scr.addstr(oy, px, f"Счёт:   {game.score}")
    scr.addstr(oy + 1, px, f"Линии:  {game.lines}")
    scr.addstr(oy + 2, px, f"Уровень: {game.level}")
    scr.addstr(oy + 4, px, "Следующая:")
    for cx, cy in SHAPES[game.next_kind]:
        scr.addstr(oy + 5 + cy, px + cx * 2, "[]", curses.color_pair(COLORS[game.next_kind]))
    scr.addstr(oy + 9, px, "← → ↑ ↓  Space  P  Q")
    if paused:
        scr.addstr(oy + HEIGHT // 2, ox + 6, " ПАУЗА ", curses.A_REVERSE)
    if game.over:
        scr.addstr(oy + HEIGHT // 2, ox + 3, " GAME OVER ", curses.A_REVERSE)
        scr.addstr(oy + HEIGHT // 2 + 1, ox + 2, " R — заново ", curses.A_REVERSE)
    scr.refresh()


def main(scr):
    curses.curs_set(0)
    scr.nodelay(True)
    curses.start_color()
    curses.use_default_colors()
    palette = [curses.COLOR_CYAN, curses.COLOR_YELLOW, curses.COLOR_MAGENTA,
               curses.COLOR_GREEN, curses.COLOR_RED, curses.COLOR_BLUE, curses.COLOR_WHITE]
    for i, color in enumerate(palette, start=1):
        curses.init_pair(i, color, -1)

    game = Game()
    paused = False
    last_fall = time.monotonic()

    while True:
        key = scr.getch()
        if key in (ord("q"), ord("Q")):
            break
        if game.over:
            if key in (ord("r"), ord("R")):
                game, paused = Game(), False
        elif key in (ord("p"), ord("P")):
            paused = not paused
        elif not paused:
            if key == curses.KEY_LEFT:
                game.move(-1, 0)
            elif key == curses.KEY_RIGHT:
                game.move(1, 0)
            elif key == curses.KEY_UP:
                game.rotate()
            elif key == curses.KEY_DOWN:
                if game.move(0, 1):
                    game.score += 1
                last_fall = time.monotonic()
            elif key == ord(" "):
                game.hard_drop()
                last_fall = time.monotonic()

        now = time.monotonic()
        if not paused and not game.over and now - last_fall >= game.fall_delay:
            game.tick()
            last_fall = now

        draw(scr, game, paused)
        time.sleep(0.016)


if __name__ == "__main__":
    curses.wrapper(main)
