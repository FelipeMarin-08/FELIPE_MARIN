import json
import os
import random
import urllib.request

from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# =========================================================
# CONFIGURAÇÃO
# =========================================================

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
CONTRIBUTION_RED = "#ff0000"

# Cobra
SNAKE = "#ffffff"
SNAKE_HEAD = "#ffffff"

# Barra de progresso
BAR_BACKGROUND = "#21262d"
BAR_BORDER = "#484f58"
BAR_FILL = "#ff0000"
TEXT_COLOR = "#c9d1d9"


# =========================================================
# TAMANHOS
# =========================================================

CELL = 11
GAP = 3

MARGIN_X = 70
MARGIN_Y = 20

WEEKS = 53
DAYS = 7

FRAME_DURATION = 65

BAR_HEIGHT = 11
BAR_MARGIN_TOP = 18
TEXT_MARGIN_TOP = 8
BOTTOM_PADDING = 22


# =========================================================
# CONTRIBUIÇÕES SIMULADAS
# =========================================================

# Adiciona mais quadrados vermelhos para deixar
# o mapa visualmente mais preenchido.
EXTRA_CONTRIBUTION_RATIO = 0.65
EXTRA_CONTRIBUTION_MIN = 30
EXTRA_CONTRIBUTION_MAX = 70


# =========================================================
# POSIÇÃO INICIAL DA COBRA
# =========================================================

START_Y = DAYS // 2

START_HEAD = (
    -1,
    START_Y,
)

INITIAL_BODY = [
    (-4, START_Y),
    (-3, START_Y),
    (-2, START_Y),
    (-1, START_Y),
]


