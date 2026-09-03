# SaaS Affiliate Autopilot v1

Systeme.ioを最初の検証案件にした、固定費ほぼゼロのアフィリエイト運用パイプラインです。
GitHub Actionsが毎日、案件DBからテーマを選び、記事・Pin文案・固定テンプレ画像・公開キュー・KPI判定を生成します。

## v1の範囲

- 自動: 案件DB読込 → テーマ選定 → 記事生成 → Pin 3案生成 → SVG画像生成 → 公開候補生成 → KPI集計 → 7/14/30日判定
- 承認前: `generated/publish_queue.csv` のリンクから、Pinterestの公式作成画面を1件ずつ開いて最終確認・投稿
- API承認後: GitHub Secretsを設定すると、承認済み行だけPinterest APIへ投稿可能
- 人が行うこと: アカウント作成・本人確認・OAuth/Secret登録・各投稿の最終承認

## 最初の1サイクル

```text
1. config/settings.json の affiliate_id を設定
2. GitHubへpush
3. Actions > Build affiliate cycle > Run workflow
4. generated/publish_queue.csv で候補を確認
5. KPIを data/kpi.csv に追記（またはworkflow入力で記録）
```

ローカルでは `python src/pipeline.py`、テストは `python -m unittest discover -s tests -v` です。追加パッケージは不要です。

## 重要

- `affiliate_id` が `REPLACE_ME` の間は、誤投稿防止のため公開キューが `BLOCKED` になります。
- Systeme.ioリンクは公式仕様に合わせ、`www`なしの `https://systeme.io/...?...sa=ID` を使います。
- 誇張した収益表現や架空レビューは生成しません。記事とPinに広告開示を入れます。
- APIトークンはリポジトリに保存せず、GitHub Secretsだけに保存してください。
- 自動投稿の既定値はOFFです。`approved=true` の行だけが対象です。

詳しいPinterest申請・暫定運用は [docs/pinterest-operations.md](docs/pinterest-operations.md) を参照してください。

