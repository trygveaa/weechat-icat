from __future__ import annotations

import array
import fcntl
import os
import termios
from base64 import standard_b64encode
from dataclasses import dataclass
from random import randint
from typing import Dict, Optional, Union

import weechat

from weechat_icat.image import load_image_data
from weechat_icat.terminal_graphics_diacritics import rowcolumn_diacritics_chars


@dataclass
class TerminalSize:
    rows: int
    columns: int
    width: int
    height: int


@dataclass
class ImagePlacement:
    path: str
    image_id: int
    columns: int
    rows: int


def get_terminal_size():
    buf = array.array("H", [0, 0, 0, 0])
    fcntl.ioctl(1, termios.TIOCGWINSZ, buf)
    return TerminalSize(*buf)


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


def create_and_send_image_to_terminal(
    image_path: str, columns: Optional[int], rows: Optional[int]
):
    image_id = get_random_image_id()
    image_data = load_image_data(image_path)
    terminal_size = get_terminal_size()
    image_columns = image_data.width / terminal_size.width * terminal_size.columns
    image_rows = image_data.height / terminal_size.height * terminal_size.rows

    if not columns:
        rows_ = rows or 5
        columns_ = rows_ / image_rows * image_columns
    else:
        columns_ = columns
        rows_ = rows or columns_ / image_columns * image_rows

    image_placement = ImagePlacement(
        image_path, image_id, round(columns_), round(rows_)
    )
    send_image_to_terminal(image_placement, image_data.data)
    return image_placement


def send_image_to_terminal(
    image_placement: ImagePlacement, image_data: Optional[bytes] = None
):
    control_data = {
        "a": "T",
        "q": 2,
        "f": 100,
        "U": 1,
        "c": image_placement.columns,
        "r": image_placement.rows,
        "i": image_placement.image_id,
    }
    image_bytes = image_data or load_image_data(image_placement.path).data
    write_chunked(control_data, image_bytes)


def display_image(buffer: str, image_placement: ImagePlacement):
    for x in range(image_placement.rows):
        chars = [
            get_cell_character(image_placement.image_id, x, y, include_color=y == 0)
            for y in range(image_placement.columns)
        ]
        weechat.prnt(buffer, "".join(chars))
