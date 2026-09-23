# 人格海図 ISOBATH

> 2026-09-23追補（研究専用属性）：`app.research_demographics(user_id,birth_year,birth_month,gender,collected_at)` を追加。出生年月と性別4択、4必須確認は独立した事前画面 `/auth/signup` で入力し、タブ内の期限付きドラフトとして保持する。次の `/auth/register` でGoogleを主手段、メール・パスワードを代替として選ぶ。Authには属性を送らず、新規認証アカウントは `app.pending_registrations` に置く。認証後の `POST /v1/me/registration` がJWTの本人に限定して専用DB関数で属性を書き込み、同意イベントと一つのトランザクションで確定する。未完了者は測深できず、ドラフト消失・別端末では `/consent` で再入力する。既存アカウントは未入力のまま扱い、APIには属性のSELECT権限を与えない。`analysis.research_demographics` は研究説明書版2への最新同意者のみをpipelineへ返す。年齢はcutoffの先月末（JST）基準。非公開の研究用補助回帰に限定し、MFM・個人位置・設問選択へ渡さない。削除時CASCADE。詳細は statistics.md §12.1 と `20260923010000_research_demographics.sql`。
## 設計書 v1.0

| 項目 | 内容 |
|---|---|
| 対象 | MVP（Pilot Phase 1） |
| 作成日 | 2026-09-21 |
| 上位文書 | [requirements.md](requirements.md)（要件）、[concept.md](concept.md)（企画）、[observation-domains.md](observation-domains.md)（観測領域） |

本書は requirements.md の要件を満たす実装方法を定める。要件IDを括弧で示す。

統計処理の現行実装・実行手順・検証対応は [statistics-implementation.md](statistics-implementation.md) を参照する。統計モデルと推論の正本は [statistics.md](statistics.md) v0.3である。

---

# 1. 設計上の主要決定

| # | 決定 | 理由 |
|---|---|---|
| D-1 | アプリのテーブルは Supabase Data API（PostgREST）に**公開しない**。`app` スキーマに置き、FastAPI だけが直接接続してアクセスする | ブラウザは Publishable Key とユーザーのJWTを持っている。テーブルを公開すると、FastAPI の検証を迂回して PostgREST から直接書き込めてしまう |
| D-2 | FastAPI は専用ロール `isobath_api` で接続し、リクエストごとのトランザクション内で `SET LOCAL ROLE authenticated` と `request.jwt.claims` を設定する（requirements Q-11 の決定） | RLS をユーザー権限で効かせたまま、「割り当ての検証＋INSERT」を一つのトランザクションにできる（SEC-AUTH-03、SEC-AUTH-04） |
| D-3 | 割り当ての検証を複合外部キーでDBに持たせる。`answers(session_id, question_id)` → `survey_session_questions` | アプリにバグがあっても、割り当てていない項目への回答をDBが拒否する（DR-04） |
| D-4 | 現在地は、**順序尺度の因子モデルの事後分布**で推定する。欠けている項目は、尤度に現れないだけで自然に扱える（[statistics.md](statistics.md) §7.1） | 5件法を順序として扱ったまま、部分的な回答からの推定と不確実性を同時に得られる（ST-POS-02、ST-POS-03、ST-MIS-04） |
| D-5 | モデルの成果物は `npz` と `json` で保存し、pickle を使わない。位置の計算は日次バッチだけが行い、numpy で足りる | pickle の読み込みはコード実行のリスクがある。推定に使う scipy / arviz を API の実行環境に入れずに済み、メモリも節約できる（NFR-PRF-02、NFR-PRF-06） |
| D-6 | アカウントの削除は、DBの `SECURITY DEFINER` 関数で行う | 通常のAPIに service_role を持たせずに、`auth.users` まで削除できる（SEC-AUTH-05） |
| D-7 | 登録（Signup）は Supabase Auth が直接受け付けるので、Cloudflare を通らない。Bot 対策には、Supabase Auth 組み込みの CAPTCHA 連携（Turnstile）と Rate Limit を使う | Cloudflare の Rate Limit は Signup に効かない（SEC-NET-04、§9.4 Signup） |
| D-8 | ブロックの割り当ては、10ブロックから3つを選ぶ全組み合わせ（120通り）から一様ランダムに選ぶ | 項目ペアの共回答率が期待値で完全に均等になる。回答者のデータに依存しないのでMCARになる（ST-PMD-04） |
| D-9 | モデルの成果物（`app/models/chart-{v}/` と `CURRENT`）はリポジトリで管理し、診断値とレポートのレビュー後にマージする。**マージしたモデルは、次の日次バッチの時点で有効になる**（§7.1） | 日中に版が変わらない（requirements FR-UNC-06）。API はモデルで位置を計算しないため、Pages と Render のデプロイ順を気にする必要がない |
| D-10 | 海図の版・海域・診断値は、成果物の metadata を正とする。DBには `chart_version` の文字列だけを持つ | requirements §11.1 の `chart_versions`、`regions`、`item_blocks` テーブルは作らない。それぞれ成果物と `questions.block_no` で代替する。lineage を実装する時点（LATER）でテーブル化する |
| D-11 | 海図と現在地は、**GitHub Actions の schedule で毎日 01:00 JST に起動する日次バッチ**（`app/isobath/nightly.py`）だけが更新する。対象は `survey_sessions.completed_at < 締め時刻` で決める。参加人数は集計値のため完了時点で反映する | 無料枠で既存の Python コードを定期実行できる。起動の遅れ・取りこぼし・再実行があっても、対象データは締め時刻だけで決まる（requirements §4.1） |
| D-12 | 日次バッチの実行記録と生成した海図は `app.batch_runs` に保存し、`(cutoff_at)` を一意にする。現在地のスナップショットは `(user_id, cutoff_at)` を一意にする | 同じ締め時刻での再実行が冪等になる（FR-BAT-06、FR-BAT-11） |
| D-13 | 海図（密度グリッド）は Pages の静的ファイルではなく、`GET /v1/chart/current` で配信し、次の締め時刻までを `max-age` として Cloudflare にキャッシュさせる | 毎日変わるものを、毎日 Pages を再デプロイせずに配信できる。1日1回しか変わらないため API の負荷はほぼ一定 |

---

# 2. リポジトリ構成

    isobath/
    ├── src/                      フロントエンド（SvelteKit）
    ├── .github/workflows/
    │   └── nightly.yml           日次バッチ（毎日 01:00 JST）
    ├── static/                   静的資産（Cloudflare Pages）
    │   └── _headers              セキュリティヘッダ
    ├── messages/                 UI文言（paraglide: ja / en）
    ├── app/                      バックエンド（Python）
    │   ├── pyproject.toml
    │   ├── uv.lock
    │   ├── isobath/              FastAPI とオンライン推論
    │   ├── pipeline/             オフラインの統計パイプライン
    │   ├── models/               モデルの成果物（パイプラインが出力）
    │   ├── items/                項目バンク（CSV）
    │   └── tests/
    ├── supabase/                 DBスキーマ（Supabase CLI の規約）
    │   ├── migrations/
    │   └── config.toml
    └── doc/

