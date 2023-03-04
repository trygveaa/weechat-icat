from __future__ import annotations

import os
from base64 import standard_b64encode
from random import randint
from typing import Dict, Union

import weechat

from weechat_icat.terminal_graphics_diacritics import rowcolumn_diacritics_chars


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
    x: int,
    y: int,
    image_id_upper: int,
    image_id_lower: int,
    include_color: bool = False,
):
    color = weechat.color(str(image_id_lower)) if include_color else ""
    x_char = rowcolumn_diacritics_chars[x]
    y_char = rowcolumn_diacritics_chars[y]
    id_char = rowcolumn_diacritics_chars[image_id_upper]
    return f"{color}\U0010eeee{x_char}{y_char}{id_char}"


def display_image(buffer: str, image_path: str, columns: int, rows: int):
    image_id_upper = randint(0, 255)
    image_id_lower = randint(0, 255)
    image_id = (image_id_upper << 24) + image_id_lower
    with open(image_path, "rb") as f:
        control_data = {
            "a": "T",
            "q": 2,
            "f": 100,
            "U": 1,
            "c": columns,
            "r": rows,
            "i": image_id,
        }
        write_chunked(control_data, f.read())
        for x in range(rows):
            chars = [
                get_cell_character(
                    x, y, image_id_upper, image_id_lower, include_color=y == 0
                )
                for y in range(columns)
            ]
            weechat.prnt(buffer, "".join(chars))
