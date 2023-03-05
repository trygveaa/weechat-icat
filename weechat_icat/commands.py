from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Dict, List

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
    buffer: str, image_placement: ImagePlacement, image_placement_was_returned: bool
):
    if image_placement_was_returned:
        weechat.command(buffer, "/window refresh")
    else:
        new_image_placement(buffer, image_placement)


def images_restored_cb(buffer: str):
    weechat.command(buffer, "/window refresh")
    print_info("finished restoring images")


def icat_cb(data: str, buffer: str, args: str) -> int:
    pos_args, options = parse_options(
        args, {"columns": True, "rows": True, "restore": False}
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

        path = weechat.string_eval_path_home(pos_args, {}, {}, {})
        if not os.path.isfile(path):
            print_error("filename must point to an existing file")
            return weechat.WEECHAT_RC_ERROR

        for ip in image_placements[path]:
            if (columns_int is None or columns_int == ip.columns) and (
                rows_int is None or rows_int == ip.rows
            ):
                image_placement = ip
                display_image(buffer, image_placement)
                break
        else:
            image_placement = create_and_send_image_to_terminal(
                path, columns_int, rows_int, image_created_cb, buffer
            )
            if image_placement:
                new_image_placement(buffer, image_placement)

    return weechat.WEECHAT_RC_OK


def register_commands():
    command_icat_description = (
        "-columns: number of columns to use to display the image\n"
        "   -rows: number of rows to use to display the image\n"
        "filename: image to display\n"
        "-restore: instead of displaying a new image, restore the existing "
        "images to a new terminal instance"
    )
    weechat.hook_command(
        "icat",
        "display an image in the chat",
        "[-columns <columns>] [-rows <rows>] <filename> || -restore",
        command_icat_description,
        "-columns|-rows|%* || -restore",
        get_callback_name(icat_cb),
        "",
    )
