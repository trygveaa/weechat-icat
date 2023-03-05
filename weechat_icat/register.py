from __future__ import annotations

import weechat

from weechat_icat.commands import register_commands
from weechat_icat.shared import shared

SCRIPT_AUTHOR = "Trygve Aaberge <trygveaa@gmail.com>"
SCRIPT_LICENSE = "MIT"
SCRIPT_DESC = "Display images in the chat"


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
        register_commands()
