from .local_binary_pattern_processing import local_binary_pattern, local_ternary_pattern, LBPResult, LTPResult
import numpy as np

def get_texture_feature_vector(image_array: np.ndarray, config) -> np.ndarray:
    texture_extraction_config = config["texture_extraction"]
    if len(texture_extraction_config) != 1:
        raise ValueError("Exactly one texture_extraction method must be specified")

    method_name, method_config = next(iter(texture_extraction_config.items()))
    if method_name == "local_binary_pattern":
        result = local_binary_pattern(
            image_array,
            p=method_config["P"],
            r=method_config["R"],
            method=method_config["method"],
        )

    elif method_name == "local_ternary_pattern":
        result = local_ternary_pattern(
            image_array,
            p=method_config["P"],
            r=method_config["R"],
            method=method_config["method"],
            threshold=method_config["threshold"],
        )

    else:
        raise ValueError(f"Unknown texture extraction method: {method_name}")
    return result