from __future__ import annotations

import os
import numpy
from typing import Tuple, Any, Union, Callable

from amulet.api.chunk import Chunk
from amulet.world_interface.chunk import translators
from amulet.world_interface.loader import Loader
import amulet_nbt as nbt
import PyMCTranslate

SUPPORTED_INTERFACE_VERSION = 0
SUPPORTED_META_VERSION = 0

INTERFACES_DIRECTORY = os.path.dirname(__file__)

loader = Loader('interface', INTERFACES_DIRECTORY, SUPPORTED_META_VERSION, SUPPORTED_INTERFACE_VERSION)


class Interface:
    def decode(self, data: Any) -> Tuple[Chunk, numpy.ndarray]:
        """
        Create an amulet.api.chunk.Chunk object from raw data given by the format
        :param data: Raw chunk data provided by the format.
        :return: Chunk object in version-specific format, along with the palette for that chunk.
        """
        raise NotImplementedError()

    def encode(self, chunk: Chunk, palette: numpy.ndarray, max_world_version: Tuple[str, Union[int, Tuple[int, int, int]]]) -> Any:
        """
        Take a version-specific chunk and encode it to raw data for the format to store.
        :param chunk: The version-specfic chunk to translate and encode.
        :param palette: The palette the ids in the chunk correspond to.
        :return: Raw data to be stored by the format.
        """
        raise NotImplementedError()

    def get_translator(self, max_world_version: Tuple[str, Union[int, Tuple[int, int, int]]], data: Any = None) -> Tuple[translators.Translator, Union[int, Tuple[int, int, int]]]:
        if data:
            key, version = self._get_translator_info(data)
        else:
            key = max_world_version
            version = max_world_version[1]
        return translators.loader.get(key), version

    def _get_translator_info(self, data: Any) -> Tuple[Any, Union[int, Tuple[int, int, int]]]:
        raise NotImplementedError()

    @staticmethod
    def is_valid(key: Tuple) -> bool:
        """
        Returns whether this interface is able to interface with the chunk type with a given identifier key,
        generated by the format.

        :param key: The key who's decodability needs to be checked.
        :return: True if this interface can interface with the chunk version associated with the key, False otherwise.
        """
        raise NotImplementedError()


if __name__ == "__main__":
    import time

    print(loader.get_all())
    time.sleep(1)
    loader.reload()
    print(loader.get_all())
