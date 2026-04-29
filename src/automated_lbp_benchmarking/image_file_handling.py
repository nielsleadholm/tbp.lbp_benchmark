from PIL import Image
import os
from typing import List
from .image_data_containers import ImageRecord, MatchRecord

def get_images_in_folder_as_image_records(folder_path: str) -> List[ImageRecord]:
    image_records: List[ImageRecord] = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
            try:
                image_path = os.path.join(folder_path, filename)
                image = Image.open(image_path).convert('RGB')
                image_metadata = parse_filename(filename)
                instance = image_metadata.get("INSTANCE", "unknown")
                category = image_metadata.get("CATEGORY", "unknown")
                distance = image_metadata.get("DISTANCE", "unknown")
                rotation = image_metadata.get("ROTATION", "unknown")
                lighting = image_metadata.get("LIGHTING", "unknown")
                image_record = ImageRecord(
                    instance=instance,
                    category=category,
                    distance=distance,
                    rotation=rotation,
                    lighting=lighting,
                    image=image,
                    lbp_hist=None
                )
                image_records.append(image_record)
            except Exception as e:
                print(f"Error loading image {filename}: {e}")
    return image_records

def parse_filename(filename: str) -> dict:
    """
    Parse filename of form:
        INSTANCE_CATEGORY_DISTANCE_ROTATION_LIGHTING.png

    Returns dict with keys:
        INSTANCE, CATEGORY, DISTANCE, ROTATION, LIGHTING
    """
    parsed_filename = filename.split("_")
    if len(parsed_filename) < 5:
        raise ValueError(f"Filename does not match expected format: {filename}")

    return {
        "INSTANCE": parsed_filename[0],
        "CATEGORY": parsed_filename[1],
        "DISTANCE": parsed_filename[2],
        "ROTATION": parsed_filename[3],
        "LIGHTING": parsed_filename[4],
    }
