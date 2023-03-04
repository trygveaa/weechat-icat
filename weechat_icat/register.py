from __future__ import annotations

from typing import List

import weechat

from weechat_icat.shared import shared
from weechat_icat.terminal_graphics import (
    ImagePlacement,
    create_image_placement,
    display_image,
    send_image_to_terminal,
)
from weechat_icat.util import get_callback_name

SCRIPT_AUTHOR = "Trygve Aaberge <trygveaa@gmail.com>"
SCRIPT_LICENSE = "MIT"
SCRIPT_DESC = "Display an image in the chat"

image_placements: List[ImagePlacement] = []


def icat_cb(data: str, buffer: str, args: str) -> int:
    if args == "-restore":
        for image_placement in image_placements:
            send_image_to_terminal(image_placement)
        weechat.command(buffer, "/window refresh")
    else:
        image_placement = create_image_placement(args, 10, 10)
        image_placements.append(image_placement)
        send_image_to_terminal(image_placement)
        display_image(buffer, image_placement)
    return weechat.WEECHAT_RC_OK


def register():
    if weechat.register(
        shared.SCRIPT_NAME,
        SCRIPT_AUTHOR,
        shared.SCRIPT_VERSION,
        SCRIPT_LICENSE,
        SCRIPT_DESC,
        "",
        "",
    ):
        command_icat_description = (
            "filename: image to display, must be a png\n"
            "-restore: instead of displaying a new image, restore the existing "
            "images to a new terminal instance"
        )
        weechat.hook_command(
            "icat",
            "display an image in the chat",
            "<filename> || -restore",
            command_icat_description,
            "-restore",
            get_callback_name(icat_cb),
            "",
        )
