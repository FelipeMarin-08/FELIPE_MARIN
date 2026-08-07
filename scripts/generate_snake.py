import json
import os
import urllib.request

from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


USERNAME = os.getenv("GITHUB_USERNAME", "FelipeMarin-08")
TOKEN = os.getenv("GITHUB_TOKEN", "")

OUTPUT = Path(
    os.getenv(
        "OUTPUT_FILE",
        "dist/github-contribution-snake-grow.gif",
    )
)


# =========================================================
# VISUAL
# =========================================================

BACKGROUND = "#161b22"
GRID_EMPTY = "#30363d"
GRID_BORDER = "#484f58"

FOOD_BASE = "#ff0000"
FOOD_BORDER = "#ff4d4d"

SNAKE = "#ffffff"
SNAKE_HEAD = "#ffffff"

BAR_BG = "#0d1117"
BAR_BORDER = "#484f58"
BAR_FILL = "#ff0000"
TEXT_COLOR = "#c9d1d9"


# =========================================================
# GRID
# =========================================================

CELL = 11
GAP = 3

MARGIN_X = 70
MARGIN_Y = 20

WEEKS = 53
DAYS = 7

FRAME_DURATION = 65

BAR_HEIGHT = 12
BAR_MARGIN_TOP = 18
TEXT_MARGIN_TOP = 10
BOTTOM_PADDING = 20


# =========================================================
# POSIÇÃO INICIAL
# =========================================================

START_Y = DAYS // 2
START_HEAD = (-1, START_Y)

INITIAL_BODY = [
    (-4, START_Y),
    (-3, START_Y),
    (-2, START_Y),
    (-1, START_Y),
]


# =========================================================
# HELPERS DE COR
# =========================================================

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(
        int(hex_color[i:i+2], 16)
        for i in (0, 2, 4)
    )


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def blend_hex(background, foreground, alpha):
    br, bg, bb = hex_to_rgb(background)
    fr, fg, fb = hex_to_rgb(foreground)

    r = round(br * (1 - alpha) + fr * alpha)
    g = round(bg * (1 - alpha) + fg * alpha)
    b = round(bb * (1 - alpha) + fb * alpha)

    return rgb_to_hex((r, g, b))


def build_contribution_levels(contributions):
    values = sorted(
        count for count in contributions.values()
        if count > 0
    )

    if not values:
        return (1, 1, 1)

    def percentile(p):
        idx = int((len(values) - 1) * p)
        return values[idx]

    return (
        percentile(0.25),
        percentile(0.50),
        percentile(0.75),
    )


def contribution_fill_color(count, levels):
    q1, q2, q3 = levels

    if count <= q1:
        alpha = 0.35
    elif count <= q2:
        alpha = 0.55
    elif count <= q3:
        alpha = 0.78
    else:
        alpha = 1.00

    return blend_hex(BACKGROUND, FOOD_BASE, alpha)


# =========================================================
# API GITHUB
# =========================================================

