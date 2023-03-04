from __future__ import annotations

from typing import Callable, Dict, Union

WeechatCallbackReturnType = Union[int, str, Dict[str, str], None]


class Shared:
    def __init__(self):
        self.SCRIPT_NAME = "icat"
        self.SCRIPT_VERSION = "0.1.0"

        self.weechat_callbacks: Dict[str, Callable[..., WeechatCallbackReturnType]]


shared = Shared()