# =========================================================
# CORES
# =========================================================

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")

    return tuple(
        int(hex_color[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(
        *rgb
    )


def blend_hex(
    background,
    foreground,
    alpha,
):
    br, bg, bb = hex_to_rgb(
        background
    )

    fr, fg, fb = hex_to_rgb(
        foreground
    )

    red = round(
        br * (1 - alpha)
        + fr * alpha
    )

    green = round(
        bg * (1 - alpha)
        + fg * alpha
    )

    blue = round(
        bb * (1 - alpha)
        + fb * alpha
    )

    return rgb_to_hex(
        (
            red,
            green,
            blue,
        )
    )


# =========================================================
# API DO GITHUB
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
            "Authorization": (
                f"Bearer {TOKEN}"
            ),
            "Content-Type": (
                "application/json"
            ),
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

        payload = json.load(
            response
        )

    if "errors" in payload:

        raise RuntimeError(
            payload["errors"]
        )

    weeks = (
        payload["data"]
        ["user"]
        ["contributionsCollection"]
        ["contributionCalendar"]
        ["weeks"]
    )

    weeks = weeks[
        -WEEKS:
    ]

    contributions = {}

    offset = (
        WEEKS
        - len(weeks)
    )

    for x, week in enumerate(
        weeks,
        start=offset,
    ):

        for day in week[
            "contributionDays"
        ]:

            count = int(
                day[
                    "contributionCount"
                ]
            )

            if count > 0:

                contributions[
                    (
                        x,
                        int(
                            day[
                                "weekday"
                            ]
                        ),
                    )
                ] = count

    return contributions


# =========================================================
# CONTRIBUIÇÕES EXTRAS
# =========================================================

def augment_contributions(
    real_contributions,
):

    # Seed fixa:
    # as posições extras não ficam
    # mudando toda vez que o Actions roda.
    rng = random.Random(
        f"{USERNAME}-github-snake-v3"
    )

    contributions = dict(
        real_contributions
    )

    simulated = set()

    occupied = set(
        contributions.keys()
    )

    real_count = len(
        real_contributions
    )

    target_extra = int(
        real_count
        * EXTRA_CONTRIBUTION_RATIO
    )

    target_extra = max(
        target_extra,
        EXTRA_CONTRIBUTION_MIN,
    )

    target_extra = min(
        target_extra,
        EXTRA_CONTRIBUTION_MAX,
    )

    available_count = (
        WEEKS * DAYS
        - len(occupied)
    )

    target_extra = min(
        target_extra,
        available_count,
    )

    # =====================================================
    # PRIMEIRO COLOCA CONTRIBUIÇÕES
    # PRÓXIMAS DAS CONTRIBUIÇÕES REAIS
    # =====================================================

    candidates = []

    if occupied:

        for x, y in list(
            occupied
        ):

            for dx in (
                -3,
                -2,
                -1,
                0,
                1,
                2,
                3,
            ):

                for dy in (
                    -2,
                    -1,
                    0,
                    1,
                    2,
                ):

                    if (
                        dx == 0
                        and dy == 0
                    ):
                        continue

                    nx = x + dx
                    ny = y + dy

                    if not (
                        0 <= nx < WEEKS
                        and
                        0 <= ny < DAYS
                    ):
                        continue

                    cell = (
                        nx,
                        ny,
                    )

                    if (
                        cell
                        not in occupied
                    ):

                        candidates.append(
                            cell
                        )

    # Remove duplicados
    candidates = list(
        dict.fromkeys(
            candidates
        )
    )

    rng.shuffle(
        candidates
    )

    # =====================================================
    # CRIA CONTRIBUIÇÕES FRACAS
    # =====================================================

    for cell in candidates:

        if (
            len(simulated)
            >= target_extra
        ):
            break

        if cell in occupied:
            continue

        # A maioria recebe valor baixo
        # para ficar mais transparente.
        fake_count = rng.choice(
            [
                1,
                1,
                1,
                1,
                1,
                2,
                2,
                2,
                3,
                3,
                4,
            ]
        )

        contributions[
            cell
        ] = fake_count

        simulated.add(
            cell
        )

        occupied.add(
            cell
        )

    # =====================================================
    # SE AINDA FALTAR, ESPALHA PELO GRID
    # =====================================================

    if (
        len(simulated)
        < target_extra
    ):

        available = [
            (
                x,
                y,
            )
            for x in range(
                WEEKS
            )
            for y in range(
                DAYS
            )
            if (
                x,
                y,
            )
            not in occupied
        ]

        rng.shuffle(
            available
        )

        needed = (
            target_extra
            - len(simulated)
        )

        for cell in available[
            :needed
        ]:

            fake_count = rng.choice(
                [
                    1,
                    1,
                    1,
                    2,
                    2,
                    3,
                ]
            )

            contributions[
                cell
            ] = fake_count

            simulated.add(
                cell
            )

            occupied.add(
                cell
            )

    return (
        contributions,
        simulated,
    )


# =========================================================
# INTENSIDADE DAS CONTRIBUIÇÕES
# =========================================================

def build_contribution_levels(
    contributions,
    simulated,
):

    real_values = sorted(
        count
        for cell, count
        in contributions.items()
        if cell not in simulated
    )

    if not real_values:

        real_values = sorted(
            contributions.values()
        )

    if not real_values:

        return (
            1,
            2,
            3,
        )

    def percentile(
        percentage,
    ):

        index = int(
            (
                len(real_values)
                - 1
            )
            * percentage
        )

        return real_values[
            index
        ]

    return (
        percentile(0.25),
        percentile(0.50),
        percentile(0.75),
    )


def contribution_fill_color(
    count,
    levels,
    is_simulated=False,
):

    # =====================================================
    # CONTRIBUIÇÕES SIMULADAS
    # =====================================================

    if is_simulated:

        if count <= 1:
            alpha = 0.16

        elif count == 2:
            alpha = 0.24

        elif count == 3:
            alpha = 0.32

        else:
            alpha = 0.40

    # =====================================================
    # CONTRIBUIÇÕES REAIS
    # =====================================================

    else:

        q1, q2, q3 = levels

        if count <= q1:
            alpha = 0.35

        elif count <= q2:
            alpha = 0.55

        elif count <= q3:
            alpha = 0.75

        else:
            alpha = 1.00

    # Simula transparência misturando
    # o vermelho com a cor da célula vazia.
    return blend_hex(
        GRID_EMPTY,
        CONTRIBUTION_RED,
        alpha,
    )


# =========================================================
# DIMENSÕES
# =========================================================

def grid_width():

    return (
        WEEKS * CELL
        + (WEEKS - 1) * GAP
    )


def grid_height():

    return (
        DAYS * CELL
        + (DAYS - 1) * GAP
    )


def canvas_size():

    width = (
        MARGIN_X
        + grid_width()
        + 25
    )

    height = (
        MARGIN_Y
        + grid_height()
        + BAR_MARGIN_TOP
        + BAR_HEIGHT
        + TEXT_MARGIN_TOP
        + 18
        + BOTTOM_PADDING
    )

    return (
        width,
        height,
    )


# =========================================================
# POSIÇÃO DAS CÉLULAS
# =========================================================

def cell_position(
    cell,
):

    x, y = cell

    px = (
        MARGIN_X
        + x
        * (
            CELL
            + GAP
        )
    )

    py = (
        MARGIN_Y
        + y
        * (
            CELL
            + GAP
        )
    )

    return (
        px,
        py,
    )


def draw_cell(
    draw,
    cell,
    fill,
    outline=None,
    radius=2,
    inset=0,
):

    x, y = cell_position(
        cell
    )

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
# BARRA DE PROGRESSO
# =========================================================

def draw_progress_bar(
    draw,
    eaten_count,
    total_count,
):

    bar_x = MARGIN_X

    bar_y = (
        MARGIN_Y
        + grid_height()
        + BAR_MARGIN_TOP
    )

    bar_width = grid_width()

    if total_count == 0:

        progress = 1.0

    else:

        progress = (
            eaten_count
            / total_count
        )

    progress = max(
        0.0,
        min(
            progress,
            1.0,
        ),
    )

    fill_width = int(
        bar_width
        * progress
    )

    # Fundo
    draw.rounded_rectangle(
        [
            bar_x,
            bar_y,
            bar_x + bar_width,
            bar_y + BAR_HEIGHT,
        ],
        radius=4,
        fill=BAR_BACKGROUND,
        outline=BAR_BORDER,
    )

    # Parte preenchida
    if fill_width > 0:

        draw.rounded_rectangle(
            [
                bar_x,
                bar_y,
                bar_x + fill_width,
                bar_y + BAR_HEIGHT,
            ],
            radius=4,
            fill=BAR_FILL,
        )

    percentage = int(
        progress
        * 100
    )

    text = (
        f"Contributions collected: "
        f"{eaten_count}/{total_count} "
        f"• {percentage}%"
    )

    font = ImageFont.load_default()

    draw.text(
        (
            bar_x,
            bar_y
            + BAR_HEIGHT
            + TEXT_MARGIN_TOP,
        ),
        text,
        fill=TEXT_COLOR,
        font=font,
    )


# =========================================================
# PATHFINDING
# =========================================================

# A ordem das direções muda para
# deixar os trajetos menos repetitivos.
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


def is_valid_position(
    cell,
    minimum_x=-1,
):

    x, y = cell

    return (
        minimum_x
        <= x
        < WEEKS
        and
        0
        <= y
        < DAYS
    )


def reconstruct_path(
    parents,
    target,
):

    path = []

    current = target

    while (
        current
        is not None
    ):

        path.append(
            current
        )

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
            % len(
                DIRECTION_ORDERS
            )
        ]
    )

    queue = deque(
        [
            start,
        ]
    )

    parents = {
        start: None,
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
                next_cell
                in parents
            ):
                continue

            if (
                next_cell
                in blocked
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
    minimum_x=-1,
):

    if start == target:

        return [
            start,
        ]

    directions = (
        DIRECTION_ORDERS[
            direction_index
            % len(
                DIRECTION_ORDERS
            )
        ]
    )

    queue = deque(
        [
            start,
        ]
    )

    parents = {
        start: None,
    }

    blocked = set(
        blocked
    )

    blocked.discard(
        start
    )

    blocked.discard(
        target
    )

    while queue:

        current = queue.popleft()

        if (
            current
            == target
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
                next_cell,
                minimum_x=minimum_x,
            ):
                continue

            if (
                next_cell
                in parents
            ):
                continue

            if (
                next_cell
                in blocked
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
    simulated,
    eaten,
    snake,
    levels,
):

    width, height = canvas_size()

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

    # =====================================================
    # GRID CINZA
    # =====================================================

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

    # =====================================================
    # CONTRIBUIÇÕES
    # =====================================================

    for (
        cell,
        count,
    ) in contributions.items():

        if cell in eaten:
            continue

        color = contribution_fill_color(
            count,
            levels,
            is_simulated=(
                cell in simulated
            ),
        )

        # Preenche o quadrado inteiro,
        # igual ao gráfico do GitHub.
        draw_cell(
            draw,
            cell,
            color,
            outline=color,
            radius=2,
        )

    # =====================================================
    # COBRA
    # =====================================================

    snake_list = list(
        snake
    )

    # Corpo
    for segment in snake_list[
        :-1
    ]:

        sx, sy = segment

        if (
            -4
            <= sx
            < WEEKS
            and
            0
            <= sy
            < DAYS
        ):

            draw_cell(
                draw,
                segment,
                SNAKE,
                radius=3,
                inset=1,
            )

    # Cabeça
    if snake_list:

        head = snake_list[
            -1
        ]

        hx, hy = head

        if (
            -4
            <= hx
            < WEEKS
            and
            0
            <= hy
            < DAYS
        ):

            draw_cell(
                draw,
                head,
                SNAKE_HEAD,
                radius=4,
            )

    # =====================================================
    # PROGRESSO
    # =====================================================

    draw_progress_bar(
        draw,
        len(eaten),
        len(contributions),
    )

    return image


# =========================================================
# MOVIMENTO DA COBRA
# =========================================================

def move_snake(
    snake,
    next_head,
    grow=False,
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
    simulated,
):

    snake = deque(
        INITIAL_BODY
    )

    eaten = set()

    eaten_order = []

    remaining = set(
        contributions.keys()
    )

    levels = (
        build_contribution_levels(
            contributions,
            simulated,
        )
    )

    frames = []

    # =====================================================
    # FRAME INICIAL
    # =====================================================

    frames.append(
        create_frame(
            contributions,
            simulated,
            eaten,
            snake,
            levels,
        )
    )

    route_number = 0

    # =====================================================
    # BUSCA AS CONTRIBUIÇÕES
    # =====================================================

    while remaining:

        head = snake[
            -1
        ]

        blocked = set(
            snake
        )

        blocked.discard(
            head
        )

        path = (
            find_nearest_food_path(
                head,
                remaining,
                blocked,
                route_number,
            )
        )

        # Se o corpo bloquear todo o caminho,
        # permite encontrar uma rota alternativa.
        if path is None:

            path = (
                find_nearest_food_path(
                    head,
                    remaining,
                    set(),
                    route_number,
                )
            )

        if path is None:

            raise RuntimeError(
                "Não foi possível encontrar "
                "caminho até uma contribuição."
            )

        # =================================================
        # PERCORRE O CAMINHO
        # =================================================

        for next_head in path[
            1:
        ]:

            grow = (
                next_head
                in remaining
            )

            move_snake(
                snake,
                next_head,
                grow=grow,
            )

            if grow:

                remaining.remove(
                    next_head
                )

                eaten.add(
                    next_head
                )

                eaten_order.append(
                    next_head
                )

            frames.append(
                create_frame(
                    contributions,
                    simulated,
                    eaten,
                    snake,
                    levels,
                )
            )

        route_number += 1

    # =====================================================
    # VOLTA PARA A ÁREA INICIAL
    # =====================================================

    head = snake[
        -1
    ]

    blocked = set(
        snake
    )

    blocked.discard(
        head
    )

    parking_target = (
        -4,
        START_Y,
    )

    return_path = (
        find_path_to_target(
            head,
            parking_target,
            blocked,
            route_number,
            minimum_x=-4,
        )
    )

    # Caso o próprio corpo impeça
    # completamente a rota.
    if return_path is None:

        return_path = (
            find_path_to_target(
                head,
                parking_target,
                set(),
                route_number,
                minimum_x=-4,
            )
        )

    if return_path is None:

        raise RuntimeError(
            "Não foi possível retornar "
            "para a posição inicial."
        )

    # =====================================================
    # CAMINHO DE VOLTA
    # =====================================================

    for next_head in return_path[
        1:
    ]:

        move_snake(
            snake,
            next_head,
            grow=False,
        )

        frames.append(
            create_frame(
                contributions,
                simulated,
                eaten,
                snake,
                levels,
            )
        )

    # =====================================================
    # ENCAIXA A COBRA EXATAMENTE
    # NA POSIÇÃO INICIAL
    # =====================================================

    parking_approach = [
        (-3, START_Y),
        (-2, START_Y),
        (-1, START_Y),
    ]

    for next_head in parking_approach:

        move_snake(
            snake,
            next_head,
            grow=False,
        )

        frames.append(
            create_frame(
                contributions,
                simulated,
                eaten,
                snake,
                levels,
            )
        )

    # =====================================================
    # RESET CONTÍNUO
    #
    # Cada contribuição reaparece ao mesmo
    # tempo que a cobra perde um segmento.
    #
    # Isso faz o último frame ficar igual
    # ao primeiro, criando um loop suave.
    # =====================================================

    reset_order = list(
        reversed(
            eaten_order
        )
    )

    for cell in reset_order:

        # Diminui a cobra de volta
        # ao tamanho inicial.
        if (
            len(snake)
            > len(
                INITIAL_BODY
            )
        ):

            snake.popleft()

        # Faz a contribuição reaparecer.
        eaten.discard(
            cell
        )

        frames.append(
            create_frame(
                contributions,
                simulated,
                eaten,
                snake,
                levels,
            )
        )

    # =====================================================
    # GARANTE ESTADO INICIAL
    # =====================================================

    snake = deque(
        INITIAL_BODY
    )

    eaten.clear()

    final_frame = (
        create_frame(
            contributions,
            simulated,
            eaten,
            snake,
            levels,
        )
    )

    frames.append(
        final_frame
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
        append_images=frames[
            1:
        ],
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
        f"Real contribution cells: "
        f"{len(contributions) - len(simulated)}"
    )

    print(
        f"Simulated contribution cells: "
        f"{len(simulated)}"
    )

    print(
        f"Total contribution cells: "
        f"{len(contributions)}"
    )

    print(
        f"Frames generated: "
        f"{len(frames)}"
    )

    print(
        "Loop final state: OK"
    )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    if not TOKEN:

        raise RuntimeError(
            "GITHUB_TOKEN não encontrado."
        )

    real_contributions = (
        fetch_contributions()
    )

    (
        contributions,
        simulated,
    ) = augment_contributions(
        real_contributions
    )

    generate_animation(
        contributions,
        simulated,
    )
