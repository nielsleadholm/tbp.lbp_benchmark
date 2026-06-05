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

import matplotlib

matplotlib.use("Agg")  # Safe default for headless / scripted plotting.
import matplotlib.pyplot as plt


# Default location to search for summary CSVs when none are provided.
DEFAULT_RESULTS_DIR = Path("results")
DEFAULT_SUMMARY_GLOB = "summary_*.csv"


class ExperimentRecord:
    """A single (lbp_config, experiment_config) result parsed from a summary CSV."""

    def __init__(
        self,
        lbp_label: str,
        experiment_label: str,
        percent_correct: Optional[float],
        num_lbp_codes: Optional[int],
        source: Path,
    ) -> None:
        self.lbp_label = lbp_label
        self.experiment_label = experiment_label
        self.percent_correct = percent_correct
        self.num_lbp_codes = num_lbp_codes
        self.source = source


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


def plot_accuracy(
    records: Sequence[ExperimentRecord],
    output_path: Path,
    title: str = "LBP accuracy across experiment conditions",
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

    cmap = plt.get_cmap("tab10")
    fig, ax = plt.subplots(figsize=(max(7, 1.8 * num_groups + 2), 5.5))

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
            color=cmap(series_idx % 10),
            edgecolor="white",
            linewidth=0.5,
        )
        ax.bar_label(bars, fmt="%.0f", padding=2, fontsize=8)

    ax.set_xticks(x_positions)
    ax.set_xticklabels([_humanize(e) for e in exp_labels])
    ax.set_ylabel("Accuracy (% correct matches)")
    ax.set_xlabel("Experiment condition")
    ax.set_ylim(0, 105)
    ax.set_title(title)
    ax.legend(title="LBP configuration", frameon=False)
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    ax.set_axisbelow(True)
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
    cmap = plt.get_cmap("tab10")
    colors = [cmap(i % 10) for i in range(len(lbp_labels))]

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

    accuracy_path = plot_accuracy(
        records,
        args.output_dir / args.accuracy_filename,
        title=args.accuracy_title,
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
