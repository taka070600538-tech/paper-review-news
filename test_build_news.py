import datetime
import os
import textwrap
from pathlib import Path

import pytest

from build_news import parse_note, classify_category, render_article_html, extract_summary, build_html, generate_site


def _write_note(dir_path: Path, name: str, frontmatter: str, body: str) -> Path:
    content = f"---\n{frontmatter}\n---\n{body}"
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / name
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


def test_parse_note_minimal_frontmatter_for_free_form_notes(tmp_path):
    # 「管理者のノート」向けの自作ファイルはtitleと本文だけでよく、
    # journal/authors/type/tagsは省略してもエラーにならず空値になる。
    frontmatter = 'title: "自由メモ"'
    body = "\n自由に書いた内容です。\n"
    path = _write_note(tmp_path, "free_note.md", frontmatter, body)

    note = parse_note(path)

    assert note["title"] == "自由メモ"
    assert note["journal"] == ""
    assert note["authors"] == ""
    assert note["type"] == ""
    assert note["tags"] == []
    assert note["body_md"].strip() == "自由に書いた内容です。"


def test_parse_note_missing_closing_delimiter_raises_value_error(tmp_path):
    path = tmp_path / "broken_精読ノート.md"
    path.write_text(
        '---\ntitle: "タイトル"\n\n本文のみで閉じデリミタなし\n', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="frontmatter closing '---' not found"):
        parse_note(path)


def test_classify_category_manual_override():
    note = {"title": "何か", "journal": "", "type": "", "tags": [], "category": "psychiatry"}
    assert classify_category(note) == ("psychiatry", "manual")


def test_classify_category_unknown_manual_value_falls_back_to_unclassified(capsys):
    note = {"title": "何か", "journal": "", "type": "", "tags": [], "category": "wellbeing"}
    assert classify_category(note) == ("unclassified", "auto")
    captured = capsys.readouterr()
    assert "unknown category 'wellbeing'" in captured.out


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


def test_render_article_html_strips_leading_h1():
    body_md = "# タイトル 精読ノート\n\n## 概要\n\n本文です。"
    html = render_article_html(body_md)
    assert "<h1>" not in html
    assert "タイトル 精読ノート" not in html
    assert "<h2>概要</h2>" in html
    assert "本文です" in html


def test_extract_summary_skips_blockquote_role_statement():
    body_md = (
        "# タイトル 精読ノート\n\n"
        "> 役割：サイエンスコミュニケーターとしての精読プロンプトに基づく分析結果\n\n"
        "## 1. 概要（500字以内）\n\n"
        "実際の概要テキストがここから始まります。"
    )
    summary = extract_summary(body_md, length=50)
    assert summary.startswith("実際の概要テキストがここから始まります")
    assert "役割" not in summary
    assert "サイエンスコミュニケーター" not in summary


