import json
import os
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw


USERNAME = os.getenv("GITHUB_USERNAME", "FelipeMarin-08")
TOKEN = os.getenv("GITHUB_TOKEN", "")

OUTPUT = Path(
    os.getenv(
        "OUTPUT_FILE",
        "dist/github-contribution-snake-grow.gif",
    )
)

# Visual inspirado no GitHub Dark
BACKGROUND = "#161b22"
GRID_EMPTY = "#30363d"
GRID_BORDER = "#484f58"

FOOD = "#ff0000"
SNAKE = "#ffffff"

CELL = 11
GAP = 3

MARGIN_X = 24
MARGIN_Y = 20

WEEKS = 53
DAYS = 7

FRAME_DURATION = 70

INITIAL_SNAKE_LENGTH = 4


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


def cell_position(cell):
    x, y = cell

    px = MARGIN_X + x * (CELL + GAP)
    py = MARGIN_Y + y * (CELL + GAP)

    return px, py


def draw_grid_cell(
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
        radius=max(1, radius - inset),
        fill=fill,
        outline=outline,
    )


def generate_snake_path():
    path = []

    # Cobra começa fora do tabuleiro
    path.extend(
        [
            (-4, 0),
            (-3, 0),
            (-2, 0),
            (-1, 0),
        ]
    )

    # Percorre o gráfico em formato serpente
    for y in range(DAYS):

        if y % 2 == 0:
            xs = range(WEEKS)
        else:
            xs = range(WEEKS - 1, -1, -1)

        for x in xs:
            path.append((x, y))

    return path


def generate_animation(contributions):

    width = (
        MARGIN_X * 2
        + WEEKS * CELL
        + (WEEKS - 1) * GAP
    )

    height = (
        MARGIN_Y * 2
        + DAYS * CELL
        + (DAYS - 1) * GAP
    )

    path = generate_snake_path()

    eaten = set()

    snake_length = INITIAL_SNAKE_LENGTH

    frames = []

    for index, head in enumerate(path):

        # Quando a cobra come uma bolinha,
        # ela cresce de verdade.
        if (
            head in contributions
            and head not in eaten
        ):
            eaten.add(head)
            snake_length += 1

        image = Image.new(
            "RGB",
            (width, height),
            BACKGROUND,
        )

        draw = ImageDraw.Draw(image)

        # Desenha TODAS as caixinhas cinza
        for y in range(DAYS):

            for x in range(WEEKS):

                draw_grid_cell(
                    draw,
                    (x, y),
                    GRID_EMPTY,
                    outline=GRID_BORDER,
                    radius=2,
                )

        # Desenha as bolinhas vermelhas
        # somente enquanto não foram comidas
        for cell in contributions:

            if cell in eaten:
                continue

            x, y = cell_position(cell)

            padding = 2

            draw.ellipse(
                [
                    x + padding,
                    y + padding,
                    x + CELL - 1 - padding,
                    y + CELL - 1 - padding,
                ],
                fill=FOOD,
            )

        # Calcula corpo atual da cobra
        body_start = max(
            0,
            index - snake_length + 1,
        )

        body = path[
            body_start:index + 1
        ]

        # Corpo
        for segment in body[:-1]:

            sx, sy = segment

            if (
                0 <= sx < WEEKS
                and 0 <= sy < DAYS
            ):

                draw_grid_cell(
                    draw,
                    segment,
                    SNAKE,
                    radius=4,
                    inset=1,
                )

        # Cabeça
        hx, hy = head

        if (
            0 <= hx < WEEKS
            and 0 <= hy < DAYS
        ):

            draw_grid_cell(
                draw,
                head,
                SNAKE,
                radius=5,
            )

        frames.append(image)

    # Pausa no início
    if frames:

        frames = (
            [frames[0]] * 8
            + frames
            + [frames[-1]] * 18
        )

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
        f"Snake generated: {OUTPUT}"
    )

    print(
        f"Contribution cells: "
        f"{len(contributions)}"
    )


if __name__ == "__main__":

    if not TOKEN:
        raise RuntimeError(
            "GITHUB_TOKEN não encontrado."
        )

    contributions = fetch_contributions()

    generate_animation(contributions)
