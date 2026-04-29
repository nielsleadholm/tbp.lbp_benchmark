from collections.abc import Sequence
from dataclasses import dataclass
from .image_data_containers import ImageRecord
import math


@dataclass
class MatchDistanceStats:
    highest_correct: float | None
    lowest_correct: float | None
    highest_incorrect: float | None
    lowest_incorrect: float | None
    average_correct: float | None
    average_incorrect: float | None

    total_matches: int
    total_correct: int
    total_incorrect: int
    percent_correct: float | None

    def __str__(self) -> str:
        lines = [
            f"Total matches: {self.total_matches}",
            f"Total correct: {self.total_correct}",
            f"Total incorrect: {self.total_incorrect}",
            f"Percent correct: {self.percent_correct:.2f}%" if self.percent_correct is not None else "Percent correct: N/A",
            f"Highest distance among correct matches: {self.highest_correct:.6f}" if self.highest_correct is not None else "Highest distance among correct matches: N/A",
            f"Lowest distance among correct matches: {self.lowest_correct:.6f}" if self.lowest_correct is not None else "Lowest distance among correct matches: N/A",
            f"Average distance among correct matches: {self.average_correct:.6f}" if self.average_correct is not None else "Average distance among correct matches: N/A",
            f"Highest distance among incorrect matches: {self.highest_incorrect:.6f}" if self.highest_incorrect is not None else "Highest distance among incorrect matches: N/A",
            f"Lowest distance among incorrect matches: {self.lowest_incorrect:.6f}" if self.lowest_incorrect is not None else "Lowest distance among incorrect matches: N/A",
            f"Average distance among incorrect matches: {self.average_incorrect:.6f}" if self.average_incorrect is not None else "Average distance among incorrect matches: N/A",
        ]
        return "\n".join(lines)


def compute_match_distance_stats(
    image_records: Sequence[ImageRecord],
) -> MatchDistanceStats:
    correct_distances: list[float] = []
    incorrect_distances: list[float] = []

    total_matches = 0
    total_correct = 0
    total_incorrect = 0

    for image_record in image_records:
        for match_record in image_record.match_records:
            distance = match_record.nn_distance
            is_correct = match_record.correct

            # skip incomplete records
            if distance is None or is_correct is None or math.isnan(distance):
                continue

            total_matches += 1

            if is_correct:
                total_correct += 1
                correct_distances.append(distance)
            else:
                total_incorrect += 1
                incorrect_distances.append(distance)

    percent_correct = (
        (total_correct / total_matches) * 100.0
        if total_matches > 0
        else None
    )

    return MatchDistanceStats(
        highest_correct=max(correct_distances) if correct_distances else None,
        lowest_correct=min(correct_distances) if correct_distances else None,
        highest_incorrect=max(incorrect_distances) if incorrect_distances else None,
        lowest_incorrect=min(incorrect_distances) if incorrect_distances else None,
        average_correct=(
            sum(correct_distances) / len(correct_distances)
            if correct_distances
            else None
        ),
        average_incorrect=(
            sum(incorrect_distances) / len(incorrect_distances)
            if incorrect_distances
            else None
        ),
        total_matches=total_matches,
        total_correct=total_correct,
        total_incorrect=total_incorrect,
        percent_correct=percent_correct,
    )