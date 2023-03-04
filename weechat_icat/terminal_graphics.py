from __future__ import annotations

import os
from base64 import standard_b64encode
from dataclasses import dataclass
from random import randint
from typing import Dict, Union

import weechat

from weechat_icat.image import load_image_data
from weechat_icat.terminal_graphics_diacritics import rowcolumn_diacritics_chars


@dataclass
class ImagePlacement:
    path: str
    image_id: int
    columns: int
    rows: int


def get_random_image_id():
    image_id_upper = randint(0, 255)
    image_id_lower = randint(0, 255)
    return (image_id_upper << 24) + image_id_lower


def serialize_gr_command(control_data: Dict[str, Union[str, int]], payload: bytes):
    tmux = weechat.string_eval_expression("${env:TMUX}", {}, {}, {})
    esc = b"\033\033" if tmux else b"\033"
    control_data_str = ",".join(f"{k}={v}" for k, v in control_data.items())
    ans = [
        b"\033Ptmux;" if tmux else b"",
        esc + b"_G",
        control_data_str.encode("ascii"),
        b";" + payload if payload else b"",
        esc + b"\\",
        b"\033\\" if tmux else b"",
    ]
    return b"".join(ans)


def write_chunked(control_data: Dict[str, Union[str, int]], data: bytes):
    with open(os.ctermid(), "wb") as tty:
        data_base64 = standard_b64encode(data)
        while data_base64:
            chunk, data_base64 = data_base64[:4096], data_base64[4096:]
            m = 1 if data_base64 else 0
            tty.write(serialize_gr_command({**control_data, "m": m}, chunk))
            tty.flush()
            control_data.clear()


def get_cell_character(
    image_id: int,
    x: int,
    y: int,
    include_color: bool = False,
):
    image_id_upper = image_id >> 24
    image_id_lower = image_id & 0xFF
    color = weechat.color(str(image_id_lower)) if include_color else ""
    x_char = rowcolumn_diacritics_chars[x]
    y_char = rowcolumn_diacritics_chars[y]
    id_char = rowcolumn_diacritics_chars[image_id_upper]
    return f"{color}\U0010eeee{x_char}{y_char}{id_char}"


def create_image_placement(image_path: str, columns: int, rows: int):
    image_id = get_random_image_id()
    return ImagePlacement(image_path, image_id, columns, rows)


def send_image_to_terminal(image_placement: ImagePlacement):
    control_data = {
        "a": "T",
        "q": 2,
        "f": 100,
        "U": 1,
        "c": image_placement.columns,
        "r": image_placement.rows,
        "i": image_placement.image_id,
    }
    image_data = load_image_data(image_placement.path)
    write_chunked(control_data, image_data)


def display_image(buffer: str, image_placement: ImagePlacement):
    for x in range(image_placement.rows):
        chars = [
            get_cell_character(image_placement.image_id, x, y, include_color=y == 0)
            for y in range(image_placement.columns)
        ]
        weechat.prnt(buffer, "".join(chars))
