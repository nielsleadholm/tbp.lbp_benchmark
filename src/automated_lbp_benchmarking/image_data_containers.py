from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np
from PIL import Image

@dataclass
class MatchRecord:
    matched_image: Image.Image = None
    matched_index: Optional[int] = None
    matched_category: Optional[str] = None
    nn_distance: Optional[float] = None
    correct: Optional[bool] = None

@dataclass
class ImageRecord:
    # Parsed filename metadata
    instance: str
    category: str
    distance: str
    rotation: str
    lighting: str

    # Data payload
    image: Image.Image  # cropped (or original) RGB/gray PIL image for visualization
    lbp_hist: np.ndarray  # normalized histogram feature vector (float64)
    match_records: List[MatchRecord] = field(default_factory=list)  # For storing multiple matches if tolerance/top is used