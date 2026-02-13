---
layout: default
title: "記事一覧"
permalink: /
---

# 自動生成記事

運用方針: 本サイトはAIツール情報を定期公開し、広告・アフィリエイトリンクを含みます。

{% assign generated_posts = site.pages | where: "autogen_post", true | sort: "date" | reverse %}

{% if generated_posts.size > 0 %}
<ul class="post-list">
  {% for post in generated_posts %}
  <li>
    <a href="{{ post.url | relative_url }}">{{ post.title }}</a>
    <span>{{ post.date | date: "%Y-%m-%d" }}</span>
  </li>
  {% endfor %}
</ul>
{% else %}
まだ記事はありません。自動投稿ジョブの初回実行後に表示されます。
{% endif %}