def fetch_contributions():
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                weekday
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    body = json.dumps(
        {
            "query": query,
            "variables": {
                "login": USERNAME,
            },
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "FelipeMarin-Contribution-Snake",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    if "errors" in payload:
        raise RuntimeError(payload["errors"])

    weeks = (
        payload["data"]["user"]["contributionsCollection"]
        ["contributionCalendar"]["weeks"]
    )

    weeks = weeks[-WEEKS:]

    contribution_cells = {}

    offset = WEEKS - len(weeks)

    for x, week in enumerate(weeks, start=offset):
        for day in week["contributionDays"]:
            count = int(day["contributionCount"])

            if count > 0:
                contribution_cells[
                    (x, int(day["weekday"]))
                ] = count

    return contribution_cells


# =========================================================
# DESENHO
# =========================================================

def grid_width():
    return WEEKS * CELL + (WEEKS - 1) * GAP


def grid_height():
    return DAYS * CELL + (DAYS - 1) * GAP


def canvas_size():
    width = MARGIN_X + grid_width() + 25

    height = (
        MARGIN_Y
        + grid_height()
        + BAR_MARGIN_TOP
        + BAR_HEIGHT
        + TEXT_MARGIN_TOP
        + 18
        + BOTTOM_PADDING
    )

    return width, height


def cell_position(cell):
    x, y = cell

    px = MARGIN_X + x * (CELL + GAP)
    py = MARGIN_Y + y * (CELL + GAP)

    return px, py


def draw_cell(draw, cell, fill, outline=None, radius=2, inset=0):
    x, y = cell_position(cell)

    draw.rounded_rectangle(
        [
            x + inset,
            y + inset,
            x + CELL - 1 - inset,
            y + CELL - 1 - inset,
        ],
        radius=max(1, radius - inset),
        fill=fill,
        outline=outline,
    )


def draw_progress_bar(draw, eaten_count, total_count):
    bar_x = MARGIN_X
    bar_y = MARGIN_Y + grid_height() + BAR_MARGIN_TOP
    bar_w = grid_width()
    bar_h = BAR_HEIGHT

    progress = 1 if total_count == 0 else eaten_count / total_count
    fill_w = int(bar_w * progress)

    draw.rounded_rectangle(
        [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
        radius=4,
        fill=BAR_BG,
        outline=BAR_BORDER,
    )

    if fill_w > 0:
        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + fill_w, bar_y + bar_h],
            radius=4,
            fill=BAR_FILL,
        )

    text = f"Progress: {eaten_count}/{total_count} • {int(progress * 100)}%"

    font = ImageFont.load_default()
    text_y = bar_y + bar_h + TEXT_MARGIN_TOP

    draw.text(
        (bar_x, text_y),
        text,
        fill=TEXT_COLOR,
        font=font,
    )


# =========================================================
# PATHFINDING
# =========================================================

DIRECTION_ORDERS = [
    [(1, 0), (0, -1), (0, 1), (-1, 0)],
    [(0, 1), (1, 0), (-1, 0), (0, -1)],
    [(-1, 0), (0, 1), (0, -1), (1, 0)],
    [(0, -1), (-1, 0), (1, 0), (0, 1)],
]


def is_valid_position(cell):
    x, y = cell
    return -1 <= x < WEEKS and 0 <= y < DAYS


def reconstruct_path(parents, target):
    path = []
    current = target

    while current is not None:
        path.append(current)
        current = parents[current]

    path.reverse()
    return path


def bfs_path(start, targets, blocked, direction_index):
    directions = DIRECTION_ORDERS[
        direction_index % len(DIRECTION_ORDERS)
    ]

    queue = deque([start])
    parents = {start: None}

    blocked = set(blocked)
    blocked.discard(start)

    while queue:
        current = queue.popleft()

        if current in targets and current != start:
            return reconstruct_path(parents, current)

        for dx, dy in directions:
            nxt = (current[0] + dx, current[1] + dy)

            if not is_valid_position(nxt):
                continue

            if nxt in parents:
                continue

            if nxt in blocked:
                continue

            parents[nxt] = current
            queue.append(nxt)

    return None


def bfs_path_to_target(start, target, blocked, direction_index):
    return bfs_path(
        start,
        {target},
        blocked,
        direction_index,
    )


# =========================================================
# FRAME
# =========================================================

def create_frame(contributions, eaten, snake, levels):
    width, height = canvas_size()

    image = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(image)

    # Grid cinza
    for y in range(DAYS):
        for x in range(WEEKS):
            draw_cell(
                draw,
                (x, y),
                GRID_EMPTY,
                outline=GRID_BORDER,
                radius=2,
            )

    # Contribuições vermelhas com intensidades diferentes
    for cell, count in contributions.items():
        if cell in eaten:
            continue

        draw_cell(
            draw,
            cell,
            contribution_fill_color(count, levels),
            outline=FOOD_BORDER,
            radius=2,
        )

    # Corpo da cobra
    snake_list = list(snake)

    for segment in snake_list[:-1]:
        sx, sy = segment

        if -4 <= sx < WEEKS and 0 <= sy < DAYS:
            draw_cell(
                draw,
                segment,
                SNAKE,
                radius=3,
                inset=1,
            )

    # Cabeça
    hx, hy = snake_list[-1]

    if -4 <= hx < WEEKS and 0 <= hy < DAYS:
        draw_cell(
            draw,
            (hx, hy),
            SNAKE_HEAD,
            radius=4,
        )

    draw_progress_bar(draw, len(eaten), len(contributions))

    return image


# =========================================================
# MOVIMENTO
# =========================================================

def move_snake(snake, next_head, grow):
    snake.append(next_head)

    if not grow:
        snake.popleft()


# =========================================================
# ANIMAÇÃO
# =========================================================

def generate_animation(contributions):
    snake = deque(INITIAL_BODY)
    eaten = set()
    remaining = set(contributions.keys())
    levels = build_contribution_levels(contributions)

    frames = []

    # Pequena pausa inicial
    first_frame = create_frame(contributions, eaten, snake, levels)
    frames.extend([first_frame] * 4)

    route_number = 0

    # Come todas as contribuições
    while remaining:
        head = snake[-1]

        blocked = set(snake)
        blocked.discard(head)

        path = bfs_path(
            head,
            remaining,
            blocked,
            route_number,
        )

        if path is None:
            path = bfs_path(
                head,
                remaining,
                set(),
                route_number,
            )

        if path is None:
            raise RuntimeError(
                "Não foi possível encontrar caminho até uma contribuição."
            )

        for next_head in path[1:]:
            grow = next_head in remaining

            move_snake(snake, next_head, grow)

            if grow:
                remaining.remove(next_head)
                eaten.add(next_head)

            frames.append(
                create_frame(contributions, eaten, snake, levels)
            )

        route_number += 1

    # Volta ao ponto inicial com fluxo contínuo
    head = snake[-1]

    blocked = set(snake)
    blocked.discard(head)

    return_path = bfs_path_to_target(
        head,
        START_HEAD,
        blocked,
        route_number,
    )

    if return_path is None:
        return_path = bfs_path_to_target(
            head,
            START_HEAD,
            set(),
            route_number,
        )

    if return_path is None:
        raise RuntimeError(
            "Não foi possível retornar ao ponto inicial."
        )

    for next_head in return_path[1:]:
        move_snake(snake, next_head, grow=False)

        frames.append(
            create_frame(contributions, eaten, snake, levels)
        )

    # Não trava no final.
    # Em vez de congelar, só faz uma pausa bem curta
    # para o loop não parecer brusco.
    frames.extend([frames[-1]] * 2)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION,
        loop=0,
        optimize=True,
        disposal=2,
    )

    print(f"Snake generated: {OUTPUT}")
    print(f"Contribution cells: {len(contributions)}")
    print(f"Eaten cells: {len(eaten)}")
    print(f"Returned to start: {snake[-1] == START_HEAD}")


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN não encontrado.")

    contributions = fetch_contributions()
    generate_animation(contributions)
