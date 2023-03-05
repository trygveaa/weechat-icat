from __future__ import annotations

import array
import fcntl
import os
import pickle
import termios
from base64 import b64decode, b64encode
from collections import defaultdict
from dataclasses import dataclass
from io import StringIO
from random import randint
from typing import Callable, Dict, List, Optional, Union
from uuid import UUID, uuid4

import weechat

from weechat_icat.image import ImageData, load_image_data
from weechat_icat.log import print_error
from weechat_icat.terminal_graphics_diacritics import rowcolumn_diacritics_chars
from weechat_icat.util import get_callback_name

string_buffers: Dict[str, StringIO] = defaultdict(StringIO)


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


@dataclass
class ImageCreateData:
    path: str
    image_id: int
    columns: Optional[int]
    rows: Optional[int]
    terminal_size: TerminalSize
    callback: Callable[[str, ImagePlacement], None]
    callback_data: str
    uuid: UUID = uuid4()


@dataclass
class ImagesSendData:
    image_placements: List[ImagePlacement]
    callback: Callable[[str], None]
    callback_data: str
    uuid: UUID = uuid4()


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
        data_base64 = b64encode(data)
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


def create_and_send_image_to_terminal_bg(data_serialized: str) -> str:
    data: ImageCreateData = pickle.loads(b64decode(data_serialized))
    image_data = load_image_data(data.path)

    image_columns = (
        image_data.width / data.terminal_size.width * data.terminal_size.columns
    )
    image_rows = image_data.height / data.terminal_size.height * data.terminal_size.rows

    if not data.columns:
        rows = data.rows or 5
        columns = rows / image_rows * image_columns
    else:
        columns = data.columns
        rows = data.rows or columns / image_columns * image_rows

    image_placement = ImagePlacement(
        data.path, data.image_id, round(columns), round(rows)
    )
    send_image_to_terminal(image_placement, image_data)

    return b64encode(pickle.dumps(image_placement)).decode("ascii")


def create_and_send_image_to_terminal_bg_finished_cb(
    data_serialized: str, command: str, return_code: int, out_chunk: str, err_chunk: str
) -> int:
    data: ImageCreateData = pickle.loads(b64decode(data_serialized))
    out_key = f"{str(data.uuid)}_out"
    err_key = f"{str(data.uuid)}_err"
    string_buffers[out_key].write(out_chunk)
    string_buffers[err_key].write(err_chunk)

    if return_code == -1:
        return weechat.WEECHAT_RC_OK

    out = string_buffers[out_key].getvalue()
    err = string_buffers[err_key].getvalue()
    string_buffers[out_key].close()
    string_buffers[err_key].close()
    del string_buffers[out_key]
    del string_buffers[err_key]

    if return_code == weechat.WEECHAT_HOOK_PROCESS_ERROR or return_code > 0 or err:
        print_error(f"failed displaying image, return_code={return_code}, err='{err}'")
        return weechat.WEECHAT_RC_OK

    image_placement: ImagePlacement = pickle.loads(b64decode(out))
    data.callback(data.callback_data, image_placement)
    return weechat.WEECHAT_RC_OK


def create_and_send_image_to_terminal(
    image_path: str,
    columns: Optional[int],
    rows: Optional[int],
    callback: Callable[[str, ImagePlacement], None],
    callback_data: str,
):
    image_create_data = ImageCreateData(
        image_path,
        get_random_image_id(),
        columns,
        rows,
        get_terminal_size(),
        callback,
        callback_data,
    )
    data_serialized = b64encode(pickle.dumps(image_create_data)).decode("ascii")

    weechat.hook_process(
        "func:" + get_callback_name(create_and_send_image_to_terminal_bg),
        60000,
        get_callback_name(create_and_send_image_to_terminal_bg_finished_cb),
        data_serialized,
    )


def send_image_to_terminal(image_placement: ImagePlacement, image_data: ImageData):
    control_data = {
        "a": "T",
        "q": 2,
        "f": 100,
        "U": 1,
        "c": image_placement.columns,
        "r": image_placement.rows,
        "i": image_placement.image_id,
    }
    write_chunked(control_data, image_data.data)


def send_images_to_terminal_bg(data_serialized: str):
    data: ImagesSendData = pickle.loads(b64decode(data_serialized))
    for image_placement in data.image_placements:
        image_data = load_image_data(image_placement.path)
        send_image_to_terminal(image_placement, image_data)
    return ""


def send_images_to_terminal_bg_finished_cb(
    data_serialized: str, command: str, return_code: int, out_chunk: str, err_chunk: str
) -> int:
    data: ImagesSendData = pickle.loads(b64decode(data_serialized))
    err_key = f"{str(data.uuid)}_err"
    string_buffers[err_key].write(err_chunk)

    if return_code == -1:
        return weechat.WEECHAT_RC_OK

    err = string_buffers[err_key].getvalue()
    string_buffers[err_key].close()
    del string_buffers[err_key]

    if return_code == weechat.WEECHAT_HOOK_PROCESS_ERROR or return_code > 0 or err:
        print_error(f"failed restoring image, return_code={return_code}, err='{err}'")
        return weechat.WEECHAT_RC_OK

    data.callback(data.callback_data)
    return weechat.WEECHAT_RC_OK


def send_images_to_terminal(
    image_placements: List[ImagePlacement],
    callback: Callable[[str], None],
    callback_data: str,
):
    images_send_data = ImagesSendData(
        image_placements,
        callback,
        callback_data,
    )
    data_serialized = b64encode(pickle.dumps(images_send_data)).decode("ascii")

    weechat.hook_process(
        "func:" + get_callback_name(send_images_to_terminal_bg),
        60000,
        get_callback_name(send_images_to_terminal_bg_finished_cb),
        data_serialized,
    )


def display_image(buffer: str, image_placement: ImagePlacement):
    for x in range(image_placement.rows):
        chars = [
            get_cell_character(image_placement.image_id, x, y, include_color=y == 0)
            for y in range(image_placement.columns)
        ]
        weechat.prnt(buffer, "".join(chars))
