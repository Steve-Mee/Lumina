"""Purge + embargo for overlapping labels (López de Prado AFML 7.4 / 12).

Train observation i with label horizon t1[i] is dropped when [i, t1[i]] overlaps
any contiguous test segment, or when i falls in the embargo window immediately
after that segment. Test groups need not be contiguous (CPCV).
"""

from __future__ import annotations

from typing import Sequence


def contiguous_segments(indices: Sequence[int]) -> tuple[tuple[int, int], ...]:
    """Inclusive [start, end] runs of sorted unique indices."""
    if not indices:
        return ()
    ordered = sorted(set(int(value) for value in indices))
    segments: list[tuple[int, int]] = []
    start = prev = ordered[0]
    for value in ordered[1:]:
        if value == prev + 1:
            prev = value
            continue
        segments.append((start, prev))
        start = prev = value
    segments.append((start, prev))
    return tuple(segments)


def purge_train_indices(
    train_index: Sequence[int],
    test_index: Sequence[int],
    t1: Sequence[int],
    embargo: int,
    n_obs: int,
) -> tuple[int, ...]:
    if embargo < 0:
        raise ValueError("embargo must be >= 0")
    if not test_index:
        return tuple(int(index) for index in train_index)
    segments = contiguous_segments(test_index)
    kept: list[int] = []
    for raw in train_index:
        index = int(raw)
        if index < 0 or index >= n_obs:
            continue
        label_end = int(t1[index])
        if label_end < index:
            label_end = index
        drop = False
        for seg_start, seg_end in segments:
            overlaps = index <= seg_end and label_end >= seg_start
            embargo_end = min(n_obs, seg_end + 1 + embargo)
            in_embargo = seg_end < index < embargo_end
            if overlaps or in_embargo:
                drop = True
                break
        if not drop:
            kept.append(index)
    return tuple(kept)
