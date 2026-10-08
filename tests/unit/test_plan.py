from scenewise.domain import plan
from scenewise.domain.jobs import StageName


def test_every_stage_has_a_prerequisite() -> None:
    assert set(plan.PREREQUISITES) == set(StageName)


def test_ordered_puts_producers_first() -> None:
    wanted = [StageName.LABELS, StageName.SUMMARY, StageName.CAPTIONS]
    assert plan.ordered(wanted) == (
        StageName.CAPTIONS,
        StageName.SUMMARY,
        StageName.LABELS,
    )


def test_unavailable() -> None:
    enabled = frozenset({StageName.AUDIO})
    requested = [StageName.CAPTIONS, StageName.AUDIO]
    assert plan.unavailable(requested, enabled) == (StageName.CAPTIONS,)
    assert plan.unavailable([StageName.AUDIO], enabled) == ()