`supabase/` は、Supabase CLI の規約に従ってリポジトリの直下に置く。マイグレーションは、フロントエンドとバックエンドのどちらにも属さないため。

---

# 3. システム構成

    Browser
      │
      ├── HTTPS ──► Cloudflare Pages
      │               isobath.jocarium.productions
      │               静的HTML/JS
      │
      ├── HTTPS ──► Supabase Auth
      │               登録（CAPTCHA）、ログイン、JWTの発行
      │
      └── HTTPS ──► Cloudflare（Proxy / WAF / Rate Limit）
                      api.isobath.jocarium.productions
                      │
                      ▼
                    Render Free
                      FastAPI（uvicorn、1 worker）
                      │ Supavisor pooler（transaction mode、IPv4）
                      ▼
                    Supabase PostgreSQL
                      schema app      … RLS、PostgREST に非公開
                      schema analysis … パイプライン専用のビュー

    日次バッチ（GitHub Actions、毎日 01:00 JST に起動）
      isobath.nightly ── isobath_batch ロール ──► Supabase
         締め区間の確定 → 現在地の射影 → 海図の生成 → app.batch_runs / position_snapshots

    Offline（ローカル / CI、モデル改訂のときだけ）
      pipeline ── isobath_pipeline ロール ──► analysis.*（読み取り専用）
         └──► app/models/chart-{version}/ → レビュー → マージ → 次の日次バッチで有効

Render から Supabase へは、Supavisor pooler 経由で接続する。Supabase の直接接続はIPv6のみのため。transaction mode では prepared statement が使えないので、psycopg の `prepare_threshold=None` で無効にする。`SET LOCAL` はトランザクション内で完結するので、transaction mode でも正しく動く。

---

# 4. データベース設計

## 4.1 スキーマとロール

| スキーマ | 用途 | PostgREST への公開 |
|---|---|---|
| `app` | アプリのテーブル | しない（D-1） |
| `analysis` | パイプライン用の仮名化ビュー | しない |

| ロール | 権限 | 用途 |
|---|---|---|
| `isobath_api` | LOGIN、NOINHERIT、`authenticated` のメンバー、`app.batch_runs` の SELECT | FastAPI |
| `authenticated` | `app` のテーブルに対する必要最小限の GRANT。RLS に従う | FastAPI が SET ROLE で使う |
| `isobath_pipeline` | LOGIN、`analysis` スキーマの SELECT だけ | オフラインのパイプライン |
| `isobath_batch` | LOGIN、NOINHERIT。回答・セッション・同意履歴の SELECT、`position_snapshots` と `batch_runs` の書き込み。それぞれ `isobath_batch` 専用の RLS ポリシーで許可する | 日次バッチ |
| `postgres` / service_role | マイグレーション、項目の投入 | 運営者のみ |

`isobath_api` は BYPASSRLS を持たない。`SET ROLE authenticated` をせずにアプリのテーブルへアクセスした場合も、GRANT がないので失敗する（フェイルクローズ）。

## 4.2 テーブル

    -- 利用者
    create table app.profiles (
      user_id      uuid primary key references auth.users on delete cascade,
      pseudo_id    uuid not null unique default gen_random_uuid(),
      observer_no  bigint generated always as identity unique,
      created_at   timestamptz not null default now()
    );

    -- 追記のみの同意履歴。研究参加は任意で撤回可能。削除時は user_id を null にして証跡を残す
    create table app.consent_events (
      id         bigint generated always as identity primary key,
      user_id    uuid references app.profiles on delete set null,
      pseudo_id  uuid not null,                    -- トリガで本人の profiles から設定
      document   text not null check (document in ('terms','privacy','research')),
      version    text not null,
      action     text not null check (action in ('grant','withdraw')),
      at         timestamptz not null default now()
    );

    -- 項目
    create table app.questions (
      id                int primary key,
      code              text not null unique,          -- 例: D01-07
      item_set_version  text not null,
      kind              text not null check (kind in ('personality','quality','comparison')),
      domain            text,                          -- D01〜D16。分析には使わない
      facet             text,
      keyed             smallint check (keyed in (1,-1)),
      anchor            boolean not null default false,
      block_no          smallint,                      -- アンカーと品質確認項目では null
      linking           boolean not null default false,
      status            text not null check (status in ('candidate','formal','retired')),
      text_ja           text not null
    );

    -- 測深
    create table app.survey_sessions (
      id                uuid primary key default gen_random_uuid(),
      user_id           uuid not null references app.profiles on delete cascade,
      kind              text not null check (kind in ('initial','continuous')),
      status            text not null default 'open'
                          check (status in ('open','completed','abandoned')),
      item_set_version  text not null,
      phase             smallint not null default 1,
      assignment_rule   text not null,                 -- 例: bibd-uniform@1
      blocks            smallint[] not null default '{}',
      created_at        timestamptz not null default now(),
      completed_at      timestamptz,
      unique (id, user_id)
    );
    create unique index one_open_session on app.survey_sessions (user_id)
      where status = 'open';                           -- DR-06

    create table app.survey_session_questions (
      session_id      uuid not null,
      user_id         uuid not null,
      question_id     int  not null references app.questions,
      seq             smallint not null,               -- 出題順
      purpose         text not null
                        check (purpose in ('anchor','block','quality','retest','comparison')),
      selection_prob  real not null,
      primary key (session_id, question_id),
      foreign key (session_id, user_id)
        references app.survey_sessions (id, user_id) on delete cascade
    );

    create table app.answers (
      session_id    uuid not null,
      user_id       uuid not null,
      question_id   int  not null,
      value         smallint not null check (value between 1 and 5),     -- DR-01
      response_ms   int check (response_ms >= 0),
      answered_at   timestamptz not null default now(),
      primary key (session_id, question_id),                             -- DR-02
      foreign key (session_id, question_id)
        references app.survey_session_questions on delete cascade,       -- DR-04 / D-3
      foreign key (session_id, user_id)
        references app.survey_sessions (id, user_id) on delete cascade
    );

    create table app.quality_flags (
      session_id   uuid primary key,
      user_id      uuid not null,
      flags        jsonb not null,                     -- {"speeding":true, ...}
      data_quality_score  real not null,
      computed_at  timestamptz not null default now(),
      foreign key (session_id, user_id)
        references app.survey_sessions (id, user_id) on delete cascade
    );

    create table app.position_snapshots (
      id             bigint generated always as identity primary key,
      user_id        uuid not null references app.profiles on delete cascade,
      session_id     uuid not null,
      chart_version  text not null,
      stage          text not null,
      latent         real[] not null,                  -- 因子空間の座標
      latent_se      real[] not null,
      map_xy         real[] not null,                  -- 海図上の2次元座標
      confidence     real not null,
      memberships    jsonb,                            -- 海域を表示する条件を満たすとき: [{"lineage_id":..,"p":..}]
      created_at     timestamptz not null default now()
    );

    -- 削除と監査
    -- 日次バッチ（D-11, D-12）
    create table app.batch_runs (
      cutoff_at      timestamptz primary key,          -- 締め時刻（毎日 01:00 JST）
      status         text not null check (status in ('running','succeeded','failed')),
      chart_version  text not null,
      stage          text not null,
      participants   int,                              -- 締め時刻までに初回測深を完了した人数
      placed         int,                              -- この回に現在地を推定した人数
      map            jsonb,                            -- 密度グリッド（k 未満のセルは除く）
      started_at     timestamptz not null default now(),
      finished_at    timestamptz,
      error          text
    );
    -- position_snapshots には cutoff_at を持たせ、unique (user_id, cutoff_at) とする

    create table app.deletion_tombstones (
      pseudo_id   uuid primary key,
      deleted_at  timestamptz not null default now()
    );

    create table app.audit_events (
      id          bigint generated always as identity primary key,
      at          timestamptz not null default now(),
      actor_hash  text,
      action      text not null,
      detail      jsonb
    );

