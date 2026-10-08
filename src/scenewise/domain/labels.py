"""Zero-shot label scores (q8c §4.1); selection and calibration arrive with item 4."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class LabelScores:
    """Raw output of one labelling pass over a batch of frames."""

    model_id: str
    preprocess: str
    cosines: tuple[tuple[float, ...], ...]  # [frame][label]
    score_transform: tuple[float, float] | None  # (logit_scale, logit_bias)
    embeddings: tuple[tuple[float, ...], ...] | None  # [frame], L2-normalised
