from pathlib import Path

import yaml

FRONTMATTER_DELIM = "---"


def parse_note(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    assert lines[0].strip() == FRONTMATTER_DELIM, f"frontmatter not found in {path}"
    end_idx = next(
        i for i in range(1, len(lines)) if lines[i].strip() == FRONTMATTER_DELIM
    )
    frontmatter_text = "\n".join(lines[1:end_idx])
    body_md = "\n".join(lines[end_idx + 1 :]).strip("\n")

    meta = yaml.safe_load(frontmatter_text) or {}
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    return {
        "title": str(meta.get("title", "")).strip(),
        "source": str(meta.get("source", "")).strip(),
        "journal": str(meta.get("journal", "")).strip(),
        "authors": str(meta.get("authors", "")).strip(),
        "type": str(meta.get("type", "")).strip(),
        "tags": [str(t) for t in tags],
        "category": meta.get("category"),
        "body_md": body_md,
    }
