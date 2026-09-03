from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import struct
import zlib
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit, urlunsplit, parse_qsl

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_text(path: Path, value: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def affiliate_url(base_url: str, affiliate_id: str, tag: str) -> str:
    parts = urlsplit(base_url)
    host = parts.netloc.removeprefix("www.")
    query = dict(parse_qsl(parts.query))
    query.update({"sa": affiliate_id, "tk": tag})
    return urlunsplit(("https", host, parts.path or "/", urlencode(query), ""))


def select_topic(topics, run_date: date):
    active = sorted(
        topics,
        key=lambda x: (-(int(x["intent"]) + int(x["evergreen"]) - int(x["saturation"])), x["topic_id"]),
    )
    top_score = int(active[0]["intent"]) + int(active[0]["evergreen"]) - int(active[0]["saturation"])
    best = [t for t in active if int(t["intent"]) + int(t["evergreen"]) - int(t["saturation"]) == top_score]
    return best[run_date.toordinal() % len(best)]


def build_article(settings, offer, topic, content_id, link):
    title = f'{topic["keyword"]}：固定費を抑えて最初の導線を作る方法'
    disclosure = settings["disclosure"]
    body = f"""# {title}

{disclosure}

「{topic['pain']}」という人向けに、最初から多機能な構成を抱えず、必要な導線だけを作る手順をまとめます。

## 結論

最初の検証では、無料プランから始められるSysteme.ioにページ、メール、販売導線を寄せると管理箇所を減らせます。向き不向きを確かめてから有料化を判断してください。

## 最小セットアップ

1. 無料アカウントを作る
2. 読者に渡す無料コンテンツを1つ決める
3. 登録ページと確認メールを作る
4. 自分で登録テストをする
5. 7日間だけ流入と登録数を記録する

## 向いている人

- {offer['audience']}
- 複数サービスの接続より、まず1本公開したい人
- 初期費用を抑えて反応を測りたい人

## 注意点

無料枠の上限や機能は変更される可能性があります。登録前に公式ページで最新条件を確認してください。成果や収益を保証するものではありません。

## 次の一歩

[{offer['name']}の無料プランを公式サイトで確認する]({link})

---
計測ID: `{content_id}`
"""
    return title, body


def markdown_to_html(markdown: str, page_title: str):
    def inline(value):
        out, pos = [], 0
        for match in re.finditer(r"\[([^]]+)\]\(([^)]+)\)", value):
            out.append(html.escape(value[pos:match.start()]))
            out.append(f'<a href="{html.escape(match.group(2), quote=True)}" rel="sponsored nofollow">{html.escape(match.group(1))}</a>')
            pos = match.end()
        out.append(html.escape(value[pos:]))
        return "".join(out)

    blocks, list_items = [], []
    def flush_list():
        nonlocal list_items
        if list_items:
            blocks.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in list_items) + "</ul>")
            list_items = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            flush_list()
        elif line.startswith("# "):
            flush_list(); blocks.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            flush_list(); blocks.append(f"<h2>{inline(line[3:])}</h2>")
        elif re.match(r"^(?:-|\d+\.) ", line):
            list_items.append(re.sub(r"^(?:-|\d+\.) ", "", line))
        elif line == "---":
            flush_list(); blocks.append("<hr>")
        else:
            flush_list(); blocks.append(f"<p>{inline(line)}</p>")
    flush_list()
    return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(page_title)}</title><style>body{{font-family:system-ui,sans-serif;line-height:1.8;max-width:760px;margin:40px auto;padding:0 20px;color:#18221d}}h1{{line-height:1.35}}a{{color:#176b45}}li{{margin:.5rem 0}}</style></head><body>{''.join(blocks)}</body></html>'''


def build_svg(title: str, subtitle: str):
    title = html.escape(title)
    subtitle = html.escape(subtitle)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1500" viewBox="0 0 1000 1500">
<rect width="1000" height="1500" fill="#f7f3ea"/>
<rect x="70" y="70" width="860" height="1360" rx="42" fill="#15241d"/>
<circle cx="820" cy="250" r="180" fill="#d9ff73" opacity=".95"/>
<text x="120" y="190" fill="#d9ff73" font-family="Arial, sans-serif" font-size="42" font-weight="700">0円から検証</text>
<foreignObject x="120" y="360" width="760" height="620">
  <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Arial,'Noto Sans JP',sans-serif;color:white;font-size:76px;font-weight:800;line-height:1.25;overflow-wrap:anywhere">{title}</div>
</foreignObject>
<foreignObject x="120" y="1080" width="760" height="180">
  <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Arial,'Noto Sans JP',sans-serif;color:#d7dfda;font-size:38px;line-height:1.4">{subtitle}</div>
</foreignObject>
<text x="120" y="1360" fill="#9eaaa3" font-family="Arial,sans-serif" font-size="28">広告・詳細はリンク先へ</text>
</svg>'''


FONT = {
    "A":"011101000110001111111000110001", "B":"111101000111110100011000111110",
    "C":"011111000010000100001000001111",
    "D":"111101000110001100011000111110", "E":"111111000011110100001000011111",
    "F":"111111000011110100001000010000", "G":"011111000010111100010100101110",
    "H":"100011000111111100011000110001", "L":"100001000010000100001000011111",
    "I":"111110010000100001000010011111", "M":"100011101110101101011000110001",
    "N":"100011100110101100111000110001", "O":"011101000110001100011000101110",
    "R":"111101000111110101001001010001", "S":"011111000001110000011000111110",
    "T":"111110010000100001000010000100", "U":"100011000110001100011000101110",
    "Y":"100011000101010001000010000100", "0":"011101001110101110011000101110",
    "7":"111110000100010001000100001000", ".":"000000000000000000000110001100",
    "/":"000010001000100010001000010000", " ":"000000000000000000000000000000",
}


def build_png(path: Path):
    width, height = 1000, 1500
    bg, card, accent, white, muted = (247,243,234), (21,36,29), (217,255,115), (255,255,255), (190,204,196)
    pixels = bytearray(bg * (width * height))

    def rect(x, y, w, h, color):
        row = bytes(color) * w
        for yy in range(y, y + h):
            start = (yy * width + x) * 3
            pixels[start:start + w * 3] = row

    def text_line(value, x, y, scale, color):
        cursor = x
        for char in value.upper():
            glyph = FONT.get(char, FONT[" "])
            for gy in range(6):
                for gx in range(5):
                    if glyph[gy * 5 + gx] == "1":
                        rect(cursor + gx * scale, y + gy * scale, scale, scale, color)
            cursor += 6 * scale

    rect(70, 70, 860, 1360, card)
    rect(120, 150, 500, 62, accent)
    text_line("START FREE", 145, 165, 7, card)
    text_line("SYSTEME.IO", 120, 430, 12, white)
    text_line("START GUIDE", 120, 560, 11, white)
    rect(120, 790, 760, 8, accent)
    text_line("TEST IN 7 DAYS", 120, 880, 8, accent)
    text_line("NO MONTHLY TOOL", 120, 1010, 8, muted)
    text_line("COST TO START", 120, 1110, 8, muted)
    text_line("AD / READ MORE", 120, 1330, 5, muted)

    raw = b"".join(b"\x00" + pixels[y * width * 3:(y + 1) * width * 3] for y in range(height))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def aggregate_kpis(rows, offer_id):
    total = {k: 0 for k in ("impressions", "outbound_clicks", "signups", "sales", "revenue_jpy")}
    for row in rows:
        if row.get("offer_id") != offer_id:
            continue
        for key in total:
            total[key] += int(float(row.get(key) or 0))
    total["ctr"] = total["outbound_clicks"] / total["impressions"] if total["impressions"] else 0
    return total


def decision(day, k):
    if day < 7:
        return "NOT_DUE", "7日目までデータを集める"
    if day < 14:
        if k["impressions"] < 100:
            return "GO", "母数不足。14日目まで継続"
        return ("GO", "CTR 1%以上") if k["ctr"] >= .01 else ("NO-GO", "画像・見出しを差し替える")
    if day < 30:
        if k["outbound_clicks"] >= 10 and k["signups"] >= 1:
            return "GO", "クリックと登録を確認"
        if k["impressions"] < 300:
            return "GO", "母数不足。30日目まで継続"
        return "NO-GO", "テーマまたは導線を変更"
    if k["sales"] >= 1 or k["signups"] >= 3:
        return "GO", "成約または登録シグナルあり。継続"
    return "NO-GO", "30日で十分な成約シグナルなし。別案件候補へ"


def run(run_date: date):
    settings = load_json(ROOT / "config/settings.json")
    offers = {x["offer_id"]: x for x in read_csv(ROOT / "data/offers.csv") if x["active"].lower() == "true"}
    topic = select_topic([x for x in read_csv(ROOT / "data/topics.csv") if x["offer_id"] in offers], run_date)
    offer = offers[topic["offer_id"]]
    content_id = f'{topic["topic_id"]}-{run_date.isoformat()}'
    link = affiliate_url(offer["base_url"], settings["affiliate_id"], content_id)
    title, article = build_article(settings, offer, topic, content_id, link)
    slug = content_id
    article_path = ROOT / "generated/articles" / f"{slug}.md"
    html_path = ROOT / "generated/articles" / f"{slug}.html"
    image_path = ROOT / "generated/images" / f"{slug}.png"
    svg_path = ROOT / "generated/images" / f"{slug}.svg"
    write_text(article_path, article)
    write_text(html_path, markdown_to_html(article, title))
    write_text(svg_path, build_svg(topic["keyword"], topic["angle"]))
    build_png(image_path)

    site = settings["site_base_url"].rstrip("/")
    article_url = f"{site}/generated/articles/{quote(slug)}.html"
    image_url = f"{site}/generated/images/{quote(slug)}.png"
    variants = [
        (f'{topic["keyword"]}を最小構成で', f'{topic["pain"]}なら、無料枠で必要な導線だけ検証。手順を整理しました。 #広告'),
        (f'固定費0円から：{topic["keyword"]}', f'{topic["angle"]}。使う前に向き不向きと注意点も確認できます。 #アフィリエイト'),
        (f'{offer["name"]}で最初の1本', f'ツールを増やしすぎず、7日で反応を見るためのセットアップ手順。 #広告'),
    ]
    blocked = settings["affiliate_id"] == "REPLACE_ME" or "YOUR_" in site
    queue_path = ROOT / "generated/publish_queue.csv"
    fields = ["content_id", "title", "description", "article_url", "image_url", "affiliate_url", "manual_create_url", "approved", "status", "pinterest_pin_id", "published_at"]
    existing = read_csv(queue_path) if queue_path.exists() else []
    by_id = {row["content_id"]: row for row in existing}
    for i, (pin_title, description) in enumerate(variants, 1):
        row_id = f"{content_id}-p{i}"
        manual = "https://www.pinterest.com/pin/create/button/?" + urlencode({"url": article_url, "media": image_url, "description": description})
        new_row = {"content_id": row_id, "title": pin_title, "description": description, "article_url": article_url, "image_url": image_url, "affiliate_url": link, "manual_create_url": manual, "approved": "false", "status": "BLOCKED" if blocked else "READY_FOR_REVIEW", "pinterest_pin_id": "", "published_at": ""}
        if row_id in by_id:
            saved = by_id[row_id]
            new_row["approved"] = saved.get("approved", "false")
            new_row["pinterest_pin_id"] = saved.get("pinterest_pin_id", "")
            new_row["published_at"] = saved.get("published_at", "")
            if saved.get("status") == "PUBLISHED":
                new_row["status"] = "PUBLISHED"
        by_id[row_id] = new_row
    with queue_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(by_id.values())

    kpis = aggregate_kpis(read_csv(ROOT / "data/kpi.csv"), offer["offer_id"])
    launch = datetime.strptime(settings["launch_date"], "%Y-%m-%d").date()
    elapsed = max(0, (run_date - launch).days)
    status, next_action = decision(elapsed, kpis)
    report = {"generated_at": run_date.isoformat(), "days_since_launch": elapsed, "offer_id": offer["offer_id"], **kpis, "decision": status, "next_action": next_action}
    write_text(ROOT / "generated/reports/latest.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    homepage = f'<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(settings["site_name"])}</title><body style="font-family:system-ui;max-width:760px;margin:40px auto;padding:20px"><h1>{html.escape(settings["site_name"])}</h1><p><a href="generated/articles/{quote(slug)}.html">最新記事：{html.escape(title)}</a></p></body></html>'
    write_text(ROOT / "index.html", homepage)
    write_text(ROOT / "generated/index.html", homepage.replace('href="generated/', 'href="'))
    write_text(ROOT / "generated/manifest.json", json.dumps({"content_id": content_id, "topic": topic, "article": str(article_path.relative_to(ROOT)), "image": str(image_path.relative_to(ROOT)), "queue": str(queue_path.relative_to(ROOT))}, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"content_id": content_id, "queue_status": "BLOCKED" if blocked else "READY_FOR_REVIEW", "decision": status}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()
    run(datetime.strptime(args.date, "%Y-%m-%d").date())
