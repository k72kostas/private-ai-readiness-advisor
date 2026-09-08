"""Pure helper functions used by the Streamlit interface."""


def enum_label(value: str) -> str:
    """Convert a machine-readable value into a readable label."""
    return value.replace("_", " ").title()


def lines(value: str) -> list[str]:
    """Convert multiline text into unique, non-empty values."""
    parsed: list[str] = []
    seen: set[str] = set()
    for line in value.splitlines():
        cleaned = line.strip()
        normalized = cleaned.casefold()
        if cleaned and normalized not in seen:
            parsed.append(cleaned)
            seen.add(normalized)
    return parsed
