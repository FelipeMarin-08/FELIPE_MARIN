import json
import os
import urllib.request

from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw


USERNAME = os.getenv(
    "GITHUB_USERNAME",
    "FelipeMarin-08",
)

TOKEN = os.getenv(
    "GITHUB_TOKEN",
    "",
)

OUTPUT = Path(
    os.getenv(
        "OUTPUT_FILE",
        "dist/github-contribution-snake-grow.gif",
    )
)


# =========================================================
# VISUAL
# =========================================================

# GitHub Dark
BACKGROUND = "#161b22"

GRID_EMPTY = "#30363d"
GRID_BORDER = "#484f58"

# Contribuições
FOOD = "#ff0000"
FOOD_BORDER = "#ff3333"

# Cobra
SNAKE = "#ffffff"
SNAKE_HEAD = "#ffffff"


# =========================================================
# GRID
# =========================================================

CELL = 11
GAP = 3

# Margem maior na esquerda para mostrar
# a posição inicial da cobra
MARGIN_X = 70
MARGIN_Y = 20

WEEKS = 53
DAYS = 7

FRAME_DURATION = 70


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
            "User-Agent": (
                "FelipeMarin-Contribution-Snake"
            ),
        },
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:

        payload = json.load(response)

    if "errors" in payload:
        raise RuntimeError(
            payload["errors"]
        )

    weeks = (
        payload["data"]["user"]
        ["contributionsCollection"]
        ["contributionCalendar"]
        ["weeks"]
    )

    weeks = weeks[-WEEKS:]

    contribution_cells = {}

    offset = WEEKS - len(weeks)

    for x, week in enumerate(
        weeks,
        start=offset,
    ):

        for day in week[
            "contributionDays"
        ]:

            count = int(
                day["contributionCount"]
            )

            if count > 0:

                contribution_cells[
                    (
                        x,
                        int(day["weekday"]),
                    )
                ] = count

    return contribution_cells


# =========================================================
# DESENHO
# =========================================================

def cell_position(cell):

    x, y = cell

    px = (
        MARGIN_X
        + x * (CELL + GAP)
    )

    py = (
        MARGIN_Y
        + y * (CELL + GAP)
    )

    return px, py


def draw_cell(
    draw,
    cell,
    fill,
    outline=None,
    radius=2,
    inset=0,
):

    x, y = cell_position(cell)

    draw.rounded_rectangle(
        [
            x + inset,
            y + inset,
            x + CELL - 1 - inset,
            y + CELL - 1 - inset,
        ],
        radius=max(
            1,
            radius - inset,
        ),
        fill=fill,
        outline=outline,
    )


# =========================================================
# PATHFINDING
# =========================================================

# A ordem muda a cada alvo.
# Isso evita que todos os trajetos tenham
# exatamente o mesmo formato.
DIRECTION_ORDERS = [

    [
        (1, 0),
        (0, -1),
        (0, 1),
        (-1, 0),
    ],

    [
        (0, 1),
        (1, 0),
        (-1, 0),
        (0, -1),
    ],

    [
        (-1, 0),
        (0, 1),
        (0, -1),
        (1, 0),
    ],

    [
        (0, -1),
        (-1, 0),
        (1, 0),
        (0, 1),
    ],
]


def is_valid_position(cell):

    x, y = cell

    # Permite a coluna -1 porque
    # é a garagem da cobra.
    return (
        -1 <= x < WEEKS
        and
        0 <= y < DAYS
    )


def reconstruct_path(
    parents,
    target,
):

    path = []

    current = target

    while current is not None:

        path.append(current)

        current = parents[
            current
        ]

    path.reverse()

    return path


def find_nearest_food_path(
    start,
    foods,
    blocked,
    direction_index,
):

    if not foods:
        return None

    directions = (
        DIRECTION_ORDERS[
            direction_index
            % len(DIRECTION_ORDERS)
        ]
    )

    queue = deque(
        [start]
    )

    parents = {
        start: None
    }

    blocked = set(
        blocked
    )

    blocked.discard(
        start
    )

    while queue:

        current = queue.popleft()

        if (
            current in foods
            and
            current != start
        ):

            return reconstruct_path(
                parents,
                current,
            )

        for dx, dy in directions:

            next_cell = (
                current[0] + dx,
                current[1] + dy,
            )

            if not is_valid_position(
                next_cell
            ):
                continue

            if (
                next_cell in parents
            ):
                continue

            if (
                next_cell in blocked
            ):
                continue

            parents[
                next_cell
            ] = current

            queue.append(
                next_cell
            )

    return None


def find_path_to_target(
    start,
    target,
    blocked,
    direction_index,
):

    directions = (
        DIRECTION_ORDERS[
            direction_index
            % len(DIRECTION_ORDERS)
        ]
    )

    queue = deque(
        [start]
    )

    parents = {
        start: None
    }

    blocked = set(
        blocked
    )

    blocked.discard(
        start
    )

    # O destino sempre precisa
    # poder ser alcançado.
    blocked.discard(
        target
    )

    while queue:

        current = queue.popleft()

        if current == target:

            return reconstruct_path(
                parents,
                current,
            )

        for dx, dy in directions:

            next_cell = (
                current[0] + dx,
                current[1] + dy,
            )

            if not is_valid_position(
                next_cell
            ):
                continue

            if (
                next_cell in parents
            ):
                continue

            if (
                next_cell in blocked
            ):
                continue

            parents[
                next_cell
            ] = current

            queue.append(
                next_cell
            )

    return None


