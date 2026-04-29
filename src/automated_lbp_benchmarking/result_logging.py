from PIL import Image
import csv
from pathlib import Path
from typing import Sequence
from .image_data_containers import ImageRecord
from datetime import datetime

def save_matches_csv(records: Sequence[ImageRecord], out_path: str) -> None:
    # Find root project director (hardcoded, probably shouldn't do this)
    project_root = Path(__file__).resolve().parents[2]

    # Build results directory path
    results_dir = project_root / "results"
    results_dir.mkdir(exist_ok=True)

    # Use the provided out_path as the filename, only add timestamp if not specified
    if out_path.endswith('.csv'):
        output_path = results_dir / out_path
    else:
        # If not a csv, add timestamp
        out_path = out_path + "_" + datetime.now().strftime("%Y%m%d_%H%M%S_") + ".csv"
        output_path = results_dir / out_path
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Index", "Instance", "Category", "Distance", "Matched_Category", "Matched_Index", "Correct"])
        for r in records:
            writer.writerow([
                r.index,
                r.instance,
                r.category,
                r.distance,
                r.matched_category,
                r.matched_index,
                bool(r.correct),
            ])

def print_verbose_report(records: Sequence[ImageRecord]) -> None:
    total = len(records)
    correct_count = 0
    all_correct_distances = []
    all_incorrect_distances = []
    lowest_correct = float("inf")
    lowest_incorrect = float("inf")
    highest_correct = float("-inf")
    highest_incorrect = float("-inf")

    for r in records:
        # Use all shown matches if available (tolerance/top), else fallback to nn_distance
        if hasattr(r, "matching_distances") and r.matching_distances:
            # Try to get categories for each match
            match_cats = getattr(r, "matching_categories", [])
            for idx, dist in enumerate(r.matching_distances):
                # Determine if this match is correct
                cat = match_cats[idx] if idx < len(match_cats) else None
                is_correct = (cat == r.category)
                if is_correct:
                    all_correct_distances.append(dist)
                    highest_correct = max(highest_correct, dist)
                    lowest_correct = min(lowest_correct, dist)
                    correct_count += 1
                else:
                    all_incorrect_distances.append(dist)
                    highest_incorrect = max(highest_incorrect, dist)
                    lowest_incorrect = min(lowest_incorrect, dist)
        elif r.nn_distance is not None:
            # Fallback: single match
            if bool(r.correct):
                all_correct_distances.append(r.nn_distance)
                highest_correct = max(highest_correct, r.nn_distance)
                lowest_correct = min(lowest_correct, r.nn_distance)
                correct_count += 1
            else:
                all_incorrect_distances.append(r.nn_distance)
                highest_incorrect = max(highest_incorrect, r.nn_distance)
                lowest_incorrect = min(lowest_incorrect, r.nn_distance)

    avg_correct = float(np.mean(all_correct_distances)) if all_correct_distances else None
    avg_incorrect = float(np.mean(all_incorrect_distances)) if all_incorrect_distances else None

    summary_lines = []
    pct = 100.0 * correct_count / (len(all_correct_distances) + len(all_incorrect_distances)) if (len(all_correct_distances) + len(all_incorrect_distances)) else 0.0
    summary_lines.append(f"Correct matches: {correct_count}/{len(all_correct_distances) + len(all_incorrect_distances)} ({pct:.2f}%)")
    summary_lines.append(f"Highest distance among correct matches: {highest_correct:.6f}" if highest_correct != float("-inf") else
          "Highest distance among correct matches: N/A")
    summary_lines.append(f"Lowest distance among correct matches: {lowest_correct:.6f}" if lowest_correct != float("inf") else
          "Lowest distance among correct matches: N/A")
    summary_lines.append(f"Average distance among correct matches: {avg_correct:.6f}" if avg_correct is not None else "Average distance among correct matches: N/A")
    summary_lines.append(f"Highest distance among incorrect matches: {highest_incorrect:.6f}" if highest_incorrect != float("-inf") else
          "Highest distance among incorrect matches: N/A")
    summary_lines.append(f"Lowest distance among incorrect matches: {lowest_incorrect:.6f}" if lowest_incorrect != float("inf") else
          "Lowest distance among incorrect matches: N/A")
    summary_lines.append(f"Average distance among incorrect matches: {avg_incorrect:.6f}" if avg_incorrect is not None else "Average distance among incorrect matches: N/A")

    for line in summary_lines:
        print(line)

    # Return a standardized results dict for automation
    results = {
        "correct_matches": int(correct_count),
        "total": int(len(all_correct_distances) + len(all_incorrect_distances)),
        "pct_correct": float(pct),
        "highest_correct": float(highest_correct) if highest_correct != float("-inf") else None,
        "lowest_correct": float(lowest_correct) if lowest_correct != float("inf") else None,
        "average_correct": avg_correct,
        "highest_incorrect": float(highest_incorrect) if highest_incorrect != float("-inf") else None,
        "lowest_incorrect": float(lowest_incorrect) if lowest_incorrect != float("inf") else None,
        "average_incorrect": avg_incorrect,
    }
    return summary_lines, results