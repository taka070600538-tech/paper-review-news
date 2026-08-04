import textwrap
from pathlib import Path

from build_news import parse_note


def _write_note(tmp_path: Path, name: str, frontmatter: str, body: str) -> Path:
    content = f"---\n{frontmatter}\n---\n{body}"
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_note_inline_tags_list(tmp_path):
    frontmatter = textwrap.dedent("""\
        title: "サンプル論文 精読ノート"
        source: "sample.pdf"
        journal: "Sample Journal 2026"
        authors: "Alice, Bob"
        type: "原著研究"
        tags: [精読, well-being, forgiveness]
        """)
    body = "\n# 見出し\n\n本文テキスト\n"
    path = _write_note(tmp_path, "sample_精読ノート.md", frontmatter, body)

    note = parse_note(path)

    assert note["title"] == "サンプル論文 精読ノート"
    assert note["journal"] == "Sample Journal 2026"
    assert note["type"] == "原著研究"
    assert note["tags"] == ["精読", "well-being", "forgiveness"]
    assert note["category"] is None
    assert note["body_md"].strip() == "# 見出し\n\n本文テキスト".strip()


def test_parse_note_block_tags_list_and_explicit_category(tmp_path):
    frontmatter = textwrap.dedent("""\
        title: "サンプル2 精読ノート"
        source: "sample2.pdf"
        journal: "Sample Journal 2"
        authors: "Carol"
        type: "総説（Review）"
        category: epigenetics
        tags:
          - 論文精読
          - エピジェネティクス
        """)
    body = "\n## 概要\n\n内容\n"
    path = _write_note(tmp_path, "sample2_精読ノート.md", frontmatter, body)

    note = parse_note(path)

    assert note["tags"] == ["論文精読", "エピジェネティクス"]
    assert note["category"] == "epigenetics"
