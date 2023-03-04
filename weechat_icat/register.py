from __future__ import annotations

import weechat

from weechat_icat.shared import shared
from weechat_icat.terminal_graphics import display_image
from weechat_icat.util import get_callback_name

SCRIPT_AUTHOR = "Trygve Aaberge <trygveaa@gmail.com>"
SCRIPT_LICENSE = "MIT"
SCRIPT_DESC = "Display an image in the chat"


def icat_cb(data: str, buffer: str, args: str) -> int:
    display_image(buffer, args, 10, 10)
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
        weechat.hook_command(
            "icat",
            "display an image in the chat",
            "<filename>",
            "filename: image to display, must be a png",
            "",
            get_callback_name(icat_cb),
            "",
        )
