import datetime
import json
import re
from pathlib import Path

import markdown as markdown_lib
import yaml

FRONTMATTER_DELIM = "---"

SITE_TITLE = "Make Well-Being First"

# TOPページ見出し直下に置くYouTubeへのリンク（URL, ラベル）。先頭が塗りつぶし、
# 2つ目以降が枠線のみのボタンになる。リンクを増減するときはここを変更する。
YOUTUBE_LINKS: list[tuple[str, str]] = [
    ("https://youtu.be/fFUVwz6roM4", "解説動画を見る"),
    ("https://www.youtube.com/channel/UClHX4olutwCBTywPOpIKfKA", "YouTubeチャンネル"),
]

YOUTUBE_ICON_SVG = (
    '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
    '<path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.4.6A3 3 0 0 0'
    " .5 6.2 31.4 31.4 0 0 0 0 12a31.4 31.4 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.6 9.4.6"
    " 9.4.6s7.5 0 9.4-.6a3 3 0 0 0 2.1-2.1A31.4 31.4 0 0 0 24 12a31.4 31.4 0 0"
    ' 0-.5-5.8zM9.5 15.6V8.4l6.3 3.6-6.3 3.6z"/></svg>'
)


def render_youtube_links_html() -> str:
    items = []
    for index, (url, label) in enumerate(YOUTUBE_LINKS):
        css_class = "youtube-link" if index == 0 else "youtube-link secondary"
        items.append(
            f'  <a class="{css_class}" href="{url}" target="_blank"'
            f' rel="noopener noreferrer">{YOUTUBE_ICON_SVG}<span>{label}</span></a>'
        )
    return "\n".join(items)

CATEGORIES: list[tuple[str, str]] = [
    ("psychiatry", "精神医学"),
    ("epigenetics", "エピジェネティクス"),
    ("well-being", "ウェルビーイング"),
    ("cbt", "認知行動療法"),
    ("psychopharmacology", "精神薬理学"),
]

SUBCATEGORIES: list[str] = ["重要論文解説", "管理者のノート"]

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
    try:
        end_idx = next(
            i for i in range(1, len(lines)) if lines[i].strip() == FRONTMATTER_DELIM
        )
    except StopIteration:
        raise ValueError(f"frontmatter closing '---' not found in {path}")
    frontmatter_text = "\n".join(lines[1:end_idx])
    body_md = "\n".join(lines[end_idx + 1 :]).strip("\n")

    meta = yaml.safe_load(frontmatter_text) or {}
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    return {
        "title": str(meta.get("title", "")).strip(),
        "source": str(meta.get("source", "")).strip(),
        # 原著（DOIまたは出版社ページ）へのURL。公開ページから原典に飛べるようにする。
        "source_url": str(meta.get("source_url", "") or "").strip(),
        "journal": str(meta.get("journal", "")).strip(),
        "authors": str(meta.get("authors", "")).strip(),
        "type": str(meta.get("type", "")).strip(),
        "tags": [str(t) for t in tags],
        "category": meta.get("category"),
        "body_md": body_md,
    }


def classify_category(note: dict) -> tuple[str, str]:
    valid_ids = {cat_id for cat_id, _ in CATEGORIES}
    category = note.get("category")
    if category:
        if category in valid_ids:
            return category, "manual"
        print(
            f"[warning] unknown category '{category}' in note, falling back to unclassified"
        )
        return "unclassified", "auto"

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
    # 本文冒頭のレベル1見出し（# タイトル）は詳細ビューの<h1>と重複するため除去する。
    body_md = re.sub(r"\A\s*#(?!#)[ \t]+[^\n]*\n?", "", body_md)
    return markdown_lib.markdown(body_md, extensions=["tables"])


def extract_summary(body_md: str, length: int = 100) -> str:
    plain = re.sub(r"^#{1,6}\s*.*$", "", body_md, flags=re.MULTILINE)
    plain = re.sub(r"^>\s*.*$", "", plain, flags=re.MULTILINE)
    plain = re.sub(r"[#*>`\-]", "", plain)
    plain = re.sub(r"\s+", "", plain).strip()
    if len(plain) <= length:
        return plain
    return plain[:length] + "..."