`user_id` は、`survey_session_questions`、`answers`、`quality_flags` に冗長に持たせる。RLS の条件を結合なしで書けるようにするためである。複合外部キーによって、セッションの所有者との一貫性を保証する。

## 4.3 RLS

全テーブルで RLS を有効にする。ポリシーは `authenticated` に対して、操作ごとに定義する（DR-05）。

| テーブル | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| profiles | 本人 | —（トリガで作成） | — | — |
| consent_events | 本人 | 本人 | — | — |
| questions | 全件 | — | — | — |
| survey_sessions | 本人 | 本人 | 本人（status、completed_at のみ） | — |
| survey_session_questions | 本人 | 本人 | — | — |
| answers | 本人 | 本人 | — | — |
| quality_flags | — | 本人 | 本人 | — |
| position_snapshots | 本人 | 本人 | — | — |
| deletion_tombstones、audit_events | — | —（関数経由） | — | — |

「本人」の条件は `user_id = (select auth.uid())` とする。

日次バッチ用のロール `isobath_batch` には、`survey_sessions`・`answers`・`consent_events`・`position_snapshots`・`batch_runs` に対して、そのロール専用のポリシー（`to isobath_batch using (true)`）を個別に定義する。BYPASSRLS は付与しない。

D-1 によって、アプリのテーブルに書き込めるのは FastAPI だけになる。したがって、`quality_flags` や `position_snapshots` に「本人」の INSERT を許可しても、利用者がそれらを偽造する経路はない。

データは、由来によって2種類に分かれる。

| 区分 | テーブル | 書き込み |
|---|---|---|
| 利用者の入力 | answers、consent_events、survey_sessions、survey_session_questions | `authenticated` の本人 INSERT が自然 |
| サーバの派生データ | quality_flags、position_snapshots | 本来はサーバだけが生成する |

MVPでは、派生データも `authenticated` の本人 INSERT で書き込む。上記のとおり D-1 によって実害はない。

LATER：派生データの書き込みを、サーバ専用の関数または別ロールに移す。`authenticated` には本人の SELECT だけを残し、INSERT を外す。

## 4.4 関数とトリガ

| 名前 | 種別 | 内容 |
|---|---|---|
| `app.on_auth_user_created()` | `auth.users` の AFTER INSERT トリガ | `app.profiles` を作成する |
| `app.delete_me()` | SECURITY DEFINER | `deletion_tombstones(pseudo_id)` と `audit_events` に記録してから、`auth.users` の `auth.uid()` の行を削除する。カスケードでアプリのデータも消える（SEC-DEL-01、D-6） |
| `app.latest_answers` | ビュー（security_invoker） | 利用者×項目ごとの最新の回答（ST-POS-04） |

### SECURITY DEFINER の hardening

SECURITY DEFINER 関数は、関数の所有者の権限で実行される。つまり**権限昇格の境界**である。3つの関数すべてに、次を適用する。

| 規則 | 実装 |
|---|---|
| search_path を空に固定する | `security definer set search_path = ''` |
| 関数の中では完全修飾名だけを使う | `app.profiles`、`auth.users`、`auth.uid()`、`extensions.digest()` など |
| 既定の EXECUTE 権限を取り消す | `revoke all on function ... from public, anon[, authenticated]` |
| 必要なロールにだけ付与する | `delete_me` → `authenticated`、`on_auth_user_created` → 付与しない（トリガ専用） |
| 呼び出し元を自分で確かめる | `delete_me` は `auth.uid()` が null なら例外を出す。引数でユーザーを受け取らない |
| 返す値を最小にする | `delete_me` は値を返さない |

## 4.5 分析用ビュー

    create view analysis.responses as
    select p.pseudo_id, s.id as session_id, s.kind, s.phase, s.item_set_version,
           s.assignment_rule, q.purpose, q.selection_prob,
           a.question_id, a.value, a.response_ms, a.answered_at,
           f.data_quality_score, f.flags
    from app.answers a
    join app.survey_sessions s on s.id = a.session_id
    join app.survey_session_questions q using (session_id, question_id)
    join app.profiles p on p.user_id = a.user_id
    left join app.quality_flags f on f.session_id = a.session_id;

このビューは `user_id`、メールアドレス、認証情報を含まない（SEC-PRV-01）。研究参加の同意が有効な利用者（`analysis.research_participants`：研究の最新の履歴が grant）のデータだけを返す。`analysis.tombstones` は `pseudo_id` だけを返す。

パイプラインがローカルに抽出したデータは、実行後に削除する。抽出データを残す場合は、次に実行する前に、tombstone で除外する（ST-CHT-04）。

---

# 5. バックエンド設計（app/）

