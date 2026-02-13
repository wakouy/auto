# Auto Revenue Lab

日本語AIツール特化の、自動投稿 + 自動レポートの最小収益化システムです。

## できること
- 日次: キーワード選定 -> 記事生成 -> 品質ゲート -> `content/posts/` に自動保存
- 日次: GitHub Actionsで自動コミットしてGitHub Pages公開
- 週次: PV/クリックから推定収益レポートを `reports/` に生成
- 規約対応: 広告表記ページ・プライバシーページを常設

## 必須構成
- 設定: `config/system.yaml`
- ツール台帳: `data/tools.csv`
- キーワード台帳: `data/keywords.csv`
- 記事: `content/posts/YYYY-MM-DD-<slug>.md`
- 法令: `content/legal/disclosure.md`, `content/legal/privacy.md`
- ワークフロー: `.github/workflows/publish.yml`, `.github/workflows/weekly_report.yml`

## 初期セットアップ
1. GitHubリポジトリを作成し、このディレクトリをpush
2. GitHub Pagesを有効化（Actionsからデプロイ）
3. Secretsを設定
   - `HUGGINGFACE_API_TOKEN`（任意。未設定時はテンプレ記事生成）
   - `GA4_PROPERTY_ID`（任意）
   - `GA4_SERVICE_ACCOUNT_JSON`（任意）
4. `config/system.yaml` の `site.base_url` を実URLへ更新
5. `data/tools.csv` の `affiliate_url` をASP発行リンクへ更新

## ローカル実行
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m scripts.publish --config config/system.yaml --mock
python -m scripts.weekly_report --config config/system.yaml
```

## テスト
```bash
pytest -q
```

## 運用メモ
- `tools.csv` の `status` が `approved` / `active` / `affiliate_ready` の場合、`affiliate_url` をCTAに利用
- それ以外は `official_url` を利用（ASP審査中向け）
- `data/costs.csv` の当月 `total_usd` が `cost.max_monthly_usd` を超えると、奇数日は投稿を自動スキップ
