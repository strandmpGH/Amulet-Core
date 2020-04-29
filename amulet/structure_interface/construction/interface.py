from typing import TYPE_CHECKING, Any, Tuple, Union, List
import numpy

from amulet.api.wrapper import Interface
from .construction import ConstructionSection
from amulet.api.chunk import Chunk
from amulet.api.block import Block
from amulet.api.selection import SelectionBox
from amulet.world_interface.chunk import translators

if TYPE_CHECKING:
    from amulet.api.wrapper import Translator
    from PyMCTranslate import TranslationManager


class ConstructionInterface(Interface):
    def is_valid(self, key: Tuple) -> bool:
        return True

    def decode(self, cx: int, cz: int, data: List[ConstructionSection]) -> Tuple['Chunk', numpy.ndarray]:
        chunk = Chunk(cx, cz)
        palette = [Block(namespace="minecraft", base_name="air")]
        for section in data:
            shapex, shapey, shapez = section.shape
            sx = section.sx % 16
            sy = section.sy % 16
            sz = section.sz % 16
            chunk.blocks[
                sx: sx + shapex,
                sy: sy + shapey,
                sz: sz + shapez,
            ] = section.blocks + len(palette)
            chunk.entities.extend(section.entities)
            chunk.block_entities.update(section.block_entities)

        np_palette, inverse = numpy.unique(palette, return_inverse=True)
        np_palette: numpy.ndarray
        inverse: numpy.ndarray
        for cy in chunk.blocks:
            chunk.blocks.add_sub_chunk(
                cy,
                inverse[chunk.blocks.get_sub_chunk(cy)].astype(numpy.uint32)
            )
        return chunk, np_palette

    def encode(
        self,
        chunk: 'Chunk',
        palette: numpy.ndarray,
        max_world_version: Tuple[str, Union[int, Tuple[int, int, int]]],
        boxes: List[SelectionBox] = None
    ) -> List[ConstructionSection]:
        sections = []
        for box in boxes:
            cx, cz = box.min_x >> 4, box.min_z >> 4
            for cy in box.chunk_y_locations():
                sub_box = box.intersection(SelectionBox.create_sub_chunk_box(cx, cy, cz))
                entities = [e for e in chunk.entities if e.location in sub_box]
                if cy in chunk.blocks:
                    sections.append(ConstructionSection(
                        box.min,
                        box.shape,
                        chunk.blocks[sub_box.chunk_slice(cx, cz)],
                        list(palette),
                        entities,
                        list(chunk.block_entities),
                    ))
                elif entities:
                    sections.append(ConstructionSection(
                        box.min,
                        box.shape,
                        None,
                        [],
                        entities,
                        []
                    ))

        return sections

    def get_translator(
        self,
        max_world_version: Tuple[str, Tuple[int, int, int]],
        data: Any = None,
        translation_manager: 'TranslationManager' = None
    ) -> Tuple['Translator', Union[int, Tuple[int, int, int]]]:
        platform, version_number = max_world_version
        version = translation_manager.get_version(platform, version_number)
        if platform == 'java':
            version_number = version.data_version
        return translators.loader.get((version, version_number)), 0


class Construction0Interface(ConstructionInterface):
    pass