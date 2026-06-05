"""Plot accuracy and LBP-code-count comparisons across LBP configs / experiments.

This consumes the aggregate summary CSV files produced by ``main.py`` (one per
``run.py`` invocation). Each summary CSV holds one row per experiment with the
columns ``lbp_config``, ``experiment_config``, ``num_lbp_codes`` and
``percent_correct`` (among others), which is everything the plots below need.

Typical workflow::

    # One run per LBP config, each evaluated on increasingly challenging conditions.
    python run.py --lbp-config config/lbp/default_lbp.yaml \
        --experiment-config config/experiments/clean.yaml \
            config/experiments/noisy_inputs.yaml config/experiments/illumination.yaml

    python run.py --lbp-config config/lbp/ltp_ror_multiscale.yaml \
        --experiment-config config/experiments/clean.yaml \
            config/experiments/noisy_inputs.yaml config/experiments/illumination.yaml

    # Then plot every summary found in results/ (or pass explicit CSV paths).
    python plot_results.py
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import yaml
from PIL import Image

import matplotlib

matplotlib.use("Agg")  # Safe default for headless / scripted plotting.
import matplotlib.pyplot as plt

from .image_processing import apply_PIL_processing, apply_numpy_processing


# Default location to search for summary CSVs when none are provided.
DEFAULT_RESULTS_DIR = Path("results")
DEFAULT_SUMMARY_GLOB = "summary_*.csv"

# Project root (…/tbp.lbp_benchmark), used to resolve config/dataset paths that
# are stored relative to it inside the summary CSVs.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Brand color palette, used in preference order (blue first, then pink, ...).
PALETTE = (
    "#00a0df",  # blue
    "#f737bd",  # pink
    "#5d11bf",  # purple
    "#ffbe31",  # gold
    "#008e43",  # green
)

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tiff")


def _color(index: int):
    """Return the palette color for a series, cycling if there are more than 5."""
    return PALETTE[index % len(PALETTE)]


class ExperimentRecord:
    """A single (lbp_config, experiment_config) result parsed from a summary CSV."""

    def __init__(
        self,
        lbp_label: str,
        experiment_label: str,
        percent_correct: Optional[float],
        num_lbp_codes: Optional[int],
        source: Path,
        experiment_config_path: str = "",
    ) -> None:
        self.lbp_label = lbp_label
        self.experiment_label = experiment_label
        self.percent_correct = percent_correct
        self.num_lbp_codes = num_lbp_codes
        self.source = source
        # Raw experiment-config path from the CSV, kept so we can render a
        # perturbation preview for each condition.
        self.experiment_config_path = experiment_config_path


def _label_from_path(raw: str) -> str:
    """Turn a config path (or already-bare name) into a short, human label."""
    if not raw:
        return "unknown"
    return Path(raw).stem


def _humanize(label: str) -> str:
    """Make a label nicer for axis ticks / legends (``noisy_inputs`` -> ``Noisy Inputs``)."""
    return label.replace("_", " ").strip().title()


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Optional[str]) -> Optional[int]:
    as_float = _to_float(value)
    return int(round(as_float)) if as_float is not None else None


def resolve_summary_files(inputs: Sequence[Path]) -> list[Path]:
    """Expand the CLI inputs into a concrete, de-duplicated list of summary CSV files.

    Inputs may be individual CSV files or directories (searched for
    ``summary_*.csv``). When no inputs are given, ``results/`` is searched.
    """
    if not inputs:
        inputs = [DEFAULT_RESULTS_DIR]

    files: list[Path] = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            files.extend(sorted(path.glob(DEFAULT_SUMMARY_GLOB)))
        elif path.is_file():
            files.append(path)
        else:
            # Treat as a glob pattern relative to the current directory.
            matches = sorted(Path().glob(str(path)))
            if not matches:
                raise FileNotFoundError(f"No summary CSV found for input: {item}")
            files.extend(matches)

    # De-duplicate while preserving order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(f)
    if not unique:
        raise FileNotFoundError(
            "No summary CSV files found. Run an experiment first (see run.py) "
            f"or point this script at one or more '{DEFAULT_SUMMARY_GLOB}' files."
        )
    return unique


def read_records(summary_files: Sequence[Path]) -> list[ExperimentRecord]:
    """Read every row from the given summary CSVs into ``ExperimentRecord`` objects."""
    records: list[ExperimentRecord] = []
    for summary_file in summary_files:
        with open(summary_file, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                lbp_raw = row.get("lbp_config") or row.get("run_name", "")
                exp_raw = row.get("experiment_config", "")
                # Fall back to splitting run_name ("<lbp>__<experiment>") if needed.
                if not exp_raw and "__" in row.get("run_name", ""):
                    lbp_part, _, exp_part = row["run_name"].partition("__")
                    lbp_raw = lbp_raw or lbp_part
                    exp_raw = exp_part
                records.append(
                    ExperimentRecord(
                        lbp_label=_label_from_path(lbp_raw),
                        experiment_label=_label_from_path(exp_raw),
                        percent_correct=_to_float(row.get("percent_correct")),
                        num_lbp_codes=_to_int(row.get("num_lbp_codes")),
                        source=summary_file,
                        experiment_config_path=row.get("experiment_config", "") or "",
                    )
                )
    if not records:
        raise ValueError("Summary CSV files contained no experiment rows.")
    return records


def _ordered_unique(values: Sequence[str]) -> list[str]:
    """Unique values in first-seen order (experiments are run worst-last, so order matters)."""
    seen: set[str] = set()
    ordered: list[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            ordered.append(v)
    return ordered


def _resolve_existing_path(raw: str) -> Optional[Path]:
    """Resolve a (possibly relative) path from a summary CSV to an existing file/dir.

    Summary CSVs store config and dataset paths relative to either the current
    working directory or the project root, so both are tried.
    """
    if not raw:
        return None
    candidates = [Path(raw), Path.cwd() / raw, PROJECT_ROOT / raw]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _list_image_files(folder: Path) -> list[Path]:
    return sorted(
        p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
    )


def _select_example_files(
    image_files: Sequence[Path],
    count: int,
    example_name: Optional[str],
) -> list[Path]:
    """Pick ``count`` example images (deterministically), optionally pinning one.

    Files are sorted, so the same images are chosen across conditions that share a
    target folder; the only visible difference between conditions is then the
    perturbation itself.
    """
    chosen: list[Path] = []
    if example_name is not None:
        for candidate in image_files:
            if candidate.stem == example_name or candidate.name == example_name:
                chosen.append(candidate)
                break
    for candidate in image_files:
        if len(chosen) >= count:
            break
        if candidate not in chosen:
            chosen.append(candidate)
    return chosen[:count]


def load_condition_previews(
    experiment_config_path: str,
    example_name: Optional[str] = None,
    count: int = 2,
    size: tuple[int, int] = (128, 128),
) -> list[Image.Image]:
    """Render ``count`` target-dataset textures with a condition's perturbations applied.

    This mirrors what the interactive ``--visualize`` tool shows: each example
    image is run through the same ``query_image_processing`` pipeline used during
    matching, giving a viewer an intuition for how strong each perturbation is.

    Returns an empty list (with a warning) if the config or dataset can't be
    located, so a single missing preview never breaks the whole plot.
    """
    config_path = _resolve_existing_path(experiment_config_path)
    if config_path is None:
        print(f"[warning] Could not locate experiment config: {experiment_config_path!r}")
        return []

    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}

    target_folder_raw = config.get("data", {}).get("target_images_folder", "")
    target_folder = _resolve_existing_path(target_folder_raw)
    if target_folder is None or not target_folder.is_dir():
        print(f"[warning] Could not locate target images folder: {target_folder_raw!r}")
        return []

    image_files = _list_image_files(target_folder)
    if not image_files:
        print(f"[warning] No images found in target folder: {target_folder}")
        return []

    processing_config = config.get("query_image_processing")
    if processing_config is None:
        print(f"[warning] No 'query_image_processing' section in {config_path}")
        return []

    seed = config.get("rng", {}).get("seed", 0)
    chosen_files = _select_example_files(image_files, count, example_name)

    previews: list[Image.Image] = []
    for chosen in chosen_files:
        # Re-seed per example so each renders deterministically, while still
        # giving distinct random crops/noise across the different textures.
        rng = np.random.default_rng(seed=seed)
        image = Image.open(chosen).convert("RGB")
        image = apply_PIL_processing(image, processing_config, rng=rng)
        processed_array = apply_numpy_processing(image, processing_config, rng=rng)
        preview = Image.fromarray(processed_array)
        preview.thumbnail(size)
        previews.append(preview)
    return previews


def build_condition_previews(
    records: Sequence[ExperimentRecord],
    example_name: Optional[str] = None,
    count: int = 2,
    size: tuple[int, int] = (128, 128),
) -> dict[str, list[Image.Image]]:
    """Build ``count`` perturbation previews per experiment condition (first-seen config)."""
    config_by_label: dict[str, str] = {}
    for r in records:
        if r.experiment_label not in config_by_label and r.experiment_config_path:
            config_by_label[r.experiment_label] = r.experiment_config_path

    previews: dict[str, list[Image.Image]] = {}
    for label, config_path in config_by_label.items():
        previews[label] = load_condition_previews(
            config_path, example_name=example_name, count=count, size=size
        )
    return previews


def _add_condition_previews(
    fig,
    ax,
    experiment_labels: Sequence[str],
    previews: dict[str, list[Image.Image]],
) -> None:
    """Stack the perturbed-texture example thumbnails beneath each x-axis condition."""
    num_groups = len(experiment_labels)
    if num_groups == 0:
        return

    # Number of examples to stack per column (max across conditions).
    rows = max((len(previews.get(label, [])) for label in experiment_labels), default=0)
    if rows == 0:
        return

    pos = ax.get_position()
    fig_w_in, fig_h_in = fig.get_size_inches()
    fig_aspect = fig_w_in / fig_h_in

    gap = 0.008  # vertical gap (figure fraction) between stacked thumbnails
    group_width_fig = pos.width / num_groups
    # The whole stack must fit in the reserved bottom margin, leaving room below
    # the axis tick labels (top) and the x-axis caption (bottom).
    available_height = max(pos.y0 - 0.12, 0.05)

    # Size a single thumbnail so the stack fits both vertically and within a
    # column, keeping each thumbnail square in display space.
    thumb_h = (available_height - (rows - 1) * gap) / rows
    thumb_w = thumb_h / fig_aspect
    if thumb_w > 0.9 * group_width_fig:
        thumb_w = 0.9 * group_width_fig
        thumb_h = thumb_w * fig_aspect

    stack_height = rows * thumb_h + (rows - 1) * gap
    stack_top = pos.y0 - 0.035
    stack_bottom = max(0.06, stack_top - stack_height)

    for i, label in enumerate(experiment_labels):
        column_previews = previews.get(label, [])
        if not column_previews:
            continue
        center_x = pos.x0 + (i + 0.5) / num_groups * pos.width
        for row_idx, preview in enumerate(column_previews):
            # Row 0 sits at the top of the stack, just under the tick label.
            thumb_bottom = stack_top - (row_idx + 1) * thumb_h - row_idx * gap
            thumb_ax = fig.add_axes(
                [center_x - thumb_w / 2, thumb_bottom, thumb_w, thumb_h]
            )
            thumb_ax.imshow(preview)
            thumb_ax.set_xticks([])
            thumb_ax.set_yticks([])
            for spine in thumb_ax.spines.values():
                spine.set_edgecolor("#444444")
                spine.set_linewidth(0.8)

    # Add the x-axis label beneath the thumbnail stack.
    fig.text(
        pos.x0 + pos.width / 2,
        max(0.02, stack_bottom - 0.03),
        "Experiment condition (example perturbed textures shown below each)",
        ha="center",
        va="top",
    )


def plot_accuracy(
    records: Sequence[ExperimentRecord],
    output_path: Path,
    title: str = "LBP accuracy across experiment conditions",
    previews: Optional[dict[str, list[Image.Image]]] = None,
) -> Path:
    """Grouped bar plot: x = experiment condition, color = LBP config, y = accuracy (%)."""
    lbp_labels = _ordered_unique([r.lbp_label for r in records])
    exp_labels = _ordered_unique([r.experiment_label for r in records])

    # Index accuracy by (lbp, experiment) for quick lookup.
    accuracy: dict[tuple[str, str], Optional[float]] = {}
    for r in records:
        accuracy[(r.lbp_label, r.experiment_label)] = r.percent_correct

    num_groups = len(exp_labels)
    num_series = len(lbp_labels)
    group_width = 0.8
    bar_width = group_width / max(num_series, 1)
    x_positions = list(range(num_groups))

    has_previews = bool(previews) and any(
        previews.get(label) for label in exp_labels
    )
    # Tallest preview stack across conditions, used to size the bottom margin.
    preview_rows = (
        max((len(previews.get(label, [])) for label in exp_labels), default=0)
        if previews
        else 0
    )

    # Give a taller figure (and more reserved bottom space) when stacking
    # multiple example thumbnails under each column.
    fig_height = 6.5 + 0.9 * max(preview_rows - 1, 0)
    fig, ax = plt.subplots(figsize=(max(7, 1.8 * num_groups + 2), fig_height))

    for series_idx, lbp_label in enumerate(lbp_labels):
        heights = [
            accuracy.get((lbp_label, exp_label)) or 0.0 for exp_label in exp_labels
        ]
        offsets = [
            x + series_idx * bar_width - group_width / 2 + bar_width / 2
            for x in x_positions
        ]
        bars = ax.bar(
            offsets,
            heights,
            width=bar_width,
            label=_humanize(lbp_label),
            color=_color(series_idx),
            edgecolor="white",
            linewidth=0.5,
        )
        ax.bar_label(bars, fmt="%.0f", padding=2, fontsize=8)

    ax.set_xticks(x_positions)
    ax.set_xticklabels([_humanize(e) for e in exp_labels])
    ax.set_xlim(-0.5, num_groups - 0.5)
    ax.set_ylabel("Accuracy (% correct matches)")
    # When previews are drawn the x-axis label is added beneath the thumbnail
    # row (see _add_condition_previews) to avoid overlapping the images.
    if not has_previews:
        ax.set_xlabel("Experiment condition")
    ax.set_ylim(0, 105)
    ax.set_title(title)
    ax.legend(title="LBP configuration", frameon=False)
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    ax.set_axisbelow(True)

    if has_previews:
        # Reserve the bottom portion of the figure for the preview thumbnails;
        # more rows of examples need a larger reserved margin.
        bottom_margin = min(0.5, 0.26 + 0.14 * max(preview_rows - 1, 0))
        fig.tight_layout(rect=(0, bottom_margin, 1, 1))
        _add_condition_previews(fig, ax, exp_labels, previews)
    else:
        fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    return output_path


def plot_lbp_code_counts(
    records: Sequence[ExperimentRecord],
    output_path: Path,
    title: str = "Number of LBP codes per configuration",
) -> Path:
    """Supplementary bar plot: one bar per LBP config showing its feature-vector length."""
    lbp_labels = _ordered_unique([r.lbp_label for r in records])

    # num_lbp_codes is fixed per LBP config; take the first non-null value seen.
    codes_by_lbp: dict[str, Optional[int]] = {}
    for r in records:
        if r.num_lbp_codes is not None and codes_by_lbp.get(r.lbp_label) is None:
            codes_by_lbp[r.lbp_label] = r.num_lbp_codes

    heights = [codes_by_lbp.get(lbp) or 0 for lbp in lbp_labels]
    x_positions = list(range(len(lbp_labels)))
    colors = [_color(i) for i in range(len(lbp_labels))]

    fig, ax = plt.subplots(figsize=(max(6, 1.6 * len(lbp_labels) + 2), 5.5))
    bars = ax.bar(
        x_positions,
        heights,
        width=0.6,
        color=colors,
        edgecolor="white",
        linewidth=0.5,
    )
    ax.bar_label(bars, fmt="%d", padding=2, fontsize=9)

    ax.set_xticks(x_positions)
    ax.set_xticklabels([_humanize(lbp) for lbp in lbp_labels])
    ax.set_ylabel("Number of LBP codes (feature-vector length)")
    ax.set_xlabel("LBP configuration")
    ax.set_title(title)
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    ax.set_axisbelow(True)
    if heights:
        ax.set_ylim(0, max(heights) * 1.15 + 1)
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    return output_path


def main(cli_args: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Plot LBP benchmarking results. Reads the aggregate summary CSV(s) "
            "produced by run.py and renders an accuracy comparison plus a "
            "supplementary plot of the number of LBP codes per configuration."
        )
    )
    parser.add_argument(
        "summaries",
        nargs="*",
        type=Path,
        help=(
            "Summary CSV files (or directories containing 'summary_*.csv'). "
            "Defaults to searching the 'results/' directory."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR / "plots",
        help="Directory to write the plot images to (default: results/plots).",
    )
    parser.add_argument(
        "--accuracy-filename",
        default="accuracy_comparison.png",
        help="Filename for the accuracy bar plot.",
    )
    parser.add_argument(
        "--codes-filename",
        default="lbp_code_counts.png",
        help="Filename for the supplementary LBP-code-count bar plot.",
    )
    parser.add_argument(
        "--accuracy-title",
        default="LBP accuracy across experiment conditions",
        help="Title for the accuracy plot.",
    )
    parser.add_argument(
        "--codes-title",
        default="Number of LBP codes per configuration",
        help="Title for the LBP-code-count plot.",
    )
    parser.add_argument(
        "--no-previews",
        action="store_true",
        help=(
            "Disable the perturbed-texture preview thumbnails beneath the "
            "accuracy plot's x-axis."
        ),
    )
    parser.add_argument(
        "--preview-example",
        default=None,
        help=(
            "Name (or stem) of the target-dataset image to use as the first "
            "preview thumbnail. Defaults to the first image in the target folder."
        ),
    )
    parser.add_argument(
        "--preview-count",
        type=int,
        default=2,
        help=(
            "Number of example perturbed textures to stack beneath each "
            "condition (default: 2)."
        ),
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the plots interactively in addition to saving them.",
    )

    args = parser.parse_args(cli_args)

    summary_files = resolve_summary_files(args.summaries)
    print("Reading summary CSV(s):")
    for f in summary_files:
        print(f"  - {f}")

    records = read_records(summary_files)

    previews = None
    if not args.no_previews:
        previews = build_condition_previews(
            records,
            example_name=args.preview_example,
            count=max(1, args.preview_count),
        )

    accuracy_path = plot_accuracy(
        records,
        args.output_dir / args.accuracy_filename,
        title=args.accuracy_title,
        previews=previews,
    )
    codes_path = plot_lbp_code_counts(
        records,
        args.output_dir / args.codes_filename,
        title=args.codes_title,
    )

    print(f"\nSaved accuracy plot to:        {accuracy_path}")
    print(f"Saved LBP-code-count plot to:  {codes_path}")

    if args.show:
        # Switch to an interactive backend only if the user asks to display.
        import matplotlib.pyplot as interactive_plt

        interactive_plt.show()


if __name__ == "__main__":
    main()