def _sample_article(article_id, title, category, updated_at="2026-01-01"):
    return {
        "id": article_id,
        "title": title,
        "journal": "Journal X",
        "type": "原著研究",
        "authors": "Author A",
        "tags": ["tag1", "tag2"],
        "category": category,
        "updated_at": updated_at,
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


def test_build_html_renders_date_before_title_and_sorts_newest_first():
    articles = [
        _sample_article("a1", "記事タイトル1", "epigenetics", updated_at="2026-01-01"),
    ]
    html = build_html(articles)

    # 見出し行の先頭に日付span、続けてタイトルが表示されるテンプレートになっている
    assert '<span class="date">${a.updated_at}</span> ${a.title}' in html
    # 新しい順(降順)にソートするロジックが含まれる
    assert "b.updated_at.localeCompare(a.updated_at)" in html


def test_build_html_uses_site_title_in_title_tag_and_heading():
    html = build_html([_sample_article("a1", "記事タイトル1", "epigenetics")])

    assert "<title>Make Well-Being First</title>" in html
    assert "<h1>Make Well-Being First</h1>" in html
    assert "精神医学的アプローチによるWell-Beingの実現" not in html


def test_build_html_includes_youtube_link_above_tabs():
    html = build_html([_sample_article("a1", "記事タイトル1", "epigenetics")])

    assert 'href="https://www.youtube.com/channel/UClHX4olutwCBTywPOpIKfKA"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    # 見出し直下・カテゴリータブより上（最初に目に入る位置）に置く
    assert html.index('class="youtube-link"') < html.index('<div class="tabs">')


def test_build_html_includes_subcategory_dropdown():
    articles = [_sample_article("a1", "記事タイトル1", "epigenetics")]
    html = build_html(articles)

    assert '<select id="subcategorySelect">' in html
    assert '<option value="重要論文解説">重要論文解説</option>' in html
    assert '<option value="管理者のノート">管理者のノート</option>' in html


def test_build_html_shows_unclassified_tab_when_present():
    articles = [_sample_article("a1", "記事タイトル1", "unclassified")]
    html = build_html(articles)
    assert "未分類" in html


def test_build_html_escapes_closing_script_tag_in_body():
    article = _sample_article("a1", "記事タイトル1", "epigenetics")
    article["body_html"] = "<p>危険な文字列</script><script>alert(1)</script></p>"
    html = build_html([article])
    assert "</script><script>alert(1)" not in html


def test_generate_site_creates_index_html(tmp_path, capsys):
    _write_note(
        tmp_path / "重要論文解説",
        "note1_精読ノート.md",
        'title: "テスト論文1"\njournal: "J1"\nauthors: "A"\ntype: "原著研究"\ncategory: psychiatry\ntags: [精読]\n',
        "\n## 概要\n\n本文1\n",
    )
    _write_note(
        tmp_path / "重要論文解説",
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


def test_generate_site_excludes_body_md_and_source_from_json(tmp_path):
    _write_note(
        tmp_path / "重要論文解説",
        "note1_精読ノート.md",
        'title: "テスト論文1"\nsource: "secret-source-marker.pdf"\njournal: "J1"\nauthors: "A"\ntype: "原著研究"\ncategory: psychiatry\ntags: [精読]\n',
        "\n## 概要\n\nsecret-body-marker\n",
    )

    output_path = generate_site(tmp_path)
    html = output_path.read_text(encoding="utf-8")

    assert "secret-source-marker.pdf" not in html
    # body_md自体はJSONに含めないが、レンダリング済みのbody_htmlには本文が残る
    assert "secret-body-marker" in html


def test_generate_site_assigns_subcategory_by_folder(tmp_path):
    _write_note(
        tmp_path / "重要論文解説",
        "paper_note.md",
        'title: "論文ノート"\ncategory: psychiatry\n',
        "\n## 概要\n\n内容\n",
    )
    _write_note(
        tmp_path / "管理者のノート",
        "my_note.md",
        'title: "自分のメモ"\ncategory: psychiatry\n',
        "\n自由なメモ内容\n",
    )

    output_path = generate_site(tmp_path)
    html = output_path.read_text(encoding="utf-8")

    assert '"subcategory": "重要論文解説"' in html
    assert '"subcategory": "管理者のノート"' in html


def test_generate_site_skips_missing_subcategory_folder(tmp_path):
    # 「管理者のノート」フォルダが存在しなくてもエラーにならない
    _write_note(
        tmp_path / "重要論文解説",
        "paper_note.md",
        'title: "論文ノート"\ncategory: psychiatry\n',
        "\n## 概要\n\n内容\n",
    )

    output_path = generate_site(tmp_path)
    html = output_path.read_text(encoding="utf-8")

    assert "論文ノート" in html


def test_generate_site_includes_updated_at_from_file_mtime(tmp_path):
    path = _write_note(
        tmp_path / "重要論文解説",
        "note1_精読ノート.md",
        'title: "テスト論文1"\ncategory: psychiatry\n',
        "\n## 概要\n\n内容\n",
    )
    target_timestamp = datetime.datetime(2026, 1, 15).timestamp()
    os.utime(path, (target_timestamp, target_timestamp))

    output_path = generate_site(tmp_path)
    html = output_path.read_text(encoding="utf-8")

    assert '"updated_at": "2026-01-15"' in html
