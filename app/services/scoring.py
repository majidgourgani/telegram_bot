"""Pure scoring helpers — no database access, easy to unit test."""

from __future__ import annotations

from typing import Any


def area_scores_from_answers(
    answers: dict[int, dict[str, Any]],
    questions: list[dict[str, Any]],
    areas: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Average score per area.

    ``answers`` maps question index -> {"label", "score"}; ``questions`` and
    ``areas`` come from a quiz snapshot. Returns a list of
    ``{"slug", "name", "score"}`` in area order, skipping areas with no answers.
    """
    buckets: dict[str, list[int]] = {}
    for index, question in enumerate(questions):
        if index not in answers:
            continue
        buckets.setdefault(question["area_slug"], []).append(answers[index]["score"])

    result: list[dict[str, Any]] = []
    for area in areas:
        values = buckets.get(area["slug"], [])
        if not values:
            continue
        result.append(
            {
                "slug": area["slug"],
                "name": area["name"],
                "score": sum(values) / len(values),
            }
        )
    return result
