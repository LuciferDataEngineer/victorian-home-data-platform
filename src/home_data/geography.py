import re
import unicodedata
from pathlib import Path

import pandas as pd


def canonical_suburb_key(value: object) -> str:
    """Create a conservative comparison key; it never splits combined source geographies."""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    text = re.sub(r"\([^)]*\)", " ", text.upper())
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def load_manual_crosswalk(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    frame = pd.read_csv(path, dtype="string")
    required = {"source_suburb", "canonical_suburb"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Crosswalk requires columns: {sorted(required)}")
    return {
        canonical_suburb_key(source): canonical_suburb_key(target)
        for source, target in zip(frame["source_suburb"], frame["canonical_suburb"], strict=True)
    }


def apply_crosswalk(value: object, manual: dict[str, str]) -> tuple[str, str]:
    key = canonical_suburb_key(value)
    if key in manual:
        return manual[key], "manual_reviewed"
    return key, "normalised_exact"
