from __future__ import annotations

import weechat

from weechat_icat.shared import shared


def print_error(message: str):
    weechat.prnt("", f"{weechat.prefix('error')}{shared.SCRIPT_NAME}: {message}")
