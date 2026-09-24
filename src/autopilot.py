"""Offline, repeatable content-to-queue cycle. No Pinterest network calls."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode

from pipeline import ROOT, affiliate_url, build_png, load_json, markdown_to_html, read_csv, write_text

QUEUE_FIELDS = ["content_id", "title", "description", "article_url", "image_url", "affiliate_url", "manual_create_url", "approved", "status", "pinterest_pin_id", "published_at", "topic_id", "pin_id", "alt_text", "image_prompt", "destination_url", "utm_campaign", "created_at"]
PERFORMANCE_FIELDS = ["date", "topic_id", "pin_id", "impressions", "outbound_clicks", "signups", "sales", "revenue_jpy"]
HOOKS = [
    ("A simpler first funnel", "Start with one landing page, one welcome email and one clear offer."),
    ("Cut the tool stack", "See a practical small business setup before adding another subscription."),
    ("Launch the first version", "Use this checklist to build, test and improve a simple funnel."),
]
IMAGE_HEADLINES = ["START GUIDE", "EMAIL GUIDE", "FUNNEL GUIDE"]


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def fingerprint(value: str) -> str:
    return hashlib.sha256(norm(value).encode()).hexdigest()[:16]


def load_state(root: Path) -> dict:
    path = root / "generated/autopilot_state.json"
    return load_json(path) if path.exists() else {"processed": {}, "paused": [], "expansion_candidates": []}


def select_candidate(topics: list[dict], state: dict) -> dict | None:
    processed = state.get("processed", {})
    paused = set(state.get("paused", []))
    seen = {fingerprint(x.get("keyword", "")) for x in processed.values()}
    candidates = state.get("expansion_candidates", []) + topics
    eligible = [t for t in candidates if t["topic_id"] not in processed and t["topic_id"] not in paused and fingerprint(t["keyword"]) not in seen]
    eligible.sort(key=lambda t: (-(int(t.get("intent", 3)) + int(t.get("evergreen", 3)) - int(t.get("saturation", 3))), t["topic_id"]))
    return eligible[0] if eligible else None


def evaluate_performance(rows: list[dict], topic_id: str, created: date, today: date) -> dict:
    totals = {k: 0 for k in ("impressions", "outbound_clicks", "signups", "sales", "revenue_jpy")}
    for row in rows:
        if row.get("topic_id") != topic_id:
            continue
        try:
            observed = date.fromisoformat(row["date"])
            if not (created <= observed <= today):
                continue
            for key in totals:
                totals[key] += int(float(row.get(key) or 0))
        except (ValueError, TypeError):
            continue
    age = max(0, (today - created).days)
    window = 30 if age >= 30 else 14 if age >= 14 else 7 if age >= 7 else 0
    decision = "INSUFFICIENT_DATA"
    if window and totals["impressions"] >= {7: 100, 14: 300, 30: 500}[window]:
        ctr = totals["outbound_clicks"] / totals["impressions"]
        if totals["sales"] > 0 or totals["signups"] >= 3 or (window == 7 and ctr >= .02) or (window == 14 and totals["signups"] >= 1):
            decision = "EXPAND"
        elif (window >= 14 and ctr < .005) or (window == 30 and totals["signups"] == 0):
            decision = "PAUSE"
        else:
            decision = "KEEP"
    return {"topic_id": topic_id, "age_days": age, "window_days": window, **totals, "decision": decision}


def apply_decisions(state: dict, rows: list[dict], today: date) -> list[dict]:
    reports = []
    for topic_id, meta in state.get("processed", {}).items():
        report = evaluate_performance(rows, topic_id, date.fromisoformat(meta["created_at"]), today)
        reports.append(report)
        if report["decision"] == "PAUSE" and topic_id not in state["paused"]:
            state["paused"].append(topic_id)
            state["expansion_candidates"] = [x for x in state["expansion_candidates"] if x.get("parent_topic_id") != topic_id]
        if report["decision"] == "EXPAND" and not meta.get("expanded"):
            child = {"topic_id": f"{topic_id}_expand", "parent_topic_id": topic_id, "offer_id": meta["offer_id"], "keyword": f"{meta['keyword']} checklist", "pain": meta["pain"], "angle": "a focused checklist for the next test", "intent": "4", "evergreen": "5", "saturation": "3"}
            state["expansion_candidates"].append(child)
            meta["expanded"] = True
    return reports


def build_content(topic: dict, offer: dict, settings: dict, topic_id: str, link: str) -> tuple[str, str]:
    keyword = topic["keyword"]
    title = f"{keyword.title()}: A Practical First Setup for Small Businesses"
    body = f"""# {title}

