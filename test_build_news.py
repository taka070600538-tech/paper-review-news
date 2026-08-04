import textwrap
from pathlib import Path

from build_news import parse_note, classify_category, render_article_html, extract_summary, build_html, generate_site


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


def test_classify_category_manual_override():
    note = {"title": "何か", "journal": "", "type": "", "tags": [], "category": "psychiatry"}
    assert classify_category(note) == ("psychiatry", "manual")


def test_classify_category_auto_epigenetics():
    note = {
        "title": "Epigenetics of Alzheimer's Disease",
        "journal": "Biomolecules",
        "type": "レビュー論文",
        "tags": ["精読", "epigenetics", "DNAメチル化", "ヒストン修飾", "miRNA"],
        "category": None,
    }
    assert classify_category(note) == ("epigenetics", "auto")


def test_classify_category_auto_wellbeing():
    note = {
        "title": "Longitudinal associations of dispositional forgivingness with multidimensional wellbeing",
        "journal": "npj Mental Health Research",
        "type": "原著研究",
        "tags": ["精読", "forgiveness", "well-being", "GlobalFlourishingStudy"],
        "category": None,
    }
    assert classify_category(note) == ("well-being", "auto")


def test_classify_category_no_match_is_unclassified():
    note = {"title": "無関係なタイトル", "journal": "", "type": "", "tags": [], "category": None}
    assert classify_category(note) == ("unclassified", "auto")


def test_render_article_html_converts_headings_and_bold():
    body_md = "## 概要（500字以内）\n\nこれは**重要**な内容です。\n\n### Table 1\n表の説明。"
    html = render_article_html(body_md)
    assert "<h2>" in html
    assert "<h3>" in html
    assert "<strong>重要</strong>" in html


def test_extract_summary_strips_markdown_and_truncates():
    body_md = "## 概要（500字以内）\n\n" + "あ" * 200
    summary = extract_summary(body_md, length=50)
    assert "##" not in summary
    assert len(summary) <= 53  # 50文字 + "..."
    assert summary.startswith("あ")


def _sample_article(article_id, title, category):
    return {
        "id": article_id,
        "title": title,
        "journal": "Journal X",
        "type": "原著研究",
        "authors": "Author A",
        "tags": ["tag1", "tag2"],
        "category": category,
        "summary": "概要の抜粋テキスト",
        "body_html": "<h2>概要</h2><p>本文</p>",
    }


def test_build_html_includes_category_tabs_and_articles():
    articles = [
        _sample_article("a1", "記事タイトル1", "epigenetics"),
        _sample_article("a2", "記事タイトル2", "well-being"),
    ]
    html = build_html(articles)

    assert "精神医学" in html
    assert "エピジェネティクス" in html
    assert "認知行動療法" in html
    assert "記事タイトル1" in html
    assert "記事タイトル2" in html
    assert "未分類" not in html


def test_build_html_shows_unclassified_tab_when_present():
    articles = [_sample_article("a1", "記事タイトル1", "unclassified")]
    html = build_html(articles)
    assert "未分類" in html


def test_generate_site_creates_index_html(tmp_path, capsys):
    _write_note(
        tmp_path,
        "note1_精読ノート.md",
        'title: "テスト論文1"\njournal: "J1"\nauthors: "A"\ntype: "原著研究"\ncategory: psychiatry\ntags: [精読]\n',
        "\n## 概要\n\n本文1\n",
    )
    _write_note(
        tmp_path,
        "note2_精読ノート.md",
        'title: "テスト論文2"\njournal: "J2"\nauthors: "B"\ntype: "総説"\ntags: [epigenetics, methylation]\n',
        "\n## 概要\n\n本文2\n",
    )

    output_path = generate_site(tmp_path)

    assert output_path == tmp_path / "index.html"
    html = output_path.read_text(encoding="utf-8")
    assert "テスト論文1" in html
    assert "テスト論文2" in html

    captured = capsys.readouterr()
    assert "[manual]" in captured.out
    assert "[auto]" in captured.out
