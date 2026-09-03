# Pinterest運用：承認前と承認後

## 承認前（v1の既定運用）

1. GitHub Actionsで候補を生成する。
2. `generated/publish_queue.csv` のタイトル、説明、リンク、画像を目視する。
3. 採用する1行の `manual_create_url` をブラウザで開く。
4. Pinterest画面でボードと画像を確認して投稿する。
5. 1日1件を上限の初期値にし、似たPinの大量投稿を避ける。

記事とPinには広告開示を入れ、短縮URLは使いません。Pinterest公式ガイドは、アフィリエイト投稿に独自価値と透明性を求め、反復的・大量の投稿を避けるよう定めています。

## API申請

1. Pinterest Businessアカウントを作成または切り替え、メールを認証する。
2. Developerサイトの「My apps」でDeveloper Termsに同意する。
3. 「Connect app」からアプリ名、用途、運営サイト、プライバシーポリシー等を入力し、Trial accessを申請する。
4. 承認後、アプリのConfigureでredirect URIを完全一致で登録する。
5. 最小権限 `boards:read,boards:write,pins:read,pins:write` でOAuthまたはテストトークンを使って疎通する。
6. 本番規模が必要なら、動作デモ動画とプライバシーポリシーを用意してStandard accessへUpgrade申請する。

公式資料:

- https://developers.pinterest.com/docs/getting-started/connect-app/
- https://developers.pinterest.com/docs/getting-started/set-up-authentication-and-authorization/
- https://developers.pinterest.com/docs/work-with-organic-content-and-users/create-boards-and-pins/
- https://developers.pinterest.com/docs/key-concepts/access-tiers/
- https://policy.pinterest.com/en/commercial-and-branded-content-guidelines

## GitHub側の本番設定

Repository Settings → Secrets and variables → Actions に以下を登録します。

- `PINTEREST_ACCESS_TOKEN`
- `PINTEREST_BOARD_ID`

その後、公開したい行だけ `approved` を `true` に変更し、`Publish approved Pinterest rows` を手動実行します。GitHub Environment `production` にrequired reviewerを設定すると、最後の承認操作を強制できます。

トークンはコミットしないでください。現行OAuthではアクセストークンは30日以内に更新し、継続リフレッシュトークンは60日で期限切れになる前に更新します。

