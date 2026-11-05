"""The notes-answering prompt text lives in `prompts/ask-notes/`; this builds the user message."""

NOT_IN_NOTES = "NOT_IN_NOTES"


def user_message(question: str, passages: list[tuple[str, str]]) -> str:
    """`passages` are (label, text) pairs, numbered from 1 in the order given."""
    blocks = [f"[{n}] {label}\n{text}" for n, (label, text) in enumerate(passages, start=1)]
    return "Passages:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}"
