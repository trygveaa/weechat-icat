from __future__ import annotations

import weechat

from weechat_icat.commands import register_commands
from weechat_icat.shared import shared

SCRIPT_AUTHOR = "Trygve Aaberge <trygveaa@gmail.com>"
SCRIPT_LICENSE = "MIT"
SCRIPT_DESC = "Display images in the chat"


def create_cache_paths():
    paths = [shared.cache_path, shared.cache_downloaded_images_path]
    for path in paths:
        if not weechat.mkdir_home(path, 0o755):
            raise RuntimeError("Failed creating cache path")


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
        create_cache_paths()
        register_commands()
