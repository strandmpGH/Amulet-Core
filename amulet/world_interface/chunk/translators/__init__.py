from __future__ import annotations

import os
import numpy

from typing import Tuple, Callable, Union, List, Any

from amulet.api.block import BlockManager, Block
from amulet.api.block_entity import BlockEntity
from amulet.api.entity import Entity
from amulet.api.chunk import Chunk
from amulet.world_interface.loader import Loader
import PyMCTranslate
from PyMCTranslate.py3.translation_manager import Version

SUPPORTED_TRANSLATOR_VERSION = 0
SUPPORTED_META_VERSION = 0

TRANSLATORS_DIRECTORY = os.path.dirname(__file__)

loader = Loader(
    "translator",
    TRANSLATORS_DIRECTORY,
    SUPPORTED_META_VERSION,
    SUPPORTED_TRANSLATOR_VERSION,
)


class Translator:
    def _translator_key(
        self, version_number: Union[int, Tuple[int, int, int]]
    ) -> Tuple[str, Union[int, Tuple[int, int, int]]]:
        """
        Return the version key for PyMCTranslate

        :return: The tuple version key for PyMCTranslate
        """
        raise NotImplementedError()

    @staticmethod
    def is_valid(key: Tuple) -> bool:
        """
        Returns whether this translator is able to translate the chunk type with a given identifier key,
        generated by the decoder.

        :param key: The key who's decodability needs to be checked.
        :return: True if this translator is able to translate the chunk type associated with the key, False otherwise.
        """
        raise NotImplementedError()

    def _translate(
        self,
        chunk: Chunk,
        palette: numpy.ndarray,
        get_chunk_callback: Union[Callable[[int, int], Tuple[Chunk, numpy.ndarray]], None],
        translate: Callable[
            [
                Union[Block, Entity, Any],
                Callable[
                    [Tuple[int, int, int]],
                    Tuple[Block, Union[None, BlockEntity]]
                ]
            ],
            Tuple[Block, BlockEntity, List[Entity], bool]
        ],
        full_translate: bool,
    ) -> Tuple[Chunk, numpy.ndarray]:
        if not full_translate:
            return chunk, palette

        todo = []
        output_block_entities = []
        finished = BlockManager()
        palette_mappings = {}

        for i, input_block in enumerate(palette):
            input_block: Block
            output_block, output_block_entity, output_entities, extra = translate(input_block)
            if extra and get_chunk_callback:
                todo.append(i)
            else:
                palette_mappings[i] = finished.get_add_block(output_block)
                if output_block_entity:
                    for x, y, z in zip(*numpy.where(chunk.blocks == i)):
                        output_block_entity.x += x + chunk.cx * 16
                        output_block_entity.y += y
                        output_block_entity.z += z + chunk.cz * 16
                        output_block_entities.append(output_block_entity)

        block_mappings = {}
        for index in todo:
            for x, y, z in zip(*numpy.where(chunk.blocks == index)):

                def get_block_at(pos: Tuple[int, int, int]) -> Tuple[Block, Union[None, BlockEntity]]:
                    """Get a block at a location relative to the current block"""
                    nonlocal x, y, z, palette, chunk

                    # calculate absolute position
                    dx, dy, dz = pos
                    dx += x
                    dy += y
                    dz += z

                    # calculate relative chunk position
                    cx = dx // 16
                    cz = dz // 16
                    if cx == 0 and cz == 0:
                        # if it is the current chunk
                        return palette[chunk.blocks[dx % 16, dy, dz % 16]], \
                            next((be for be in chunk.block_entities if (be.x, be.y, be.z) == (dx, dy, dz)), None)

                    # if it is in a different chunk
                    local_chunk, local_palette = get_chunk_callback(cx, cz)
                    return local_palette[local_chunk.blocks[dx % 16, dy, dz % 16]], \
                        next((be for be in local_chunk.block_entities if (be.x, be.y, be.z) == (dx, dy, dz)), None)

                input_block = palette[chunk.blocks[x, y, z]]
                output_block, output_block_entity, output_entities, extra = translate(input_block, get_block_at)
                if output_block_entity:
                    output_block_entity.x += x + chunk.cx * 16
                    output_block_entity.y += y
                    output_block_entity.z += z + chunk.cz * 16
                    output_block_entities.append(output_block_entity)
                block_mappings[(x, y, z)] = finished.get_add_block(output_block)

        for old, new in palette_mappings.items():
            chunk.blocks[chunk.blocks == old] = new
        for (x, y, z), new in block_mappings.items():
            chunk.blocks[x, y, z] = new
        chunk.block_entities = output_block_entities
        return chunk, numpy.array(finished.blocks())

    def to_universal(
        self,
        chunk_version: Union[int, Tuple[int, int, int]],
        translation_manager: PyMCTranslate.TranslationManager,
        chunk: Chunk,
        palette: numpy.ndarray,
        get_chunk_callback: Union[Callable[[int, int], Tuple[Chunk, numpy.ndarray]], None],
        full_translate: bool,
    ) -> Tuple[Chunk, numpy.ndarray]:
        """
        Translate an interface-specific chunk into the universal format.

        :param chunk_version: The version number (int or tuple) of the input chunk
        :param translation_manager: PyMCTranslate.TranslationManager used for the translation
        :param chunk: The chunk to translate.
        :param palette: The palette that the chunk's indices correspond to.
        :param get_chunk_callback: function callback to get a chunk's data
        :param full_translate: if true do a full translate. If false just unpack the palette (used in callback)
        :return: Chunk object in the universal format.
        """
        version = translation_manager.get_version(*self._translator_key(chunk_version))
        translator = version.get().to_universal

        def translate(
                input_object: Union[Block, Entity],
                get_block_callback: Callable[[Tuple[int, int, int]], Tuple[Block, Union[None, BlockEntity]]] = None
        ) -> Tuple[Block, BlockEntity, List[Entity], bool]:
            final_block = None
            final_block_entity = None
            final_entities = []
            final_extra = False

            if isinstance(input_object, Block):
                for depth, block in enumerate((input_object.base_block, ) + input_object.extra_blocks):
                    output_object, output_block_entity, extra = translator(block, get_block_callback)

                    if isinstance(output_object, Block):
                        if __debug__ and not output_object.namespace.startswith('universal'):
                            print(f'Error translating {input_object.blockstate} to universal. Got {output_object.blockstate}')
                        if final_block is None:
                            final_block = output_object
                        else:
                            final_block += output_object
                        if depth == 0:
                            final_block_entity = output_block_entity

                    elif isinstance(output_object, Entity):
                        final_entities.append(output_object)
                        # TODO: offset entity coords

                    final_extra |= extra

            elif isinstance(input_object, Entity):
                # TODO: entity support
                pass

            return final_block, final_block_entity, final_entities, final_extra

        palette = self._unpack_palette(version, palette)
        chunk.biomes = self._biomes_to_universal(version, chunk.biomes)
        if version.block_entity_map is not None:
            for block_entity in chunk.block_entities:
                block_entity: BlockEntity
                if block_entity.namespace is None and block_entity.base_name in version.block_entity_map:
                    block_entity.namespaced_name = version.block_entity_map[block_entity.base_name]
        return self._translate(
            chunk, palette, get_chunk_callback, translate, full_translate
        )

    def from_universal(
        self,
        max_world_version_number: Union[int, Tuple[int, int, int]],
        translation_manager: PyMCTranslate.TranslationManager,
        chunk: Chunk,
        palette: numpy.ndarray,
        get_chunk_callback: Union[Callable[[int, int], Tuple[Chunk, numpy.ndarray]], None],
        full_translate: bool,
    ) -> Tuple[Chunk, numpy.ndarray]:
        """
        Translate a universal chunk into the interface-specific format.

        :param max_world_version_number: The version number (int or tuple) of the max world version
        :param translation_manager: PyMCTranslate.TranslationManager used for the translation
        :param chunk: The chunk to translate.
        :param palette: The palette that the chunk's indices correspond to.
        :param get_chunk_callback: function callback to get a chunk's data
        :param full_translate: if true do a full translate. If false just pack the palette (used in callback)
        :return: Chunk object in the interface-specific format and palette.
        """
        version = translation_manager.get_version(
            *self._translator_key(max_world_version_number)
        )
        translator = version.get().from_universal

        # TODO: perhaps find a way so this code isn't duplicated in three places
        def translate(
                input_object: Union[Block, Entity],
                get_block_callback: Callable[[Tuple[int, int, int]], Tuple[Block, Union[None, BlockEntity]]] = None
        ) -> Tuple[Block, BlockEntity, List[Entity], bool]:
            final_block = None
            final_block_entity = None
            final_entities = []
            final_extra = False

            if isinstance(input_object, Block):
                for depth, block in enumerate((input_object.base_block, ) + input_object.extra_blocks):
                    output_object, output_block_entity, extra = translator(block, get_block_callback)

                    if isinstance(output_object, Block):
                        if __debug__ and output_object.namespace.startswith('universal'):
                            print(f'Error translating {input_object.blockstate} from universal. Got {output_object.blockstate}')
                        if final_block is None:
                            final_block = output_object
                        else:
                            final_block += output_object
                        if depth == 0:
                            final_block_entity = output_block_entity

                    elif isinstance(output_object, Entity):
                        final_entities.append(output_object)
                        # TODO: offset entity coords

                    final_extra |= extra

            elif isinstance(input_object, Entity):
                # TODO: entity support
                pass

            return final_block, final_block_entity, final_entities, final_extra

        chunk, palette = self._translate(
            chunk, palette, get_chunk_callback, translate, full_translate
        )
        palette = self._pack_palette(version, palette)
        chunk.biomes = self._biomes_from_universal(version, chunk.biomes)
        if version.block_entity_map is not None:
            for block_entity in chunk.block_entities:
                block_entity: BlockEntity
                if block_entity.namespaced_name in version.block_entity_map_inverse:
                    block_entity.namespaced_name = version.block_entity_map_inverse[block_entity.namespaced_name]
        return chunk, palette

    def _biomes_to_universal(self, translator_version: Version, biome_array):
        biome_palette, biome_compact_array = numpy.unique(biome_array, return_inverse=True)
        universal_biome_palette = numpy.array([translator_version.biomes.to_universal(biome) for biome in biome_palette])
        return universal_biome_palette[biome_compact_array]

    def _biomes_from_universal(self, translator_version: Version, biome_array):
        biome_palette, biome_compact_array = numpy.unique(biome_array, return_inverse=True)
        universal_biome_palette = numpy.array([translator_version.biomes.from_universal(biome) for biome in biome_palette])
        return universal_biome_palette[biome_compact_array]

    def _unpack_palette(
        self, version: Version, palette: numpy.ndarray
    ) -> numpy.ndarray:
        """
        Unpack the version-specific palette into the stringified version where needed.

        :return: The palette converted to block objects.
        """
        return palette

    def _pack_palette(self, version: Version, palette: numpy.ndarray) -> numpy.ndarray:
        """
        Translate the list of block objects into a version-specific palette.
        :return: The palette converted into version-specific blocks (ie id, data tuples for 1.12)
        """
        return palette


if __name__ == "__main__":
    import time

    print(loader.get_all())
    time.sleep(1)
    loader.reload()
    print(loader.get_all())
