"""Tag matching utilities using Levenshtein distance."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import Levenshtein


if TYPE_CHECKING:
    import polars as pl


@dataclass
class TagMatch:
    """Represents a potential match between CE and Stashapp tags."""

    ce_uuid: str
    ce_name: str
    stashapp_id: int
    stashapp_name: str
    stashdb_id: str | None
    distance: int
    similarity: float


def normalize_tag_name(name: str) -> str:
    """Normalize tag name for matching.

    Args:
        name: Tag name to normalize

    Returns:
        Normalized tag name (lowercase, no spaces/special chars)
    """
    return name.lower().replace(" ", "").replace("-", "").replace("_", "")


def calculate_similarity(name1: str, name2: str) -> tuple[int, float]:
    """Calculate Levenshtein distance and similarity ratio between two tag names.

    Args:
        name1: First tag name
        name2: Second tag name

    Returns:
        Tuple of (distance, similarity_ratio) where similarity_ratio is between 0 and 1
    """
    norm1 = normalize_tag_name(name1)
    norm2 = normalize_tag_name(name2)

    distance = Levenshtein.distance(norm1, norm2)
    similarity = Levenshtein.ratio(norm1, norm2)

    return distance, similarity


def find_tag_matches(
    ce_tags: pl.DataFrame,
    stashapp_tags: pl.DataFrame,
    threshold: float = 0.85,
    max_distance: int | None = None,
) -> list[TagMatch]:
    """Find potential matches between CE and Stashapp tags using Levenshtein distance.

    Args:
        ce_tags: DataFrame with CE tags (columns: ce_tags_uuid, ce_tags_name)
        stashapp_tags: DataFrame with Stashapp tags (columns: id, name, stashdb_id)
        threshold: Minimum similarity ratio (0-1) for a match (default: 0.85)
        max_distance: Maximum Levenshtein distance for a match (optional)

    Returns:
        List of TagMatch objects sorted by similarity (highest first)
    """
    matches = []

    # Convert to Python lists for iteration
    ce_tags_list = ce_tags.select(["ce_tags_uuid", "ce_tags_name"]).to_dicts()
    stashapp_tags_list = stashapp_tags.select(["id", "name", "stashdb_id"]).to_dicts()

    for ce_tag in ce_tags_list:
        ce_uuid = ce_tag["ce_tags_uuid"]
        ce_name = ce_tag["ce_tags_name"]

        for stash_tag in stashapp_tags_list:
            stash_id = stash_tag["id"]
            stash_name = stash_tag["name"]
            stashdb_id = stash_tag.get("stashdb_id")

            distance, similarity = calculate_similarity(ce_name, stash_name)

            # Check if match meets criteria
            if similarity >= threshold and (max_distance is None or distance <= max_distance):
                matches.append(
                    TagMatch(
                        ce_uuid=ce_uuid,
                        ce_name=ce_name,
                        stashapp_id=stash_id,
                        stashapp_name=stash_name,
                        stashdb_id=stashdb_id,
                        distance=distance,
                        similarity=similarity,
                    )
                )

    # Sort by similarity (highest first), then by distance (lowest first)
    matches.sort(key=lambda x: (-x.similarity, x.distance))

    return matches


def find_best_match_for_tag(
    ce_tag_name: str,
    stashapp_tags: pl.DataFrame,
    threshold: float = 0.85,
) -> TagMatch | None:
    """Find the best match for a single CE tag.

    Args:
        ce_tag_name: CE tag name to match
        stashapp_tags: DataFrame with Stashapp tags
        threshold: Minimum similarity ratio for a match

    Returns:
        Best TagMatch or None if no match found
    """
    stashapp_tags_list = stashapp_tags.select(["id", "name", "stashdb_id"]).to_dicts()

    best_match = None
    best_similarity = 0.0

    for stash_tag in stashapp_tags_list:
        stash_id = stash_tag["id"]
        stash_name = stash_tag["name"]
        stashdb_id = stash_tag.get("stashdb_id")

        distance, similarity = calculate_similarity(ce_tag_name, stash_name)

        if similarity >= threshold and similarity > best_similarity:
            best_similarity = similarity
            best_match = TagMatch(
                ce_uuid="",  # Will be filled in by caller
                ce_name=ce_tag_name,
                stashapp_id=stash_id,
                stashapp_name=stash_name,
                stashdb_id=stashdb_id,
                distance=distance,
                similarity=similarity,
            )

    return best_match
