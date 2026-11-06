"""The checkpoint builder: fixed examples plus properties checked on random inputs.
# covers: REQ-12
"""

from collections import Counter

from hypothesis import given, settings
from hypothesis import strategies as st

from careerpilot.modules.learn.checkpoint import KIND_OF, Candidate, Spec, build
from careerpilot.modules.learn.enums import QuestionType

TYPES = list(QuestionType)


def pool(topics: int, per_topic: int, types: list[QuestionType] | None = None) -> list[Candidate]:
    types = types or [QuestionType.MCQ_SINGLE]
    return [
        Candidate(f"q{t}-{i}", f"t{t}", types[(t + i) % len(types)], difficulty=1 + i % 5)
        for t in range(topics)
        for i in range(per_topic)
    ]


def test_builds_requested_size_without_repeats() -> None:
    built = build(pool(4, 10), Spec(size=12, seed=1))
    assert len(built.question_ids) == 12
    assert len(set(built.question_ids)) == 12
    assert built.shortfall == 0


def test_every_topic_is_covered_when_there_is_room() -> None:
    built = build(pool(5, 8), Spec(size=10, seed=3))
    assert set(built.per_topic) == {f"t{i}" for i in range(5)}


def test_weights_shift_the_share() -> None:
    built = build(pool(2, 20), Spec(size=20, seed=0, topic_weights={"t0": 3.0, "t1": 1.0}))
    assert built.per_topic["t0"] > built.per_topic["t1"]
    assert built.per_topic["t0"] + built.per_topic["t1"] == 20


def test_never_more_than_a_topic_has() -> None:
    built = build(pool(2, 3) + pool(1, 30)[:0], Spec(size=6, seed=0))
    assert built.per_topic == {"t0": 3, "t1": 3}


def test_short_supply_reports_the_shortfall_in_plain_words() -> None:
    built = build(pool(2, 2), Spec(size=10))
    assert len(built.question_ids) == 4
    assert built.shortfall == 6
    assert any("short of the 10" in note for note in built.notes)


def test_fewer_slots_than_topics_gives_the_heaviest_topics_one_each() -> None:
    built = build(pool(5, 4), Spec(size=2, topic_weights={"t3": 5.0, "t1": 4.0}))
    assert set(built.per_topic) == {"t3", "t1"}


def test_recently_seen_questions_are_avoided_when_there_are_enough_others() -> None:
    items = [
        Candidate(f"old{i}", "t0", QuestionType.MCQ_SINGLE, seen_days_ago=1) for i in range(5)
    ] + [Candidate(f"new{i}", "t0", QuestionType.MCQ_SINGLE) for i in range(5)]
    built = build(items, Spec(size=5, seed=0))
    assert all(q.startswith("new") for q in built.question_ids)


def test_recent_questions_are_used_only_to_fill_the_gap_and_a_note_says_so() -> None:
    items = [
        Candidate(f"old{i}", "t0", QuestionType.MCQ_SINGLE, seen_days_ago=2) for i in range(5)
    ] + [Candidate("new0", "t0", QuestionType.MCQ_SINGLE)]
    built = build(items, Spec(size=4, seed=0))
    assert "new0" in built.question_ids
    assert any("recently" in note for note in built.notes)


def test_type_mix_is_followed_when_supply_allows() -> None:
    items = pool(3, 12, [QuestionType.MCQ_SINGLE, QuestionType.SHORT, QuestionType.PRACTICAL])
    built = build(
        items, Spec(size=20, seed=5, mix={"choice": 0.5, "written": 0.3, "practical": 0.2})
    )
    kinds = Counter(KIND_OF[next(c.type for c in items if c.id == q)] for q in built.question_ids)
    assert kinds["choice"] == 10
    assert kinds["written"] == 6
    assert kinds["practical"] == 4


def test_same_seed_same_exam_and_different_seed_different_order() -> None:
    items = pool(4, 10)
    a = build(items, Spec(size=12, seed=7))
    b = build(items, Spec(size=12, seed=7))
    c = build(items, Spec(size=12, seed=8))
    assert a == b
    assert a.question_ids != c.question_ids


def test_input_order_does_not_matter() -> None:
    items = pool(4, 6)
    forward = build(items, Spec(size=10, seed=2))
    backward = build(list(reversed(items)), Spec(size=10, seed=2))
    assert forward == backward


def test_duplicate_ids_are_ignored() -> None:
    items = pool(1, 3) * 2
    built = build(items, Spec(size=6))
    assert sorted(built.question_ids) == ["q0-0", "q0-1", "q0-2"]


def test_empty_pool_builds_nothing() -> None:
    built = build([], Spec(size=5))
    assert built.question_ids == []
    assert built.shortfall == 5


candidates = st.lists(
    st.builds(
        Candidate,
        id=st.text(alphabet="abcdefgh0123456789", min_size=1, max_size=4),
        topic_id=st.sampled_from(["t0", "t1", "t2", "t3"]),
        type=st.sampled_from(TYPES),
        difficulty=st.integers(1, 5),
        seen_days_ago=st.one_of(st.none(), st.integers(0, 30)),
    ),
    max_size=40,
)


@settings(max_examples=200, deadline=None)
@given(
    items=candidates, size=st.integers(1, 30), seed=st.integers(0, 1000), avoid=st.integers(0, 14)
)
def test_properties(items: list[Candidate], size: int, seed: int, avoid: int) -> None:
    built = build(items, Spec(size=size, seed=seed, avoid_days=avoid))
    ids = {c.id for c in items}
    # Only real candidates, no repeats, never more than asked for or available.
    assert set(built.question_ids) <= ids
    assert len(set(built.question_ids)) == len(built.question_ids)
    assert len(built.question_ids) <= min(size, len(ids))
    # Reported numbers agree with the result.
    assert built.shortfall == size - len(built.question_ids)
    assert sum(built.per_topic.values()) == len(built.question_ids)
    # It always uses the whole supply when the supply is smaller than the request.
    if len(ids) <= size:
        assert len(built.question_ids) == len(ids)
    # Deterministic.
    assert built == build(items, Spec(size=size, seed=seed, avoid_days=avoid))