Disclosure: This article contains an affiliate link. We may earn a commission if you sign up, at no extra cost to you.

If {topic['pain'].lower()}, start with a small test you can actually finish. This guide focuses on {topic['angle'].lower()}.

## What to build first

1. Pick one offer and one audience. Write down the problem the offer solves.
2. Create one landing page with a clear headline, a short explanation and a single call to action.
3. Connect one welcome email. Explain what the visitor receives and what happens next.
4. Test the signup and every link yourself on a phone and a desktop browser.
5. Review visits, clicks and signups after a week before adding more tools.

## Where {offer['name']} fits

{offer['name']} is one option for building a landing page and email flow in the same place. Compare its current plan limits and terms with your needs before committing. A free starting option can help you test the workflow, but features and prices can change.

## A useful decision rule

Keep the first version if visitors understand the offer and complete the intended action. If they leave without clicking, rewrite the headline and simplify the page. If they click but do not sign up, check the form and the promise made by the call to action. Do not treat a small sample as proof of future income.

## Next step

Use the [small business AI tools overview]({settings['existing_landing_url']}) for context, then [check {offer['name']} on its official site]({link}) if it fits your setup.

Topic ID: `{topic_id}`
"""
    return title, body


def quality_check(title: str, article: str, topic: dict, link: str) -> dict:
    issues = []
    if len(article.split()) < 180: issues.append("article_too_short")
    if topic["keyword"].casefold() not in article.casefold(): issues.append("keyword_missing")
    if "Disclosure:" not in article or link not in article: issues.append("disclosure_or_cta_missing")
    if len(title) > 110: issues.append("title_too_long")
    if re.search(r"guaranteed income|earn \$\d+|verified review", article, re.I): issues.append("unsupported_claim")
    return {"result": "PASS" if not issues else "FAIL", "issues": issues}


def save_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run(root: Path = ROOT, today: date | None = None, dry_run: bool = False) -> dict:
    today = today or date.today()
    settings = load_json(root / "config/settings.json")
    offers = {o["offer_id"]: o for o in read_csv(root / "data/offers.csv") if o["active"].lower() == "true"}
    topics = [t for t in read_csv(root / "data/topics_en.csv") if t["offer_id"] in offers]
    state = load_state(root)
    perf_path = root / "data/performance.csv"
    performance = read_csv(perf_path) if perf_path.exists() else []
    reports = apply_decisions(state, performance, today)
    topic = select_candidate(topics, state)
    summary = {"selected_topic": "NONE", "quality_result": "NOT_RUN", "generated_article": "NONE", "pins_created": 0, "queue_status": "UNCHANGED", "next_action": "Add new English topics to data/topics_en.csv"}
    queue_path = root / "generated/autopilot_queue.csv"
    queue = read_csv(queue_path) if queue_path.exists() else []
    if topic:
        topic_id = topic["topic_id"]
        offer = offers[topic["offer_id"]]
        affiliate = affiliate_url(offer["base_url"], settings["affiliate_id"], topic_id)
        title, article = build_content(topic, offer, settings, topic_id, affiliate)
        quality = quality_check(title, article, topic, affiliate)
        summary.update(selected_topic=topic_id, quality_result=quality["result"])
        if quality["result"] == "PASS":
            slug = topic_id
            article_file = f"generated/articles/{slug}.html"
            article_url = settings["site_base_url"].rstrip("/") + "/" + article_file
            summary["generated_article"] = article_file
            new_rows = []
            existing_copies = {fingerprint(r.get("title", "") + " " + r.get("description", "")) for r in queue}
            for i, (hook, explanation) in enumerate(HOOKS, 1):
                pin_id = f"{topic_id}-p{i}"
                pin_title = f"{topic['keyword'].title()}: {hook}"
                description = f"{explanation} Read the {topic['keyword']} guide. Affiliate disclosure on the page."
                if fingerprint(pin_title + " " + description) in existing_copies:
                    continue
                utm = {"utm_source": "pinterest", "utm_medium": "organic", "utm_campaign": topic_id, "utm_content": pin_id}
                destination = article_url + "?" + urlencode(utm)
                image_file = f"generated/images/{pin_id}.png"
                image_url = settings["site_base_url"].rstrip("/") + "/" + image_file
                prompt = f"Vertical 2:3 Pinterest graphic, accessible high contrast, clean SaaS checklist layout, topic: {topic['keyword']}, hook: {hook}; no product logos, no earnings claims"
                row = {"content_id": pin_id, "topic_id": topic_id, "pin_id": pin_id, "title": pin_title[:100], "description": description[:500], "alt_text": f"Systeme.io guide graphic reading {IMAGE_HEADLINES[i - 1]}", "image_prompt": prompt, "article_url": article_url, "destination_url": destination, "image_url": image_url, "affiliate_url": affiliate_url(offer["base_url"], settings["affiliate_id"], pin_id), "manual_create_url": "https://www.pinterest.com/pin/create/button/?" + urlencode({"url": destination, "media": image_url, "description": description}), "approved": "false", "status": "WAITING_FOR_STANDARD", "pinterest_pin_id": "", "published_at": "", "utm_campaign": topic_id, "created_at": today.isoformat()}
                new_rows.append(row)
                existing_copies.add(fingerprint(pin_title + " " + description))
            summary.update(pins_created=len(new_rows), queue_status="WAITING_FOR_STANDARD", next_action="Await Pinterest Standard access; queue is ready")
            if not dry_run:
                write_text(root / f"generated/articles/{slug}.md", article)
                write_text(root / article_file, markdown_to_html(article, title).replace('lang="ja"', 'lang="en"'))
                for row in new_rows:
                    build_png(root / f"generated/images/{row['pin_id']}.png", IMAGE_HEADLINES[int(row["pin_id"].rsplit("p", 1)[1]) - 1], topic["keyword"])
                queue.extend(new_rows)
                fields = list(dict.fromkeys(QUEUE_FIELDS + [key for row in queue for key in row]))
                save_csv(queue_path, queue, fields)
                state["processed"][topic_id] = {"created_at": today.isoformat(), "keyword": topic["keyword"], "pain": topic["pain"], "offer_id": topic["offer_id"]}
                state["expansion_candidates"] = [x for x in state["expansion_candidates"] if x["topic_id"] != topic_id]
        else:
            summary["next_action"] = "Resolve quality issues: " + ", ".join(quality["issues"])
    if not dry_run:
        write_text(root / "generated/autopilot_state.json", json.dumps(state, indent=2, ensure_ascii=False) + "\n")
        write_text(root / "generated/reports/performance.json", json.dumps({"as_of": today.isoformat(), "topics": reports}, indent=2) + "\n")
        write_text(root / "generated/reports/autopilot_latest.json", json.dumps(summary, indent=2) + "\n")
    github_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if github_summary:
        with open(github_summary, "a", encoding="utf-8") as f:
            f.write("## SaaS affiliate autopilot\n\n" + "\n".join(f"- **{k}**: {v}" for k, v in summary.items()) + "\n")
    print(json.dumps(summary))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", choices=["autopilot"], default="autopilot")
    parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(today=args.date, dry_run=args.dry_run)
