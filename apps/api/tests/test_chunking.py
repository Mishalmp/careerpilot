import uuid

from careerpilot.modules.knowledge.chunking import chunk_markdown
from careerpilot.modules.knowledge.ranking import or_query, reciprocal_rank_fusion

DOC = """# Python

Intro paragraph about the guide.

## Core questions

**1. Mutable defaults.** A default argument is created once, so a list default is shared between calls.

**2. `is` vs `==`.** `is` compares identity, `==` compares value.

## Practice

- write a decorator
- write a context manager
"""


def test_each_chunk_knows_its_heading_path() -> None:
    chunks = chunk_markdown(DOC)
    # the two short questions are merged into one passage (see the next tests)
    assert [c.heading_path for c in chunks] == [
        "Python",
        "Python > Core questions",
        "Python > Practice",
    ]


def test_a_numbered_question_starts_a_new_chunk() -> None:
    chunks = chunk_markdown(DOC, min_chars=20)
    questions = [c.text for c in chunks if c.heading_path.endswith("Core questions")]
    assert len(questions) == 2
    assert questions[0].startswith("**1. Mutable") and "**2." not in questions[0]
    assert questions[1].startswith("**2.")


def test_tiny_items_are_merged_rather_than_left_alone() -> None:
    chunks = chunk_markdown(DOC)  # default minimum is 200 characters
    questions = [c.text for c in chunks if c.heading_path.endswith("Core questions")]
    assert len(questions) == 1 and "**1." in questions[0] and "**2." in questions[0]


def test_headings_inside_code_fences_are_code_not_headings() -> None:
    markdown = (
        "## Templates\n\n```python\n# sliding window\ndef f():\n    pass\n```\n\nAfter the code.\n"
    )
    chunks = chunk_markdown(markdown)
    assert {c.heading_path for c in chunks} == {"Templates"}
    assert any("# sliding window" in c.text for c in chunks)


def test_code_blocks_are_not_cut_in_the_middle_when_they_fit() -> None:
    code = "```python\n" + "\n".join(f"line_{i} = {i}" for i in range(40)) + "\n```"
    chunks = chunk_markdown(f"## Code\n\nBefore.\n\n{code}\n\nAfter.\n", max_chars=1500)
    holder = next(c for c in chunks if "line_0" in c.text)
    assert "line_39" in holder.text and holder.text.count("```") == 2


def test_oversized_blocks_are_split_and_every_piece_fits() -> None:
    sentence = "This sentence is exactly forty-eight chars. "  # 44 chars
    markdown = "## Long\n\n" + sentence * 200 + "\n"
    chunks = chunk_markdown(markdown, max_chars=500)
    assert len(chunks) > 5
    assert all(
        len(c.text) <= 500 * 1.3 for c in chunks
    )  # a small tail may push a passage over by up to 30%
    assert sum(c.text.count("This sentence") for c in chunks) == 200  # nothing lost


def test_a_single_unbroken_line_is_hard_cut() -> None:
    chunks = chunk_markdown("## Blob\n\n" + "x" * 3200, max_chars=1000)
    assert [len(c.text) for c in chunks] == [1000, 1000, 1000, 200]


def test_nested_headings_build_the_path_and_siblings_replace_each_other() -> None:
    markdown = "# A\n\n## B\n\ntext b\n\n### C\n\ntext c\n\n## D\n\ntext d\n"
    paths = [c.heading_path for c in chunk_markdown(markdown, min_chars=1)]
    assert paths == ["A > B", "A > B > C", "A > D"]


def test_empty_and_heading_only_documents() -> None:
    assert chunk_markdown("") == []
    assert chunk_markdown("# Title\n\n## Empty section\n") == []


def test_tables_stay_together() -> None:
    table = "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
    chunks = chunk_markdown(f"## T\n\n{table}\n")
    assert chunks[0].text == table


def test_text_before_any_heading_has_an_empty_path() -> None:
    assert chunk_markdown("Just text.\n")[0].heading_path == ""


# ---- ranking ----


def test_rank_fusion_rewards_agreement_between_lists() -> None:
    a, b, c = (uuid.UUID(int=n) for n in (1, 2, 3))
    fused = dict(reciprocal_rank_fusion([[a, b], [c, b]]))
    assert fused[b] > fused[a] and fused[b] > fused[c]  # b is in both lists
    assert list(dict(reciprocal_rank_fusion([[a, b, c]]))) == [a, b, c]


def test_rank_fusion_of_nothing() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_or_query_keeps_only_plain_words() -> None:
    assert (
        or_query("How do I use 'dict' keys; DROP TABLE x --")
        == "how | do | use | dict | keys | drop | table"
    )
    assert or_query("") == ""
    assert or_query("!!! ??? a b") == ""
