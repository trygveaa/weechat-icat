from __future__ import annotations

import array
import fcntl
import os
import pickle
import termios
from base64 import b64decode, b64encode
from collections import defaultdict
from dataclasses import dataclass, field
from io import StringIO
from random import randint
from typing import Callable, Dict, List, Optional, Union
from uuid import UUID, uuid4

import weechat

from weechat_icat.image import ImageData, load_image_data
from weechat_icat.terminal_graphics_diacritics import rowcolumn_diacritics_chars
from weechat_icat.util import get_callback_name

string_buffers: Dict[str, StringIO] = defaultdict(StringIO)
image_create_queue: List[ImageCreateData] = []


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
    terminal_cmds: List[bytes] = field(default_factory=list)


ImageCreateFinished = Union[ImagePlacement, Exception]
ImagesSendFinished = Union[None, Exception]


@dataclass
class ImageCreateData:
    path: str
    image_id: int
    columns: Optional[int]
    rows: Optional[int]
    terminal_size: TerminalSize
    image_placement: Optional[ImagePlacement]
    callback: Callable[[str, ImageCreateFinished, bool], None]
    callback_data: str
    uuid: UUID = uuid4()


@dataclass
class ImagesSendData:
    image_placements: List[ImagePlacement]
    callback: Callable[[str, ImagesSendFinished], None]
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
    cmds: List[bytes] = []
    with open(os.ctermid(), "wb") as tty:
        data_base64 = b64encode(data)
        while data_base64:
            chunk, data_base64 = data_base64[:4096], data_base64[4096:]
            m = 1 if data_base64 else 0
            cmd = serialize_gr_command({**control_data, "m": m}, chunk)
            cmds.append(cmd)
            tty.write(cmd)
            tty.flush()
            control_data.clear()
    return cmds


def get_cell_character(
    image_id: int,
    y: int,
    x: int,
    include_color: bool = False,
):
    image_id_upper = image_id >> 24
    image_id_lower = image_id & 0xFF
    color = weechat.color(str(image_id_lower)) if include_color else ""
    y_char = rowcolumn_diacritics_chars[y]
    x_char = rowcolumn_diacritics_chars[x]
    id_char = rowcolumn_diacritics_chars[image_id_upper]
    return f"{color}\U0010eeee{y_char}{x_char}{id_char}"


def create_and_send_image_to_terminal_bg(data_serialized: str) -> str:
    try:
        data: ImageCreateData = pickle.loads(b64decode(data_serialized))
        image_data = load_image_data(data.path)

        if data.image_placement:
            image_placement = data.image_placement
        else:
            image_columns = (
                image_data.width / data.terminal_size.width * data.terminal_size.columns
            )
            image_rows = (
                image_data.height / data.terminal_size.height * data.terminal_size.rows
            )

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
    except Exception as e:  # pylint: disable=broad-exception-caught
        return b64encode(pickle.dumps(e)).decode("ascii")


def create_and_send_image_to_terminal_bg_finished_cb(
    data_serialized: str, command: str, return_code: int, out_chunk: str, err_chunk: str
) -> int:
    try:
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

        image_placement_was_returned = data.image_placement is not None

        if return_code == weechat.WEECHAT_HOOK_PROCESS_ERROR or return_code > 0 or err:
            error = RuntimeError(f"return_code={return_code}, err='{err}'")
            data.callback(data.callback_data, error, image_placement_was_returned)
            return weechat.WEECHAT_RC_OK

        result: ImageCreateFinished = pickle.loads(b64decode(out))
        data.callback(data.callback_data, result, image_placement_was_returned)
    finally:
        if return_code != -1:
            image_create_queue.pop(0)
            start_image_create_job(True)
    return weechat.WEECHAT_RC_OK


def start_image_create_job(prev_job_finished: bool):
    if image_create_queue and prev_job_finished or len(image_create_queue) == 1:
        data_serialized = b64encode(pickle.dumps(image_create_queue[0])).decode("ascii")
        weechat.hook_process(
            "func:" + get_callback_name(create_and_send_image_to_terminal_bg),
            60000,
            get_callback_name(create_and_send_image_to_terminal_bg_finished_cb),
            data_serialized,
        )


def create_and_send_image_to_terminal(
    image_path: str,
    columns: Optional[int],
    rows: Optional[int],
    callback: Callable[[str, ImageCreateFinished, bool], None],
    callback_data: str,
):
    image_id = get_random_image_id()
    if columns and rows:
        image_placement = ImagePlacement(image_path, image_id, columns, rows)
    else:
        image_placement = None

    image_create_data = ImageCreateData(
        image_path,
        image_id,
        columns,
        rows,
        get_terminal_size(),
        image_placement,
        callback,
        callback_data,
    )
    image_create_queue.append(image_create_data)
    start_image_create_job(False)
    return image_placement


def send_image_to_terminal(
    image_placement: ImagePlacement, image_data: Optional[ImageData] = None
):
    if image_placement.terminal_cmds:
        with open(os.ctermid(), "wb") as tty:
            for cmd in image_placement.terminal_cmds:
                tty.write(cmd)
                tty.flush()
    else:
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
        image_placement.terminal_cmds = write_chunked(control_data, image_data.data)


def send_images_to_terminal_bg(data_serialized: str):
    try:
        data: ImagesSendData = pickle.loads(b64decode(data_serialized))
        for image_placement in data.image_placements:
            send_image_to_terminal(image_placement)
        return b64encode(pickle.dumps(None)).decode("ascii")
    except Exception as e:  # pylint: disable=broad-exception-caught
        return b64encode(pickle.dumps(e)).decode("ascii")


def send_images_to_terminal_bg_finished_cb(
    data_serialized: str, command: str, return_code: int, out_chunk: str, err_chunk: str
) -> int:
    data: ImagesSendData = pickle.loads(b64decode(data_serialized))
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
        error = RuntimeError(f"return_code={return_code}, err='{err}'")
        data.callback(data.callback_data, error)
        return weechat.WEECHAT_RC_OK

    result: ImagesSendFinished = pickle.loads(b64decode(out))
    data.callback(data.callback_data, result)
    return weechat.WEECHAT_RC_OK


def send_images_to_terminal(
    image_placements: List[ImagePlacement],
    callback: Callable[[str, ImagesSendFinished], None],
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
    for y in range(image_placement.rows):
        chars = [
            get_cell_character(image_placement.image_id, y, x, include_color=x == 0)
            for x in range(image_placement.columns)
        ]
        weechat.prnt(buffer, "".join(chars))
