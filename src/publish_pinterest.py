from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    token = os.getenv("PINTEREST_ACCESS_TOKEN")
    board_id = os.getenv("PINTEREST_BOARD_ID")
    if not token or not board_id:
        raise SystemExit("Pinterest secrets are missing; no posts were sent.")
    queue_path = ROOT / "generated/publish_queue.csv"
    rows = list(csv.DictReader(queue_path.open(encoding="utf-8-sig")))
    approved = [r for r in rows if r["approved"].lower() == "true" and r["status"] == "READY_FOR_REVIEW"]
    if not approved:
        print("No approved rows; no posts were sent.")
        return
    for row in approved:
        payload = {
            "board_id": board_id,
            "title": row["title"],
            "description": row["description"],
            "link": row["article_url"],
            "media_source": {"source_type": "image_url", "url": row["image_url"]},
        }
        req = Request("https://api.pinterest.com/v5/pins", data=json.dumps(payload).encode(), method="POST", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read())
            row["pinterest_pin_id"] = result["id"]
            row["published_at"] = datetime.now(timezone.utc).isoformat()
            row["status"] = "PUBLISHED"
            print(response.status, result["id"])
    with queue_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
