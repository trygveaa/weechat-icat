from __future__ import annotations

from typing import Callable

from weechat_icat.shared import WeechatCallbackReturnType, shared


def get_callback_name(callback: Callable[..., WeechatCallbackReturnType]) -> str:
    callback_id = f"{callback.__name__}-{id(callback)}"
    shared.weechat_callbacks[callback_id] = callback
    return callback_id
