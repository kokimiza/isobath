# 人格海図 ISOBATH

<!-- impeccable:product-schema 1 -->

## Platform

web

## Product Purpose

独自の観測項目への回答を継続的に集め、回答分布から人格に関連する地形を探索的に可視化する。参加者は診断対象ではなく、海図をつくる観測点になる。

## Users

公開海図を見る未登録訪問者と、初回・継続測深に回答し現在地や航跡を確認する観測参加者。根拠: doc/requirements.md §3。

## Capabilities and Constraints

Svelte 5 / SvelteKit / Tailwind CSS 4。日本語・英語。バックエンド、API契約、認証、同意、回答保存、日次更新の動作を保つ。未測量時に現在地や海域を作り上げない。人数・段階は実データのみ。参照優先順位は requirements.md > concept.md。

## Brand Commitments

ユーザー指定: 「明るいお風呂の中に深海がある感じ」。サービス名と、人格を固定タイプに分類せず継続観測する思想を保つ。

## Evidence on Hand

doc/concept.md、doc/requirements.md、doc/design.md、messages/ja.json、messages/en.json、既存の動作するSvelte画面。レビュー用の説明図は実測海図と明確に区別する。

## Product Principles

- 人格の位置に優劣をつけない。
- 統計的不確実性と暫定段階を隠さない。
- 個人の変化と海図改訂を区別する。
- 医療・能力・適性の診断を標榜しない。
- 海図は完成せず、観測とともに変化する。
