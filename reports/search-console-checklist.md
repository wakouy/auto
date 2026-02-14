# Search Console 提出チェックリスト

- 生成日時: 2026-02-14 12:24 JST
- 対象サイト: https://wakouy.github.io/auto
- 自動チェック: 15/15 PASS

## 自動チェック結果
- [x] site.base_url が https で設定済み（https://wakouy.github.io/auto）
- [x] GA4 Measurement ID が設定済み（G-7Z5Y9GS01K）
- [x] AdSense Publisher ID 形式が妥当（ca-pub-8816776160139989）
- [x] robots.txt がリポジトリに存在（/Users/shimojikouichi/Documents/auto/robots.txt）
- [x] sitemap.xml がリポジトリに存在（/Users/shimojikouichi/Documents/auto/sitemap.xml）
- [x] 広告表記ページが存在（/Users/shimojikouichi/Documents/auto/content/legal/disclosure.md）
- [x] プライバシーポリシーが存在（/Users/shimojikouichi/Documents/auto/content/legal/privacy.md）
- [x] 利用規約ページが存在（/Users/shimojikouichi/Documents/auto/content/legal/terms.md）
- [x] Cookie同意バナー(同意前GA停止)が実装済み（_layouts/default.html）
- [x] 同意後のみAdSense読込が実装済み（_layouts/default.html）
- [x] data/ad_revenue.csv が存在し形式が妥当（/Users/shimojikouichi/Documents/auto/data/ad_revenue.csv (valid)）
- [x] 収益化リンク(approved/active)が1件以上（3件）
- [x] 公開サイトが到達可能（HTTP 200）
- [x] 公開 sitemap.xml が到達可能（HTTP 200）
- [x] 公開 robots.txt が到達可能（HTTP 200）

## 手動チェック（Search Consoleで1回だけ実施）
- [ ] Search ConsoleでURLプレフィックス プロパティを追加
- [ ] 所有権確認を完了（対象: https://wakouy.github.io/auto）
- [ ] `sitemap.xml` を送信（https://wakouy.github.io/auto/sitemap.xml）
- [x] AdSense審査/Publisher ID設定は完了
- [x] GA4 Measurement ID設定は完了
- [ ] インデックス未登録ページがあれば原因を確認
- [ ] 主要記事URLをURL検査で送信

## 運用ルール
- 週1回このチェックを見て、未達項目だけ修正する。
- `公開 sitemap.xml` と `公開 robots.txt` がFAILなら最優先で修正する。
