# SaaS Affiliate Autopilot

The weekly **SaaS affiliate autopilot** GitHub Action selects one unused English topic, writes a landing article with an affiliate disclosure and CTA, checks basic quality, creates three distinct Pin drafts and PNG graphics, adds Pin-level UTM links, and saves a queue. It runs without paid services or credentials. Previous Japanese content and queue rows remain intact.

## Normal operation

The workflow runs every Monday at 22:17 UTC. No daily action is needed. To run once manually: **Actions → SaaS affiliate autopilot → Run workflow**; leave `command=autopilot`. The run summary shows `selected_topic`, `quality_result`, `generated_article`, `pins_created`, `queue_status`, and `next_action`. Choose `dry_run=true` to preview without changing generated files or state. The workflow saves new files only after a normal run.

Generated pages, images, queue (`generated/autopilot_queue.csv`) and reports are in `generated/`. The previous `generated/publish_queue.csv` and published Pin history are untouched. Pin destination URLs point to the repository's configured GitHub Pages address. Ensure GitHub Pages publishes `main` from the repository root before using those links publicly. The existing [systeme.io overview](https://smallbizaitools.systeme.io/ai-tools-small-business) is linked from each new article.

## Pinterest access

The current Developer app is **SaaS Affiliate Autopilot, ID 1607856**. Trial is pending. The publisher is OFF and all new queue rows are `WAITING_FOR_STANDARD`; no Pinterest API request is made by the content workflow. The rejected app 1607850 is never used.

After Trial approval, connect app 1607856 via OAuth and test in Trial, then request Standard access. When Standard is actually approved, configure repository variables `PINTEREST_APP_ID=1607856`, `PINTEREST_ACCESS_TIER=standard`, `PINTEREST_PUBLISH_ENABLED=true` and repository secrets `PINTEREST_ACCESS_TOKEN`, `PINTEREST_BOARD_ID` for the **AI Tools for Small Business** board. The daily publisher workflow will then publish at most one waiting Pin per run and record the returned Pinterest ID. Keep the enable variable unset until Standard approval and confirm the Pages article and image URLs work. Tokens are never stored in the repository.

## Performance and content supply

`data/performance.csv` accepts **daily increments**, with `date,topic_id,pin_id,impressions,outbound_clicks,signups,sales,revenue_jpy`. Import actual Pinterest/affiliate results when available; no results are invented. `generated/reports/performance.json` evaluates each topic after 7, 14 and 30 days. Missing or small samples remain `INSUFFICIENT_DATA`; strong results become `EXPAND` and add one related topic; weak results become `PAUSE` and remove that topic's pending expansion. Otherwise the decision is `KEEP`. Topic IDs and Pin IDs in the queue and UTM links allow later attribution. Unused seed topics are in `data/topics_en.csv`; after they are exhausted, the workflow reports `NONE` until new topics or performance-driven expansions are available.

Run locally with `python src/autopilot.py --command autopilot` or `python src/autopilot.py --dry-run`. Tests: `python -m unittest discover -s tests -v`. No third-party Python packages are required.
