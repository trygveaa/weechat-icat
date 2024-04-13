from __future__ import annotations

import weechat

from weechat_icat.shared import shared


def print_log(prefix: str, message: str):
    sep = "" if prefix.endswith("\t") else "\t"
    weechat.prnt("", f"{prefix}{sep}{shared.SCRIPT_NAME}: {message}")


def print_info(message: str):
    print_log("", message)


def print_error(message: str):
    if shared.print_errors:
        print_log(weechat.prefix("error"), message)
