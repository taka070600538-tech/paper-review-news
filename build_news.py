import re
from pathlib import Path

import markdown as markdown_lib
import yaml

FRONTMATTER_DELIM = "---"

CATEGORIES: list[tuple[str, str]] = [
    ("psychiatry", "精神医学"),
    ("epigenetics", "エピジェネティクス"),
    ("well-being", "ウェルビーイング"),
    ("cbt", "認知行動療法"),
    ("psychopharmacology", "精神薬理学"),
]

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "psychiatry": [
        "psychiatry", "psychiatric", "精神医学", "精神科", "精神疾患", "精神障害",
        "schizophrenia", "統合失調症", "depression", "うつ病", "bipolar", "双極性",
        "anxiety disorder", "不安障害", "ptsd", "adhd", "autism", "自閉症",
    ],
    "epigenetics": [
        "epigenetic", "epigenetics", "エピジェネティクス", "methylation", "メチル化",
        "histone", "ヒストン", "mirna", "microrna", "ncrna", "non-coding rna",
        "mitoepigenetics", "chromatin", "クロマチン",
    ],
    "well-being": [
        "well-being", "wellbeing", "ウェルビーイング", "flourishing", "happiness",
        "幸福", "forgiveness", "許し", "life satisfaction", "人生満足度",
        "positive psychology", "ポジティブ心理学", "resilience", "レジリエンス",
    ],
    "cbt": [
        "cognitive behavioral therapy", "cognitive therapy", "cbt", "認知行動療法",
        "認知療法", "schema therapy", "スキーマ療法", "automatic thoughts", "自動思考",
        "cognitive restructuring", "認知再構成",
    ],
    "psychopharmacology": [
        "pharmacology", "psychopharmacology", "薬理学", "薬理", "精神薬理",
        "antidepressant", "抗うつ薬", "antipsychotic", "抗精神病薬", "ssri", "snri",
        "benzodiazepine", "ベンゾジアゼピン", "pharmacokinetics", "薬物動態",
        "drug interaction", "薬物相互作用",
    ],
}


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


def classify_category(note: dict) -> tuple[str, str]:
    if note.get("category"):
        return note["category"], "manual"

    haystack = " ".join(
        [note.get("title", ""), note.get("journal", ""), note.get("type", "")]
        + note.get("tags", [])
    ).lower()

    scores = {
        cat_id: sum(1 for kw in keywords if kw.lower() in haystack)
        for cat_id, keywords in CATEGORY_KEYWORDS.items()
    }
    max_score = max(scores.values())
    if max_score == 0:
        return "unclassified", "auto"

    top = [cat_id for cat_id, score in scores.items() if score == max_score]
    if len(top) > 1:
        return "unclassified", "auto"
    return top[0], "auto"


def render_article_html(body_md: str) -> str:
    return markdown_lib.markdown(body_md, extensions=["tables"])


def extract_summary(body_md: str, length: int = 100) -> str:
    plain = re.sub(r"^#{1,6}\s*.*$", "", body_md, flags=re.MULTILINE)
    plain = re.sub(r"[#*>`\-]", "", plain)
    plain = re.sub(r"\s+", "", plain).strip()
    if len(plain) <= length:
        return plain
    return plain[:length] + "..."
