from __future__ import annotations

import argparse
import csv
import shutil
import time
import yaml

from typing import Optional, Sequence
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.color import rgb2gray

from .image_file_handling import get_images_in_folder_as_image_records
from .texture_extraction_registry import get_texture_feature_vector
from .image_processing import apply_PIL_processing, apply_numpy_processing
from .processed_to_raw_image_matching import ProcessedToRawMatcher
from .match_statistics import compute_match_distance_stats, MatchDistanceStats
from .visualization import visualize_image_records
from .save_visualization_as_pdf import create_image_record_match_pdf
from .result_logging import save_matches_csv
from datetime import datetime


# Keys that an LBP config is expected to provide.
LBP_CONFIG_KEYS = ("texture_extraction", "matching")
# Keys that an experiment config is expected to provide.
EXPERIMENT_CONFIG_KEYS = (
    "data",
    "rng",
    "query_image_processing",
    "target_image_processing",
)


def load_yaml(path: Path) -> dict:
    """Load a YAML file into a dictionary."""
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def build_run_config(lbp_config: dict, experiment_config: dict) -> dict:
    """Merge an LBP (texture extraction + matching) config with an experiment config.

    The experiment config supplies the dataset, rng, perturbations, and output
    options, while the LBP config supplies texture extraction and matching
    parameters. The two are combined into a single dict used by the rest of the
    pipeline.
    """
    missing_lbp = [k for k in LBP_CONFIG_KEYS if k not in lbp_config]
    if missing_lbp:
        raise ValueError(
            f"LBP config is missing required section(s): {missing_lbp}. "
            f"An LBP config must define {list(LBP_CONFIG_KEYS)}."
        )
    missing_exp = [k for k in EXPERIMENT_CONFIG_KEYS if k not in experiment_config]
    if missing_exp:
        raise ValueError(
            f"Experiment config is missing required section(s): {missing_exp}. "
            f"An experiment config must define {list(EXPERIMENT_CONFIG_KEYS)}."
        )

    run_config = dict(experiment_config)
    run_config["texture_extraction"] = lbp_config["texture_extraction"]
    run_config["matching"] = lbp_config["matching"]
    # Default output options if the experiment config omits them.
    run_config.setdefault(
        "output", {"save_csv": True, "save_pdf": False, "visualize": False}
    )
    return run_config


def run_single_experiment(
    run_config: dict,
    run_name: str,
    config_source: Optional[Path] = None,
    force_visualize: bool = False,
) -> tuple[MatchDistanceStats, float, int]:
    """Run a single experiment (one LBP config + one experiment config).

    When ``force_visualize`` is True, the results visualization GUI is shown
    regardless of the experiment config's ``output.visualize`` setting.

    Returns the match-distance statistics, the elapsed processing time, and the
    number of LBP codes (length of the feature vector / total histogram bins)
    produced by the texture extraction setup.
    """
    rng = np.random.default_rng(seed=run_config["rng"]["seed"])

    query_image_folder = run_config["data"]["query_images_folder"]
    target_image_folder = run_config["data"]["target_images_folder"]
    query_image_records = get_images_in_folder_as_image_records(query_image_folder)
    target_image_records = get_images_in_folder_as_image_records(target_image_folder)

    # Perform image preprocessing and texture extraction for both raw and working
    # image records. Generally, target (raw) records have minimal processing, while
    # query (processed) records have more aggressive processing to simulate noise,
    # illumination, and other real-world conditions.
    start = time.time()
    for records, processing_config in [
        (target_image_records, run_config["target_image_processing"]),
        (query_image_records, run_config["query_image_processing"]),
    ]:
        for record in records:
            processed_image = record.image
            processed_image = apply_PIL_processing(processed_image, processing_config, rng=rng)
            processed_image = apply_numpy_processing(processed_image, processing_config, rng=rng)
            record.image = Image.fromarray(processed_image)
            gray_image = rgb2gray(processed_image)
            image_array = (gray_image * 255).astype(np.uint8)  # uint8 format expected by LBP functions
            hist = get_texture_feature_vector(image_array, run_config)
            record.lbp_hist = hist

    # The feature-vector length (total number of LBP codes / histogram bins) is
    # fixed by the texture extraction config, so any computed histogram reports it.
    num_lbp_codes = int(len(query_image_records[0].lbp_hist))

    # Match query records (processed) against target records (raw).
    distance_metric = run_config["matching"]["metric"]
    match_tolerance = run_config["matching"]["tolerance"]
    top_k = run_config["matching"]["top"]
    matcher = ProcessedToRawMatcher(metric_name=distance_metric, tolerance=match_tolerance, top=top_k)
    processed_matched_records = matcher(query_image_records, target_image_records)
    stats = compute_match_distance_stats(processed_matched_records)
    elapsed = time.time() - start

    print(f"\n=== Experiment: {run_name} ===")
    print(stats)
    print(f"Total number of LBP codes (feature vector length): {num_lbp_codes}")
    print(f"Total time to process and match images: {elapsed:.4f} seconds")

    output_config = run_config.get("output", {})
    save_csv = output_config.get("save_csv", False)
    save_pdf = output_config.get("save_pdf", False)
    visualize = force_visualize or output_config.get("visualize", False)

    output_dir = None
    if save_csv or save_pdf:
        project_root = Path(__file__).resolve().parents[2]
        results_dir = project_root / "results" / run_name
        results_dir.mkdir(parents=True, exist_ok=True)
        if save_csv:
            output_dir = save_matches_csv(processed_matched_records, results_dir)
        if save_pdf:
            output_dir = create_image_record_match_pdf(
                image_records=processed_matched_records,
                results_dir=results_dir,
                stats=stats,
                config=run_config,
                records_per_page=5,
                matches_per_row=top_k,
            )
        # Persist the merged config used for this run alongside its results.
        with open(Path(output_dir) / "run_config.yaml", "w") as f:
            yaml.safe_dump(run_config, f, sort_keys=False)
        if config_source is not None:
            shutil.copy(config_source, Path(output_dir) / "experiment_config.yaml")

    if visualize:
        visualize_image_records(processed_matched_records, 50)

    return stats, elapsed, num_lbp_codes


