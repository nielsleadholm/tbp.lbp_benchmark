
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from PIL import Image

DistanceValue = Union[float, int, str, None]


@dataclass(frozen=True)
class MatchItemModel:
    index: int

    original_image: Optional[Image.Image]
    matched_image: Optional[Image.Image]

    original_meta: Dict[str, str]
    matched_meta: Dict[str, str]
    distance: DistanceValue
    metric_name: str

    matched_images: Optional[List[Image.Image]] = None
    matched_meta_list: Optional[List[Dict[str, str]]] = None
    matched_distances: Optional[List[DistanceValue]] = None
