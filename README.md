# Auto Revenue Lab

日本語AIツール特化の、自動投稿 + 自動レポートのハイブリッド収益化システムです。

## できること
- 日次: キーワード選定 -> 記事生成 -> 品質ゲート -> `content/posts/` に自動保存
- 日次: GitHub Actionsで自動コミットしてGitHub Pages公開
- 日次: キーワード在庫を自動補充（投稿ネタ切れ防止）
- 日次: GA4メトリクスを `data/analytics_metrics.csv` に自動同期（設定時）
- 週次: Affiliate推定収益 + AdSense実績(手入力CSV)の合算レポートを `reports/` に生成
- 週次: Search Console提出チェックリストを `reports/search-console-checklist.md` に生成
- 日次/週次: 進捗と収益を `content/dashboard.md` と `reports/monetization-dashboard.md` に自動更新
- 規約対応: 広告表記ページ・プライバシーページを常設
- 規約対応: 利用規約ページ + Cookie同意バナー（同意前はGA停止）
- 同意後のみ GA4 と AdSense Auto Ads を読み込み
- 収益優先: `approved/active` かつ実リンクの案件を優先投稿

## 必須構成
- 設定: `config/system.yaml`
- ツール台帳: `data/tools.csv`
- キーワード台帳: `data/keywords.csv`
- AdSense実績台帳: `data/ad_revenue.csv`
- ダッシュボード(公開): `content/dashboard.md` (`/dashboard/`)
- ダッシュボード(詳細): `reports/monetization-dashboard.md`
- 記事: `content/posts/YYYY-MM-DD-<slug>.md`
- 法令: `content/legal/disclosure.md`, `content/legal/privacy.md`
- 法令: `content/legal/disclosure.md`, `content/legal/privacy.md`, `content/legal/terms.md`
- ワークフロー: `.github/workflows/publish.yml`, `.github/workflows/weekly_report.yml`
- 日次メトリクス: `.github/workflows/daily_metrics.yml`

## 初期セットアップ
1. GitHubリポジトリを作成し、このディレクトリをpush
2. GitHub Pagesを有効化（Actionsからデプロイ）
3. Secretsを設定
   - `HUGGINGFACE_API_TOKEN`（任意。未設定時はテンプレ記事生成）
   - `GA4_PROPERTY_ID`（任意）
   - `GA4_SERVICE_ACCOUNT_JSON`（任意）
4. `config/system.yaml` の `site.base_url` を実URLへ更新
5. `_config.yml` の `ga4_measurement_id` と `adsense_publisher_id` を設定（未設定でも動作は継続）
6. `data/tools.csv` の `affiliate_url` をASP発行リンクへ更新

## ローカル実行
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m scripts.publish --config config/system.yaml --mock
python -m scripts.weekly_report --config config/system.yaml
python -m scripts.sync_ga4_metrics --config config/system.yaml --metrics data/analytics_metrics.csv
python -m scripts.refresh_keywords --config config/system.yaml --keywords data/keywords.csv --tools data/tools.csv
python -m scripts.monetization_audit --config config/system.yaml
python -m scripts.search_console_checklist --config config/system.yaml --output reports/search-console-checklist.md
python -m scripts.ad_revenue_validate --file data/ad_revenue.csv
python -m scripts.update_dashboard --config config/system.yaml --site-config _config.yml --tools data/tools.csv --metrics data/analytics_metrics.csv --ad-revenue data/ad_revenue.csv --output-report reports/monetization-dashboard.md --output-site content/dashboard.md
```

## テスト
```bash
pytest -q
```

## 運用メモ
- `tools.csv` の `status` が `approved` / `active` / `affiliate_ready` の場合、`affiliate_url` をCTAに利用
- それ以外は `official_url` を利用（ASP審査中向け）
- `data/costs.csv` の当月 `total_usd` が `cost.max_monthly_usd` を超えると、奇数日は投稿を自動スキップ
- `content.posts_per_run` を `2` 以上にすると1回の実行で複数記事を生成可能
- `affiliate_url` が `example.com` などのダミー値の場合は収益案件として扱わず、公式URLへフォールバック
- CTAは2箇所以上を自動挿入し、クリック機会を増やす
- `growth.min_keyword_pool` / `growth.keyword_add_limit` でキーワード補充量を制御可能
- AdSense収益は `data/ad_revenue.csv` に週1回手入力（`date,adsense_revenue_usd,source,note`）
- `adsense_publisher_id` が空の間は広告タグを読み込まない（審査前の安全運用）
- 進捗は公開ページ `/dashboard/` で即確認、詳細は `reports/monetization-dashboard.md` を確認