def write_summary_csv(summary_rows: Sequence[dict], output_path: Path) -> Path:
    """Write one row per experiment to an aggregate summary CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_name",
        "lbp_config",
        "experiment_config",
        "num_lbp_codes",
        "total_matches",
        "total_correct",
        "total_incorrect",
        "percent_correct",
        "highest_correct",
        "lowest_correct",
        "average_correct",
        "highest_incorrect",
        "lowest_incorrect",
        "average_incorrect",
        "time_seconds",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)
    return output_path


def main(cli_args=None, return_results: bool = False) -> Optional[dict]:
    parser = argparse.ArgumentParser(
        description=(
            "Run one or more LBP benchmarking experiments. A single LBP config "
            "(texture extraction + matching) is evaluated against a series of "
            "experiment configs (dataset, rng, and perturbations)."
        )
    )
    parser.add_argument(
        "--lbp-config",
        type=Path,
        required=True,
        help="Path to the YAML config defining texture extraction + matching parameters.",
    )
    parser.add_argument(
        "--experiment-config",
        type=Path,
        nargs="+",
        required=True,
        help=(
            "One or more paths to experiment YAML configs (dataset, rng, "
            "perturbations, output). Evaluated in series."
        ),
    )
    parser.add_argument(
        "--summary-csv",
        type=Path,
        default=None,
        help=(
            "Path for the aggregate summary CSV. Defaults to "
            "results/summary_<timestamp>.csv."
        ),
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help=(
            "Open the results visualization GUI after each experiment finishes, "
            "overriding the per-experiment 'output.visualize' setting."
        ),
    )

    args = parser.parse_args(cli_args)

    lbp_config = load_yaml(args.lbp_config)
    lbp_name = args.lbp_config.stem

    summary_rows: list[dict] = []
    for experiment_path in args.experiment_config:
        experiment_config = load_yaml(experiment_path)
        experiment_name = experiment_path.stem
        run_name = f"{lbp_name}__{experiment_name}"

        run_config = build_run_config(lbp_config, experiment_config)
        stats, elapsed, num_lbp_codes = run_single_experiment(
            run_config,
            run_name=run_name,
            config_source=experiment_path,
            force_visualize=args.visualize,
        )

        row = {
            "run_name": run_name,
            "lbp_config": str(args.lbp_config),
            "experiment_config": str(experiment_path),
            "num_lbp_codes": num_lbp_codes,
            "time_seconds": round(elapsed, 4),
        }
        row.update(stats.as_dict())
        summary_rows.append(row)

    project_root = Path(__file__).resolve().parents[2]
    if args.summary_csv is not None:
        summary_path = args.summary_csv
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_path = project_root / "results" / f"summary_{lbp_name}_{timestamp}.csv"
    write_summary_csv(summary_rows, summary_path)
    print(f"\nSummary of {len(summary_rows)} experiment(s) saved to: {summary_path}")

    if return_results:
        return {"summary_csv": str(summary_path), "experiments": summary_rows}
    return None


if __name__ == "__main__":
    main()