# =========================================================
# FRAME
# =========================================================

def create_frame(
    contributions,
    eaten,
    snake,
):

    width = (
        MARGIN_X
        + WEEKS * CELL
        + (WEEKS - 1) * GAP
        + 25
    )

    height = (
        MARGIN_Y * 2
        + DAYS * CELL
        + (DAYS - 1) * GAP
    )

    image = Image.new(
        "RGB",
        (
            width,
            height,
        ),
        BACKGROUND,
    )

    draw = ImageDraw.Draw(
        image
    )

    # =====================================
    # GRID CINZA
    # =====================================

    for y in range(
        DAYS
    ):

        for x in range(
            WEEKS
        ):

            draw_cell(
                draw,
                (
                    x,
                    y,
                ),
                GRID_EMPTY,
                outline=GRID_BORDER,
                radius=2,
            )

    # =====================================
    # CONTRIBUIÇÕES
    # =====================================

    for cell in contributions:

        if cell in eaten:
            continue

        # Quadrado vermelho ocupando
        # a célula inteira.
        draw_cell(
            draw,
            cell,
            FOOD,
            outline=FOOD_BORDER,
            radius=2,
        )

    # =====================================
    # COBRA
    # =====================================

    snake_list = list(
        snake
    )

    # Corpo
    for segment in snake_list[:-1]:

        sx, sy = segment

        # Permite mostrar a cobra
        # até quatro posições antes
        # do grid.
        if (
            -4 <= sx < WEEKS
            and
            0 <= sy < DAYS
        ):

            draw_cell(
                draw,
                segment,
                SNAKE,
                radius=3,
                inset=1,
            )

    # Cabeça
    head = snake_list[-1]

    hx, hy = head

    if (
        -4 <= hx < WEEKS
        and
        0 <= hy < DAYS
    ):

        draw_cell(
            draw,
            head,
            SNAKE_HEAD,
            radius=4,
        )

    return image


# =========================================================
# MOVIMENTO
# =========================================================

def move_snake(
    snake,
    next_head,
    grow,
):

    snake.append(
        next_head
    )

    if not grow:

        snake.popleft()


# =========================================================
# ANIMAÇÃO
# =========================================================

def generate_animation(
    contributions,
):

    snake = deque(
        INITIAL_BODY
    )

    eaten = set()

    remaining = set(
        contributions.keys()
    )

    frames = []

    # Frame inicial
    frames.append(
        create_frame(
            contributions,
            eaten,
            snake,
        )
    )

    route_number = 0

    # =====================================================
    # PROCURA AS CONTRIBUIÇÕES
    # =====================================================

    while remaining:

        head = snake[-1]

        # Evita atravessar o próprio corpo
        blocked = set(
            snake
        )

        blocked.discard(
            head
        )

        path = find_nearest_food_path(
            head,
            remaining,
            blocked,
            route_number,
        )

        # Fallback:
        # caso a própria cobra bloqueie
        # completamente a rota.
        if path is None:

            path = find_nearest_food_path(
                head,
                remaining,
                set(),
                route_number,
            )

        if path is None:

            raise RuntimeError(
                "Não foi possível encontrar "
                "caminho até uma contribuição."
            )

        # Percorre somente o caminho
        # necessário até a contribuição.
        for next_head in path[1:]:

            grow = (
                next_head
                in remaining
            )

            move_snake(
                snake,
                next_head,
                grow,
            )

            if grow:

                remaining.remove(
                    next_head
                )

                eaten.add(
                    next_head
                )

            frames.append(
                create_frame(
                    contributions,
                    eaten,
                    snake,
                )
            )

        route_number += 1

    # =====================================================
    # VOLTA PARA O PONTO INICIAL
    # =====================================================

    head = snake[-1]

    blocked = set(
        snake
    )

    blocked.discard(
        head
    )

    return_path = (
        find_path_to_target(
            head,
            START_HEAD,
            blocked,
            route_number,
        )
    )

    # Caso o corpo esteja bloqueando
    # a garagem, usamos rota livre.
    if return_path is None:

        return_path = (
            find_path_to_target(
                head,
                START_HEAD,
                set(),
                route_number,
            )
        )

    if return_path is None:

        raise RuntimeError(
            "Não foi possível retornar "
            "ao ponto inicial."
        )

    for next_head in (
        return_path[1:]
    ):

        move_snake(
            snake,
            next_head,
            grow=False,
        )

        frames.append(
            create_frame(
                contributions,
                eaten,
                snake,
            )
        )

    # =====================================================
    # PAUSAS
    # =====================================================

    if frames:

        frames = (
            [frames[0]] * 12
            + frames
            + [frames[-1]] * 20
        )

    # =====================================================
    # SALVA GIF
    # =====================================================

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION,
        loop=0,
        optimize=True,
        disposal=2,
    )

    print(
        f"Snake generated: "
        f"{OUTPUT}"
    )

    print(
        f"Contribution cells: "
        f"{len(contributions)}"
    )

    print(
        f"Eaten cells: "
        f"{len(eaten)}"
    )

    print(
        f"Final snake length: "
        f"{len(snake)}"
    )

    print(
        "Snake returned to start: "
        f"{snake[-1] == START_HEAD}"
    )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    if not TOKEN:

        raise RuntimeError(
            "GITHUB_TOKEN "
            "não encontrado."
        )

    contributions = (
        fetch_contributions()
    )

    generate_animation(
        contributions
    )