def build_html(articles: list[dict]) -> str:
    categories = list(CATEGORIES)
    if any(a["category"] == "unclassified" for a in articles):
        categories = categories + [("unclassified", "未分類")]

    # </script> のような文字列が本文に含まれていてもscriptタグが早期終了しないようにする。
    articles_json = json.dumps(articles, ensure_ascii=False).replace("</", "<\\/")
    tabs_html = "\n".join(
        f'<button class="tab" data-category="{cat_id}">{label}</button>'
        for cat_id, label in categories
    )
    subcategory_options_html = "\n".join(
        f'<option value="{sub}">{sub}</option>' for sub in SUBCATEGORIES
    )
    youtube_links_html = render_youtube_links_html()

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{SITE_TITLE}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, "Hiragino Sans", sans-serif; max-width: 860px; margin: 0 auto; padding: 1.5rem; line-height: 1.7; }}
  .youtube-links {{ display: flex; flex-wrap: wrap; gap: 0.6rem; margin: 0.25rem 0 1.5rem; }}
  .youtube-link {{ display: inline-flex; align-items: center; gap: 0.55rem; padding: 0.6rem 1.1rem; border: 2px solid #e62117; border-radius: 8px; background: #e62117; color: #fff; text-decoration: none; font-weight: 600; font-size: 0.95rem; }}
  .youtube-link:hover {{ background: #b81410; border-color: #b81410; }}
  .youtube-link.secondary {{ background: transparent; color: #e62117; }}
  .youtube-link.secondary:hover {{ background: rgba(230,33,23,0.1); border-color: #e62117; }}
  .youtube-link svg {{ width: 1.5rem; height: 1.5rem; flex-shrink: 0; }}
  @media (prefers-color-scheme: dark) {{
    .youtube-link.secondary {{ color: #ff6b60; border-color: #ff6b60; }}
    .youtube-link.secondary:hover {{ background: rgba(255,107,96,0.15); border-color: #ff6b60; }}
  }}
  .tabs {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; }}
  .tab {{ padding: 0.5rem 1rem; border: 1px solid #888; border-radius: 999px; background: transparent; cursor: pointer; font-size: 0.95rem; }}
  .tab.active {{ background: #2563eb; color: white; border-color: #2563eb; }}
  .subcategory-bar {{ margin-bottom: 1.5rem; }}
  #subcategorySelect {{ padding: 0.4rem 0.6rem; font-size: 0.9rem; border-radius: 6px; border: 1px solid #888; background: transparent; color: inherit; }}
  .headline-list {{ display: flex; flex-direction: column; }}
  .headline {{ display: block; padding: 0.6rem 0.2rem; border-bottom: 1px solid #ddd; color: #06c; text-decoration: none; font-size: 1rem; }}
  .headline:hover {{ text-decoration: underline; background: rgba(37,99,235,0.06); }}
  .headline .date {{ color: #888; font-size: 0.85rem; margin-right: 0.4rem; }}
  @media (prefers-color-scheme: dark) {{
    .headline {{ color: #6cf; border-color: #444; }}
    .headline .date {{ color: #999; }}
  }}
  .badge {{ display: inline-block; font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; background: #eee; color: #333; border: 1px solid #ccc; margin-right: 0.4rem; }}
  .hidden {{ display: none; }}
  #backBtn {{ margin-bottom: 1rem; cursor: pointer; }}
  .source-url {{ font-size: 0.9rem; word-break: break-all; }}
  .source-url a {{ color: #06c; }}
  .tags span {{ font-size: 0.75rem; color: #666; margin-right: 0.5rem; }}
  @media (prefers-color-scheme: dark) {{
    .badge {{ background: #444; color: #eee; border-color: #666; }}
    .source-url a {{ color: #6cf; }}
    .tags span {{ color: #aaa; }}
  }}
</style>
</head>
<body>
<h1>{SITE_TITLE}</h1>
<div class="youtube-links">
{youtube_links_html}
</div>
<div class="tabs">{tabs_html}</div>
<div class="subcategory-bar">
  <select id="subcategorySelect">
    <option value="all">すべて</option>
    {subcategory_options_html}
  </select>
</div>
<div id="listView"></div>
<div id="detailView" class="hidden">
  <button id="backBtn">&larr; 一覧に戻る</button>
  <div id="detailContent"></div>
</div>
<script>
const articles = {articles_json};
let currentCategory = articles.length ? (articles.find(a => a.category) || articles[0]).category : null;
let currentSubcategory = 'all';

function renderList(category) {{
  currentCategory = category;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.category === category));
  const list = articles
    .filter(a => a.category === category && (currentSubcategory === 'all' || a.subcategory === currentSubcategory))
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  const listView = document.getElementById('listView');
  listView.innerHTML = `<div class="headline-list">${{list.map(a => `
    <a href="#" class="headline" data-id="${{a.id}}"><span class="date">${{a.updated_at}}</span> ${{a.title}}</a>
  `).join('') || '<p>このカテゴリーの記事はまだありません。</p>'}}</div>`;
  document.querySelectorAll('.headline').forEach(el => {{
    el.addEventListener('click', (e) => {{ e.preventDefault(); showDetail(el.dataset.id); }});
  }});
  document.getElementById('listView').classList.remove('hidden');
  document.getElementById('detailView').classList.add('hidden');
}}

function showDetail(id) {{
  const a = articles.find(x => x.id === id);
  document.getElementById('detailContent').innerHTML = `
    <span class="badge">${{a.type}}</span>
    <h1>${{a.title}}</h1>
    <p>${{a.journal}} / ${{a.authors}}</p>
    ${{a.source_url ? `<p class="source-url">原著論文: <a href="${{a.source_url}}" target="_blank" rel="noopener noreferrer">${{a.source_url}}</a></p>` : ''}}
    <div class="tags">${{a.tags.map(t => `<span>#${{t}}</span>`).join('')}}</div>
    <hr>
    ${{a.body_html}}
  `;
  document.getElementById('listView').classList.add('hidden');
  document.getElementById('detailView').classList.remove('hidden');
}}

document.querySelectorAll('.tab').forEach(t => {{
  t.addEventListener('click', () => renderList(t.dataset.category));
}});
document.getElementById('subcategorySelect').addEventListener('change', (e) => {{
  currentSubcategory = e.target.value;
  renderList(currentCategory);
}});
document.getElementById('backBtn').addEventListener('click', () => renderList(currentCategory));

if (currentCategory) {{
  renderList(currentCategory);
}} else {{
  document.getElementById('listView').innerHTML = '<p>精読ノートがまだありません。</p>';
}}
</script>
</body>
</html>"""


def generate_site(folder: Path) -> Path:
    articles = []
    for subcategory in SUBCATEGORIES:
        subfolder = folder / subcategory
        if not subfolder.is_dir():
            continue
        note_paths = sorted(subfolder.glob("*.md"))
        for path in note_paths:
            note = parse_note(path)
            note["subcategory"] = subcategory
            category, method = classify_category(note)
            note["category"] = category
            note["id"] = path.stem
            note["updated_at"] = datetime.date.fromtimestamp(
                path.stat().st_mtime
            ).isoformat()
            note["body_html"] = render_article_html(note["body_md"])
            note["summary"] = extract_summary(note["body_md"])
            articles.append(note)
            print(f"[{method}] {subcategory}/{path.name} -> {category}")

    # body_md/source はJS側で参照されず、特にbody_mdはサイズが大きいためJSONには含めない。
    json_articles = [
        {k: v for k, v in article.items() if k not in ("body_md", "source")}
        for article in articles
    ]
    html = build_html(json_articles)
    output_path = folder / "index.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"Generated: {output_path}")
    return output_path


def main():
    generate_site(Path(__file__).resolve().parent)


if __name__ == "__main__":
    main()