## 5.1 パッケージ構成

    app/
    ├── pyproject.toml
    ├── isobath/
    │   ├── main.py            FastAPIの生成、ミドルウェア、ルータの登録
    │   ├── config.py          環境変数（pydantic-settings）
    │   ├── auth.py            JWTの検証（JWKS）
    │   ├── db.py              コネクションプール、ユーザースコープのトランザクション
    │   ├── ratelimit.py       アプリ内のRate Limit
    │   ├── schemas.py         リクエストとレスポンスの Pydantic モデル
    │   ├── routers/
    │   │   ├── meta.py        /healthz、/v1/meta
    │   │   ├── surveys.py     /v1/me/surveys/*
    │   │   ├── position.py    /v1/me/position、/v1/me/history
    │   │   └── account.py     /v1/me/consents、/v1/me/research、DELETE /v1/me
    │   ├── survey/
    │   │   ├── assign.py      出題の割り当て（D-8）
    │   │   └── quality.py     オンラインの品質フラグ
    │   ├── inference/
    │   │   ├── artifact.py    成果物の読み書き（パイプラインと共用）
    │   │   └── project.py     事後推定、所属確率
    │   └── drift.py           LATER（ST-DRF-03 までは使わない）
    ├── pipeline/
    │   ├── run.py             エントリポイント（§5.12 の段どおりに呼ぶ）
    │   ├── extract.py         analysis.* から取得、品質フィルタ
    │   ├── model.py           モデルと事前分布（statistics.md §2・§3）
    │   ├── sampler.py        周辺化Gibbs + split-merge（statistics.md §4.2）
    │   ├── fit.py             チェインの実行と収束診断（arviz）
    │   ├── summarize.py       標準化・整列、代表分割、所属確率、P(K)
    │   ├── lineage.py         海域IDの継承（Hungarian法）
    │   ├── chart.py           密度 → map.json
    │   └── report.py          回答分布、共回答数、事前予測検査のレポート
    ├── models/
    │   ├── CURRENT            現在の版名（1行）
    │   └── chart-{version}/
    ├── items/
    │   └── items-{item_set_version}.csv
    └── tests/

## 5.2 依存関係

| グループ | パッケージ | インストール先 |
|---|---|---|
| 実行時 | fastapi、uvicorn、pydantic-settings、psycopg[binary,pool]、pyjwt[crypto]、numpy | Render |
| `inference` / `pipeline` | scipy、arviz（`pipeline` は `inference` を含む） | 日次バッチ / 研究処理。HTTPリクエストではインポートしない |
| `dev` | pytest、httpx、ruff | ローカル / CI |

Render では `uv sync --frozen --no-dev` を実行し、`pipeline` グループはインストールしない（NFR-DEV-01）。

## 5.3 設定

| 環境変数 | 内容 |
|---|---|
| `DATABASE_URL` | `isobath_api` ロールでの pooler 接続文字列 |
| `SUPABASE_URL` | JWKS と issuer の取得元 |
| `JWT_AUDIENCE` | `authenticated` |
| `ALLOWED_ORIGINS` | カンマ区切り（SEC-NET-03） |
| `SIGNUP_ENABLED` | Emergency L2。false のとき初回セッションを作成しない |
| `SURVEY_WRITE_ENABLED` | Emergency L3。false のとき回答と完了を 503 にする |
| `READ_ONLY_MODE` | Emergency L3。書き込み系のAPIをすべて 503 にする |
| `EMERGENCY_LEVEL` | `/v1/meta` で表示に使う |

新規登録そのものは Supabase Auth 側で止める（Dashboard で signup を無効にする）。`SIGNUP_ENABLED` は、すでにアカウントを作った人が初回測深を始めることも止める。

## 5.4 リクエスト処理

    request
      → CORSMiddleware（許可リストのOriginのみ）
      → ボディサイズの上限（64 KB）
      → auth.verify(JWT)           /v1/me/* のみ
      → ratelimit(user_id, endpoint)
      → router
          → db.user_tx(claims)     BEGIN; SET LOCAL ROLE authenticated;
                                   set_config('request.jwt.claims', ..., true)
          → 業務処理
          → COMMIT
      → Cache-Control: private, no-store   /v1/me/*

### JWTの検証（SEC-AUTH-02）

- Supabase の JWKS（`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`）を起動時に取得してキャッシュする。未知の `kid` が来たときに再取得する。
- 許可するアルゴリズムは、非対称鍵（ES256 / RS256）だけとする。`none` と HS* を拒否する。
- `exp`、`iss`（`{SUPABASE_URL}/auth/v1`）、`aud`、`sub` を検証する。
- ユーザーIDは `sub` からだけ取得する（FR-API-02）。

### Rate Limit（NFR-RL-01）

- Cloudflare では、IP単位の粗い制限と WAF を担当する。
- アプリ内では、`(user_id, endpoint)` ごとのトークンバケットをメモリに持つ。

      # ponytail: メモリ内・単一worker前提。複数インスタンス化したら Redis 等へ移す

### リソース上限（NFR-LIM）

| 対象 | 上限 |
|---|---|
| リクエストボディ | 64 KB |
| `answers` 配列 | 1〜20件 |
| `history` の limit | 最大50 |
| DB の statement_timeout | 5秒（`SET LOCAL`） |
| uvicorn の timeout-keep-alive | 5秒 |

## 5.5 出題の割り当て（ST-PMD）

### 初回測深

    anchors   = アンカー項目30問（全員共通）
    blocks    = random.sample(range(10), 3)        # 120通りから一様に選ぶ（D-8）
    block_qs  = 選んだ3ブロックの項目（約60問）
    quality   = 品質確認項目5〜10問
    order     = shuffle(anchors + block_qs + quality)   # FR-SUR-10
    selection_prob:
        anchor / quality = 1.0
        block            = 3/10

記録する値は、`assignment_rule = 'bibd-uniform@1'`、`phase = 1`、`blocks = [...]` とする（ST-PMD-05）。

### 継続測深（FR-CON-02）

    n = 15
    retest   = 再出題の候補から k 問            # 前回の回答から14日以上経過したもの（FR-CON-03）
    fresh    = 未回答ブロックを1つ選び、その中から n - k 問
    order    = shuffle(retest + fresh)

`k` は requirements の Q-09 で決める。初期値は 3 とする。すべてのブロックに回答し終えた利用者には、再出題だけを出す。

割り当てと `survey_session_questions` の INSERT は、セッション作成と同じトランザクションで行う。

## 5.6 回答の受け付け（SEC-AUTH-04）

    POST /v1/me/surveys/{id}/answers
    BEGIN (user_tx)
      INSERT INTO app.answers (session_id, user_id, question_id, value, response_ms)
      SELECT ... FROM unnest(...)
      -- 割り当てていない項目は複合FKで失敗する        → 422
      -- 二重回答は主キー違反で失敗する                → 409
      -- 他人のセッションは RLS と複合FKで失敗する    → 404
      -- 完了済みのセッションは、事前に status を確認  → 409
    COMMIT
    → 204

一つのバッチの中で1件でも失敗したら、バッチ全体をロールバックする。クライアントは、エラーの種類に応じて表示を変える。

## 5.7 完了処理

    POST /v1/me/surveys/{id}/complete
    BEGIN (user_tx)
      割り当てた項目に全問回答したか確認する       → 未回答があれば 409
      status = 'completed'、completed_at = now()   # 締め区間はこの時刻で決まる（FR-BAT-03）
      quality.compute(session)  → quality_flags
    COMMIT
    → 200 { next_update_at }                      # 現在地は計算しない（FR-BAT-01）。§5.13 の日次バッチが計算する

オンラインの品質フラグ（ST-QLT-01）：

| フラグ | 判定 |
|---|---|
| `speeding` | 回答時間（`response_ms`）の中央値が 1,000ms 未満（しきい値は Pilot のデータで調整する） |
| `straightline` | アンカー項目で、同じ値が90%以上 |
| `attention_fail` | 注意確認項目で、指示と違う値を回答した |
| `inconsistent` | 同じ意味の再質問で、回答の差が3以上 |

`data_quality_score` は、フラグの数に重みを付けて 1.0 から減算した値とする。品質フラグは位置の推定には影響させず、パイプラインの品質フィルタだけで使う（ST-QLT-03）。

- 名前は `reliability` にしない。心理測定の「信頼性」（再検査信頼性、α、ω）と区別するため。
- **`response_ms` はクライアントが申告する値であり、信頼境界の外にある。** 利用者は自由に改ざんできる。ただし、これはセキュリティの判定ではなく統計品質の補助指標なので、それでよい。`response_ms` だけを理由に回答を除外せず、他の品質指標と組み合わせるときだけ使う。

## 5.8 位置の推定（ST-POS、D-4）

モデルの定義は [statistics.md](statistics.md) §2 を正とする。成果物（閾値 `tau`、負荷 `Lambda`、混合 `m`・`Sigma`・`w`、射影 `P`・`c`）を固定したうえで、観測者ごとに潜在位置 `f` の事後分布を求める。

    y*_j | f  ~ N(λ_j' f, 1),   y_j = c ⟺ τ_{j,c-1} < y*_j ≤ τ_{j,c}
    f        ~ Σ_k w_k N(m_k, Σ_k)

閉じた式にはならないため、観測者ごとに小さなGibbs（`y*` の切断正規 → 所属 `z` → `f` の条件付き正規）を回す。**所属も更新する**：混合事前のもとで `f` の条件付き分布は単一の正規分布ではない。さらに、成果物に保存した事後ドロー `θ^(s)`（S=200）について繰り返し、平均を取る。これによりモデル推定自体の不確実性を落とさない（statistics.md §7.1）。固定シードで再現する。

- `latent` は `f` の事後平均、`latent_se` は事後標準偏差。
- 未回答の項目は尤度に現れない。補完は要らない（ST-POS-02）。
- `confidence=1/(1+tr(Cov(f))/16)`。全員にグリッド信用領域を用い、楕円は経験的距離分位点で校正した補助表示とする。
- 海図上の座標は `map_xy = P · f + c`。D01・D04への固定射影を使う。版を跨ぐ比較は測定モデル・中心・尺度も固定した参照成果物で再計算する（statistics.md §5.1）。
- 所属確率は各ドローの成分ID対応表で代表海域へ対応づけ、`alignment_unmatched` と `unseen` を別々に集計する。新規利用者の推論はcut型であり、通常の完全ベイズ事後とは区別する。
- `near_boundary` は、所属確率の1位と2位の差が0.2未満のときに真とする。

観測者ごとに独立に計算する。日次処理はNumPy・SciPy・ArviZを使用し、内側Gibbsと保存された外側ドローの精度を別に確認する。所要時間は実測する。

## 5.9 モデルの成果物（D-5）

    app/models/
      CURRENT                    例: 2027.01
      chart-2027.01/
        model.npz                間引いた事後ドロー（S=200）を保存する（statistics.md §7）
                                 draws_tau[S,p,4], draws_Lambda[S,p,16],
                                 draws_w[S,C], draws_m[S,C,16], draws_Sigma[S,C,16,16],
                                 draws_valid[S,C], draws_occupied[S,C], draws_K[S], draws_T[S],
                                 draws_component_to_region[S,C], draws_core_z[S,core],
                                 center_b[S,16], scale_a[S,16],
                                 P[2,16], c[2], T_post[...], K_post[...]
        metadata.json

    metadata.json
    {
      "version": "2027.01",
      "stage": "CHARTED",                // COLLECTING / CHARTED の2値（requirements §4）
      "item_set_version": "0.2",
      "question_ids": [...],             // model.npz の行の順序
      "regions": [{"index":0,"lineage_id":"REGION-A"}],
      "diagnostics": {"rhat_max": 1.004, "ess_bulk_min": 780, "ess_tail_min": 610,
                      "credible_ball_radius": 0.21,
                      "p_t": [0.02, 0.61, 0.29], "p_t_ge2": 0.98, "p_t_ge2_mcse": 0.004},
      "S": 200,
      "core_user_index": [...],
      "n_observers": 612,
      "pipeline_commit": "abc1234",
      "seed": 20270101,
      "created_at": "..."
    }

- 起動時に `CURRENT` が指す版を1回だけ読み込み、プロセス内に保持する（NFR-PRF-04）。
- `artifact.py` は読み込みと書き出しの両方を実装し、パイプラインと共用する。形式のずれを防ぐため。
- 成果物がまだないときは、`model.npz` を置かずに metadata（`stage: COLLECTING`）だけを置く。日次バッチは位置を計算せず、APIは `observer_no` を返す（FR-POS-06）。
- 配列の定義は [statistics.md](statistics.md) §7 を正とする。`mu`・`scale`・`psi` は順序モデルでは不要で、`tau` が代わる。
- **成分ごとの値をドローをまたいで平均しない**（ラベル入れ替わり）。必ずドロー単位で使う。

## 5.10 API（requirements §8.2 の実装）

| メソッド | パス | 処理 | 主なエラー |
|---|---|---|---|
| GET | `/healthz` | 定数を返す。DBにアクセスしない | — |
| GET | `/v1/meta` | 直近に成功した `batch_runs` の版・段階・参加人数、`updated_at`・`next_update_at`・`stale`、Emergency の状態。バッチ未実行のときは成果物の metadata。`Cache-Control: public, max-age=60` | — |
| GET | `/v1/chart/current` | 直近に成功した `batch_runs.map`。`Cache-Control: public, max-age=<次の締め時刻までの秒数>` | 404（未生成） |
| GET / POST | `/v1/me/consents` | 同意状態の取得・同意の記録（SEC-CON-01）。状態は `app.consent_state`（最新の履歴）から求める | 422 |
| PUT | `/v1/me/research` | `{participating}` で研究参加の撤回・再開（FR-ACC-06） | — |
| POST | `/v1/me/surveys` | `{kind}` を受け取り、セッションを作成する。同意していなければ 403。開いているセッションがあればそれを返す。継続測深は、現在の締め区間にすでに完了していれば 429（FR-CON-05） | 403、409、429、503 |
| GET | `/v1/me/surveys/current` | 開いているセッションと、未回答の項目を先頭から最大20問 | 404 |
| POST | `/v1/me/surveys/{id}/answers` | §5.6 | 404、409、422、503 |
| POST | `/v1/me/surveys/{id}/complete` | §5.7 | 409、503 |
| GET | `/v1/me/position` | 最新のスナップショットに段階に応じた表示の制御をかけ、`updated_at`・`next_update_at`を加えて返す | 404 |
| GET | `/v1/me/history` | `id` をカーソルとして降順に返す。limit は50以下 | — |
| DELETE | `/v1/me` | `app.delete_me()` を呼ぶ | — |

成果物の状態による出し分け（`/v1/me/position`）：

| 状態 | 返す値 |
|---|---|
| 成果物なし（`stage = COLLECTING`） | `observer_no`、`participants`、`stage` |
| 成果物あり（`CHARTED`） | 上記に加えて、`position`（map_xy）、`se`、`confidence` |
| 上に加えて、海域を表示する条件（FR-UNC-03）を満たす | `regions`（lineage_id と membership）、`near_boundary` |

エラーのレスポンスは、`{"error": {"code": "...", "message": "..."}}` の形に統一する。500 のときは内部の詳細を返さない。

## 5.11 ログ（SEC-LOG）

- 1リクエストにつき1行の JSON を出す：`request_id`、`user_hash`（sha256(sub + salt) の先頭16文字）、`endpoint`、`status`、`latency_ms`。
- Authorization ヘッダ、リクエストボディ、例外メッセージに含まれる値は出力しない。uvicorn の access log は無効にし、自前のミドルウェアに一本化する。

## 5.12 オフラインパイプライン（ST-CHT）

推定するモデルと事前分布は [statistics.md](statistics.md) を正とする。ここでは実装の構成だけを定める。

    python -m pipeline.run fit --version 2027.01 --cutoff ... --sign-anchors ...

    extract    analysis.responses から取得する。tombstone と品質フィルタ（data_quality_score < しきい値）で除外する。
               比較尺度（kind = 'comparison'）と品質確認（'quality'）はここで落とす（ST-CHT-03）
      ↓
    report     項目ごとの回答分布、閾値の偏り、項目ペアの共回答数の行列（ST-PMD-06）
      ↓
    prior      事前予測検査。生成される回答分布が5件法として現実的か（statistics.md §9.2）
      ↓
    fit        周辺化Gibbs + split-merge。4チェイン、初期分割を変える（statistics.md §4）
      ↓
    diagnose   R-hat、bulk/tail ESS、判定確率の MCSE、チェイン間の代表分割の一致。
               満たさなければ**成果物を作らず失敗する**（FR-UNC-07）
      ↓
    standardize 各ドローで中心化と標準化を行い、b と a を保存する（statistics.md §5）
      ↓
    align      前の版があれば、共通の観測者で Procrustes 整列（ST-CHT-06）。射影 P は固定の参照基底
               であり、毎回取り直さない（statistics.md §5.1）
      ↓
    summarize  代表分割（VI損失の事後期待値を最小化）、credible ball 半径、P(T_N=t)、P(K=k)、
               所属確率（ドローごとに代表海域へ対応づけ。statistics.md §6）
      ↓
    lineage    前の版のクラスタと Hungarian法で対応づけ、region_lineage_id を継承（ST-CHT-07）
      ↓
    chart      map_xy の密度。人口が k 未満のセルは出力しない（FR-CHT-04）
      ↓
    write      app/models/chart-{v}/（`CURRENT` は切り替えない。§7.1）

- 推論は自前の周辺化Gibbsで行う（§5.12.1）。JAX / NumPyro は使わない。
- 乱数シード、コミットハッシュ、件数、診断値を metadata に記録する（ST-CHT-05）。
- 出力は PR にして、運営者がレポートと診断値をレビューしてから merge する（FR-OPS-02、FR-UNC-06）。

### 5.12.1 推論の実装方式（NumPyro / HMC を使わない判断）

| 論点 | 判断 |
|---|---|
| HMC（NumPyro）で分割を動かせるか | できない。HMCは離散潜在変数を直接サンプリングしない |
| 列挙で周辺化すればよいか | 元の事前を保持した周辺化は可能。可変次元・計算量・打ち切り誤差を考慮して、今回はGibbsを選ぶ。周辺化自体は事前の変更ではない |
| 採る方式 | **データ拡張付きの周辺化Gibbs + Jain-Neal split-merge を自前で書く。** `y*` を拡張すれば全条件付き分布が共役になる。NumPy + SciPy で実装する |
| 診断 | arviz（R-hat、bulk/tail ESS、MCSE）。加えて初期分割を変えた4チェインの比較（statistics.md §4.3） |
| 高速化 | まず実測する。足りなければ JAX 化、または連続部分だけHMC（`HMCGibbs`）を検討する（LATER） |

**依存関係**：NumPy（本体）、SciPy・ArviZ（`inference` / `pipeline`）。JAX と NumPyro は入れない。

## 5.13 日次バッチ（requirements §4.1、D-11、D-12）

    python -m isobath.nightly            # GitHub Actions から起動する（.github/workflows/nightly.yml）

    cutoff = 現在時刻以前で直近の 01:00 JST
    batch_runs に cutoff の succeeded があれば終了       # 再起動・取りこぼし対策の2回目以降（FR-BAT-11）
    model = artifact.load(CURRENT)                     # この時点でマージ済みのモデルが有効になる（D-9）

    対象者 =
      直前に成功した締め時刻 ≤ completed_at < cutoff のセッションを持つ利用者     # 新しい回答がある
      ∪ 最新スナップショットの chart_version ≠ model.version の利用者             # モデルが変わった
    for 対象者:
      y = completed_at < cutoff のセッションの回答のうち、項目ごとに最新のもの
      place(model, y) → position_snapshots を (user_id, cutoff_at) で upsert

    海図 = 研究参加者（研究の同意が有効）の最新スナップショットの map_xy の 2次元ヒストグラム
           人数が k 未満のセルは 0 にする（FR-CHT-04）
    participants = completed_at < cutoff の初回測深の完了者数
    batch_runs に succeeded として保存（map、participants、placed、finished_at）
    失敗時：failed と error を記録して終了コード 1（GitHub の失敗通知が飛ぶ）

- 日次処理には `uv sync --frozen --no-dev --group inference` を使う。学習者の同時事後を渡す非公開保管先を `PRIVATE_STATISTICS_DIR` に設定する。
- 締め時刻の計算は `zoneinfo("Asia/Tokyo")` で行う。日本時間に夏時間はない。
- 成果物に配列がないとき（`stage: COLLECTING`）は、現在地と海図を作らず、実行記録だけを残す。
- 結果の書き込みは1つのトランザクションで行う。途中で失敗しても、中途半端な結果は残らない。

### GitHub Actions（`.github/workflows/nightly.yml`）

| 項目 | 値 |
|---|---|
| トリガ | `schedule: '7 16 * * *'`（01:07 JST）と `'37 16 * * *'`（01:37 JST、取りこぼし対策）、手動実行の `workflow_dispatch`。GitHub は毎時0分に起動が集中して遅れやすいため、締め時刻（01:00）より少し後に起動する |
| 同時実行 | `concurrency: nightly`（重ならない） |
| 接続 | Secret `NIGHTLY_DATABASE_URL` を環境変数 `DATABASE_URL` として渡す（`isobath_batch` ロール、Supavisor pooler 経由。GitHub のランナーは IPv6 を使えない）。ローカルでは `app/.env` の `NIGHTLY_DATABASE_URL` を使う（`pnpm batch`） |
| 失敗の検知 | ワークフローの失敗通知（schedule の場合、cron を最後に変更したユーザーに届く）。加えて `/v1/meta` の `updated_at` が26時間以上前なら `stale: true` を返す |

GitHub の schedule は、混雑時に起動が遅れたり、まれに起動されないことがある。締め区間は `completed_at` だけで決まるため、遅れても結果は変わらない。また、リポジトリに60日間活動がないと schedule が無効になるため、運用中は定期的に確認する（deploy.md）。

---

# 6. フロントエンド設計（src/）

## 6.1 レンダリング方針

adapter-static を使う。

| ルート | 方式 | 理由 |
|---|---|---|
| `/`、`/chart`、`/status` | プリレンダリング（SSG） | 認証が不要。API が止まっていても表示できる（NFR-AVL-04） |
| `/auth/*`、`/survey/*`、`/journey`、`/profile`、`/settings` | `ssr = false` のSPAシェル | 認証が必要で、データはすべて API から取得する |

    src/routes/+layout.ts            export const prerender = true;
    src/routes/(app)/+layout.ts      export const ssr = false;   // シェルだけプリレンダリングする

paraglide は URL 戦略（`/en/...`）で使う。hooks.server.ts はプリレンダリングのときだけ実行される。雛形にある非表示のロケールリンクは、クローラが `/en` 側のページも辿れるようにするためのものなので、残しておく。

## 6.2 ディレクトリ構成

    src/
    ├── app.html
    ├── hooks.ts / hooks.server.ts         paraglide（既存）
    ├── lib/
    │   ├── config.ts                      PUBLIC_* の環境変数
    │   ├── api/
    │   │   ├── client.ts                  fetch のラッパ（JWTの付与、タイムアウト、エラーの正規化）
    │   │   └── types.ts                   API の型
    │   ├── auth/
    │   │   └── supabase.ts                supabase-js（Auth のみ）
    │   ├── survey/
    │   │   ├── draft.ts                   未送信の回答の一時保存
    │   │   └── sync.ts                    5〜10問ごとのバッチ送信
    │   ├── chart/
    │   │   ├── load.ts                    /charts/{v}/map.json の取得
    │   │   └── ChartView.svelte           等値線のSVGと現在地の重ね描き
    │   └── components/
    │       ├── LikertItem.svelte
    │       ├── StageBanner.svelte         暫定海図・未測量の表示
    │       └── ShipStatus.svelte          Cold Start と混雑の表示
    └── routes/
        ├── +layout.svelte / +layout.ts
        ├── +page.svelte                   ランディング
        ├── chart/+page.svelte
        ├── status/+page.svelte
        ├── auth/
        │   ├── login/+page.svelte
        │   ├── signup/+page.svelte        CAPTCHA（Turnstile）、同意
        │   └── callback/+page.svelte      メール確認からの戻り先
        └── (app)/
            ├── +layout.ts / +layout.svelte    認証ガード
            ├── survey/initial/+page.svelte
            ├── survey/+page.svelte
            ├── journey/+page.svelte
            ├── profile/+page.svelte
            └── settings/+page.svelte

雛形の `src/routes/demo/` と `src/lib/vitest-examples/` は削除する。

## 6.3 環境変数

| 変数 | 内容 |
|---|---|
| `PUBLIC_SUPABASE_URL` | Supabase のプロジェクトURL |
| `PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Publishable Key（SEC-AUTH-06） |
| `PUBLIC_API_BASE` | `https://api.isobath.jocarium.productions`。開発時は `http://localhost:8000` |
| `PUBLIC_TURNSTILE_SITE_KEY` | CAPTCHA 用 |

## 6.4 認証

- supabase-js は Auth（signUp、signInWithPassword、signOut、onAuthStateChange、getSession）だけに使う。DB へのクエリは書かない（D-1）。
- セッションは supabase-js の既定どおり localStorage に保存する。XSS で盗まれる危険は、CSP で抑える（§6.8）。
- `(app)/+layout.svelte` でセッションがなければ、`/auth/login?next=...` へリダイレクトする。
- 登録画面では、必須（利用規約・プライバシーポリシー・18歳以上・非診断の理解）と任意（研究参加）を分けて表示する。チェックした文書と版を user_metadata に載せ、最初のログイン時に `POST /v1/me/consents` で記録する。必須の同意が揃うまで測深の作成は 403 になる。

## 6.5 APIクライアント

    api(path, { method, body })
      - Authorization: Bearer <access_token>（getSession で最新のトークンを取る）
      - 10秒応答がなければ ShipStatus に「測量船を起動しています……」を出して待ち続け、最大90秒で打ち切る（FR-UI-03）
      - 401 → トークンを1回リフレッシュして再試行する。失敗したらログイン画面へ
      - 429 → 「測量船へのアクセスが集中しています」
      - 503 → /v1/meta の Emergency 状態を見て、書き込みを止めた旨を表示する
      - ネットワークエラー → /status へ案内する

## 6.6 測深画面

    GET /v1/me/surveys/current で最大20問を取得する
      ↓
    1問ずつ表示する（LikertItem、5件法）。表示した時刻から response_ms を測る
      ↓
    回答を draft に追加する（localStorage。読み書きはすべて try/catch で囲む。FR-SUR-07）
      ↓
    draft が5問たまったら、またはページを離れるときに POST answers
      204 → draft から削除する
      409（二重回答）→ draft から削除する（送信済みだった）
      その他 → draft に残し、次の機会に再送する
      ↓
    20問を終えたら次の20問を取得する。未回答がなくなったら complete
      ↓
    段階に応じた結果画面へ

- 途中で離脱しても、同じ URL に戻れば `surveys/current` から再開できる（FR-SUR-06）。
- 画面には進捗（n / 100）だけを出し、観測領域の名前は出さない。

## 6.7 海図の表示

- 海図は `GET /v1/chart/current`（日次バッチが生成した密度グリッド）を取得して描く。自分の現在地は `/v1/me/position` のものを重ねる。両方とも同じ日次バッチの結果なので、版が一致する。
- 等値線は密度グリッドからクライアントで描く（描画方法は海図の実装時に決める）。
- 最終更新日時と、次回の更新予定（毎日 01:00 頃）を表示する（FR-POS-07）。
- `StageBanner` は、成果物の有無と不確実性（`P(K)`、credible ball 半径）に応じた文言を出す（FR-UNC-02、FR-UNC-05、FR-POS-04、FR-POS-06）。
- 色や高さの表現に、優劣を連想させるもの（上位／下位、良い／悪い）を使わない（FR-UI-01）。

## 6.8 セキュリティヘッダ（SEC-FE）

`static/_headers`（Cloudflare Pages）：

    /*
      X-Content-Type-Options: nosniff
      Referrer-Policy: strict-origin-when-cross-origin
      Permissions-Policy: camera=(), microphone=(), geolocation=()
      Strict-Transport-Security: max-age=31536000; includeSubDomains
      X-Frame-Options: DENY

    /_app/immutable/*
      Cache-Control: public, max-age=31536000, immutable

CSP は SvelteKit の `kit.csp`（mode: `hash`）で生成する。プリレンダリングしたページにインラインスクリプトのハッシュが入る。

    default-src 'self';
    script-src 'self' https://challenges.cloudflare.com;
    connect-src 'self' https://api.isobath.jocarium.productions https://<project>.supabase.co;
    frame-src https://challenges.cloudflare.com;
    img-src 'self' data:;
    style-src 'self' 'unsafe-inline';
    object-src 'none'; base-uri 'self'; frame-ancestors 'none'

`style-src 'unsafe-inline'` は、Svelte の transition などのインラインスタイルのために許可する。

---

# 7. デプロイ

GUI での具体的な作業手順と設定値の一覧は [deploy.md](deploy.md) にまとめる。

| 対象 | 設定 |
|---|---|
| Cloudflare Pages | ビルド `pnpm build`、出力 `build/`、本番ブランチ `main` |
| Render | Root Directory `app`、ビルド `uv sync --frozen --no-dev`、起動 `uv run uvicorn isobath.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log`、ヘルスチェック `/healthz` |
| GitHub Actions | `.github/workflows/nightly.yml`。Secret `NIGHTLY_DATABASE_URL` |
| Render ドメイン | カスタムドメイン `api.isobath.jocarium.productions` を設定し、`onrender.com` を Disabled にする（SEC-NET-02） |
| Cloudflare | api レコードを Proxied にする。WAF のマネージドルールと、IP単位の Rate Limit ルールを設定する |
| Supabase | `supabase db push` でマイグレーションを適用する。Data API の公開スキーマは `public`（と `graphql_public`）だけにする（`app` と `analysis` は公開しない）。Auth はメール確認を有効にする。CAPTCHA（Turnstile）はフロントエンドのウィジェット実装後に有効にする（それまでは有効にすると登録できない。deploy.md 1-6） |
| 項目の投入 | `app/items/items-{v}.csv` を、スクリプトで `app.questions` に upsert する（FR-OPS-01） |

## 7.1 モデルのリリース手順（FR-UNC-06、FR-OPS-03、D-9）

API はモデルで現在地を計算せず、海図も Pages に置かないため、以前の「成果物を先に配置してからポインタを切り替える」2段階の手順は不要になった。

    pipeline.run → PR（app/models/chart-{v}/、CURRENT = {v}、レポートと診断値）
      → レビュー → main へ merge
      → 次の日次バッチ（01:00 JST）が CURRENT を読み、新しい版で全員を再射影して海図を作る

- どの版で計算したかは `batch_runs.chart_version` に記録される。
- 00:30〜02:00 JST（締め時刻とバッチの起動・再起動の時間帯）には、モデルの PR を merge しない。
- 切り戻すときは、`CURRENT` を前の版に戻す PR を merge する。翌日の日次バッチで前の版に戻る（その日の締め時刻はすでに成功済みのため、手動で再実行しても再計算されない）。

---

# 8. テスト方針

| 対象 | 方法 | 検証する内容 |
|---|---|---|
| 位置の推定 | pytest | 全問回答したときに、真の因子を十分な精度で復元できること。回答が減るほど事後標準偏差が増えること。所属確率の合計が1になること |
| モデルの推定 | pytest（`pipeline`） | SBC で推論実装の校正を確認すること（statistics.md §9.1）。合成データからの回復を反復して測ること（`T=1`／`T=3` 離れた・重なった／`N=1`。§9.2）。診断を満たさないときに失敗すること |
| 割り当て | pytest | 構成（30＋約60＋品質確認）、重複がないこと、selection_prob の値。大量にシミュレーションしたときに、ブロックのペアの出現頻度が均等になること |
| JWT | pytest | 期限切れ、iss / aud の不一致、alg=none、HS256 を拒否すること |
| RLS | pytest ＋ ローカルの Supabase（`supabase start`） | ユーザーAのトランザクションから、Bのセッションや回答を読めず、書けないこと。割り当てていない項目への INSERT がFKで失敗すること（受け入れ基準3、4） |
| 削除 | pytest ＋ ローカルの Supabase | `delete_me()` の後に、アプリのデータが0件になり、tombstone だけが残ること |
| 成果物 | pytest | `artifact.py` で書いたものを読み戻したとき、完全に一致すること |
| フロントエンド | vitest | draft の再送と重複除去、成果物の有無と不確実性による表示の切り替え |
| E2E | Playwright | 登録 → 初回測深 → 中断 → 再開 → 完了 |

---

# 9. requirements.md への反映事項

本書の設計に伴い、requirements.md の次の箇所を更新する。

| 箇所 | 内容 |
|---|---|
| §4、FR-UNC | 反映済み：人数のしきい値による段階を廃止し、不確実性の表示に置き換えた（statistics.md） |
| §11.3 | 反映済み：成果物の形式を statistics.md §7 に合わせた |
| Q-11 | 決定：直接接続して SET LOCAL する方式（D-2） |
| §8.2 | `POST /v1/me/consents` を追加する |
| §11.1 | `chart_versions`、`regions`、`item_blocks` はMVPではテーブル化しない（D-10） |
| §9.4 Signup | Supabase Auth 側の Rate Limit と CAPTCHA で担保する（D-7） |
