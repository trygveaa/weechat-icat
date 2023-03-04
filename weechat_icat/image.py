from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image


@dataclass
class ImageData:
    data: bytes
    width: int
    height: int


def load_image_data(path: str):
    with io.BytesIO() as data:
        with Image.open(path) as im:
            im.save(data, "png")
            return ImageData(data.getvalue(), im.width, im.height)
