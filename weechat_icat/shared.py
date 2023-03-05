from __future__ import annotations

from typing import Callable, Dict, Union

WeechatCallbackReturnType = Union[int, str, Dict[str, str], None]


class Shared:
    def __init__(self):
        self.SCRIPT_NAME = "icat"
        self.SCRIPT_VERSION = "0.1.0"

        self.weechat_callbacks: Dict[str, Callable[..., WeechatCallbackReturnType]]
        self.cache_path = "${weechat_cache_dir}/icat"
        self.cache_downloaded_images_path = f"{self.cache_path}/downloaded_images"


shared = Shared()
