from __future__ import annotations

import os
import pickle
import re
from base64 import b64decode, b64encode
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

import weechat

from weechat_icat.log import print_error, print_info
from weechat_icat.python_compatibility import removeprefix
from weechat_icat.terminal_graphics import (
    ImagePlacement,
    create_and_send_image_to_terminal,
    display_image,
    send_images_to_terminal,
)
from weechat_icat.util import get_callback_name

image_placements: Dict[str, List[ImagePlacement]] = defaultdict(list)


@dataclass
class ImageCreatedData:
    buffer: str
    print_immediately: bool


def parse_options(args: str, supported_options: Dict[str, bool]):
    args_split = re.split(r"(\s+)", args)
    pos_args: List[str] = []
    options: Dict[str, str] = {}
    i = 0
    while i < len(args_split):
        arg = args_split[i]
        option_name = removeprefix(arg, "-")
        if option_name in supported_options:
            if supported_options[option_name]:
                i += 2
                options[option_name] = args_split[i]
            else:
                options[option_name] = " "
            i += 1
        else:
            pos_args.append(arg)
        i += 1
    return "".join(pos_args).strip(), options


def new_image_placement(buffer: str, image_placement: ImagePlacement):
    display_image(buffer, image_placement)
    image_placements[image_placement.path].append(image_placement)


def image_created_cb(
    data_serialized: str,
    image_placement: ImagePlacement,
    image_placement_was_returned: bool,
):
    data: ImageCreatedData = pickle.loads(b64decode(data_serialized))
    if data.print_immediately and image_placement_was_returned:
        weechat.command(data.buffer, "/window refresh")
    else:
        new_image_placement(data.buffer, image_placement)


def images_restored_cb(buffer: str):
    weechat.command(buffer, "/window refresh")
    print_info("finished restoring images")


def create_image(
    buffer: str,
    path: str,
    columns: Optional[int],
    rows: Optional[int],
    print_immediately: bool,
):
    for ip in image_placements[path]:
        if (columns is None or columns == ip.columns) and (
            rows is None or rows == ip.rows
        ):
            image_placement = ip
            display_image(buffer, image_placement)
            break
    else:
        image_created_data = ImageCreatedData(buffer, print_immediately)
        callback_data = b64encode(pickle.dumps(image_created_data)).decode("ascii")
        image_placement = create_and_send_image_to_terminal(
            path, columns, rows, image_created_cb, callback_data
        )
        if print_immediately and image_placement:
            new_image_placement(buffer, image_placement)


def icat_cb(data: str, buffer: str, args: str) -> int:
    pos_args, options = parse_options(
        args,
        {"columns": True, "rows": True, "print_immediately": False, "restore": False},
    )
    if "restore" in options:
        image_placements_values = [
            image_placement
            for image_placement_list in image_placements.values()
            for image_placement in image_placement_list
        ]
        send_images_to_terminal(image_placements_values, images_restored_cb, buffer)
    else:
        columns = options.get("columns")
        if columns is not None and not columns.isdecimal():
            print_error("columns must be a positive integer")
            return weechat.WEECHAT_RC_ERROR
        columns_int = int(columns) if columns else None

        rows = options.get("rows")
        if rows is not None and not rows.isdecimal():
            print_error("rows must be a positive integer")
            return weechat.WEECHAT_RC_ERROR
        rows_int = int(rows) if rows else None

        print_immediately = options.get("print_immediately")
        if print_immediately and (not columns_int or not rows_int):
            print_error(
                "both -columns and -rows must be specified when using -print_immediately"
            )
            return weechat.WEECHAT_RC_ERROR

        path = weechat.string_eval_path_home(pos_args, {}, {}, {})
        if not os.path.isfile(path):
            print_error("filename must point to an existing file")
            return weechat.WEECHAT_RC_ERROR

        create_image(buffer, path, columns_int, rows_int, bool(print_immediately))

    return weechat.WEECHAT_RC_OK


def register_commands():
    command_icat_description = (
        "          -columns: number of columns to use to display the image\n"
        "             -rows: number of rows to use to display the image\n"
        "-print_immediately: print the image lines immediately (the lines will "
        "be blank until the image is created); requires both -columns and -rows\n"
        "          filename: image to display\n"
        "          -restore: instead of displaying a new image, restore the existing "
        "images to a new terminal instance\n"
        "\n"
        "Note that images are loaded in the background, so they may not be "
        "displayed immediately after running the command."
    )
    weechat.hook_command(
        "icat",
        "display an image in the chat",
        "[-columns <columns>] [-rows <rows>] [-print_immediately] <filename> || -restore",
        command_icat_description,
        "-columns|-rows|-print_immediately|%* || -restore",
        get_callback_name(icat_cb),
        "",
    )
