# 人格海図 ISOBATH
## 設計書 v1.0

| 項目 | 内容 |
|---|---|
| 対象 | MVP（Pilot Phase 1） |
| 作成日 | 2026-09-21 |
| 上位文書 | [requirements.md](requirements.md)（要件）、[concept.md](concept.md)（企画）、[observation-domains.md](observation-domains.md)（観測領域） |

本書は requirements.md の要件を満たす実装方法を定める。要件IDを括弧で示す。

---

# 1. 設計上の主要決定

| # | 決定 | 理由 |
|---|---|---|
| D-1 | アプリのテーブルは Supabase Data API（PostgREST）に**公開しない**。`app` スキーマに置き、FastAPI だけが直接接続してアクセスする | ブラウザは Publishable Key とユーザーのJWTを持っている。テーブルを公開すると、FastAPI の検証を迂回して PostgREST から直接書き込めてしまう |
| D-2 | FastAPI は専用ロール `isobath_api` で接続し、リクエストごとのトランザクション内で `SET LOCAL ROLE authenticated` と `request.jwt.claims` を設定する（requirements Q-11 の決定） | RLS をユーザー権限で効かせたまま、「割り当ての検証＋INSERT」を一つのトランザクションにできる（SEC-AUTH-03、SEC-AUTH-04） |
| D-3 | 割り当ての検証を複合外部キーでDBに持たせる。`answers(session_id, question_id)` → `survey_session_questions` | アプリにバグがあっても、割り当てていない項目への回答をDBが拒否する（DR-04） |
| D-4 | 現在地は、**因子モデルの事後分布**で推定する。欠けている項目は、観測した行だけを使えば自然に扱える | 部分的な回答からの推定とSEの算出を、閉じた式で同時に得られる（ST-POS-02、ST-POS-03） |
| D-5 | モデルの成果物は `npz` と `json` で保存し、pickle を使わない。実行時は numpy だけで推論する | pickle の読み込みはコード実行のリスクがある。scikit-learn を実行環境に入れずに済み、メモリも節約できる（NFR-PRF-02、NFR-PRF-06） |
| D-6 | アカウントの削除は、DBの `SECURITY DEFINER` 関数で行う | 通常のAPIに service_role を持たせずに、`auth.users` まで削除できる（SEC-AUTH-05） |
| D-7 | 登録（Signup）は Supabase Auth が直接受け付けるので、Cloudflare を通らない。Bot 対策には、Supabase Auth 組み込みの CAPTCHA 連携（Turnstile）と Rate Limit を使う | Cloudflare の Rate Limit は Signup に効かない（SEC-NET-04、§9.4 Signup） |
| D-8 | ブロックの割り当ては、10ブロックから3つを選ぶ全組み合わせ（120通り）から一様ランダムに選ぶ | 項目ペアの共回答率が期待値で完全に均等になる。回答者のデータに依存しないのでMCARになる（ST-PMD-04） |
| D-9 | 海図とモデルは、パイプラインがリポジトリに出力し、merge によって Pages と Render の両方へデプロイする | 段階の移行が成果物のデプロイだけで済む（FR-STG-02、FR-OPS-03） |
| D-10 | 海図の版・段階・海域は、成果物の metadata を正とする。DBには `chart_version` の文字列だけを持つ | requirements §11.1 の `chart_versions`、`regions`、`item_blocks` テーブルは作らない。それぞれ成果物と `questions.block_no` で代替する。lineage を実装する時点（LATER）でテーブル化する |

---

# 2. リポジトリ構成

    isobath/
    ├── src/                      フロントエンド（SvelteKit）
    ├── static/                   静的資産（Cloudflare Pages）
    │   ├── _headers              セキュリティヘッダ
    │   └── charts/               海図の成果物（パイプラインが出力）
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
      │               静的HTML/JS、/charts/{version}/*
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

    Offline（ローカル / CI）
      pipeline ── isobath_pipeline ロール ──► analysis.*（読み取り専用）
         │
         ├──► app/models/chart-{version}/   → Render
         └──► static/charts/{version}/      → Cloudflare Pages

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
| `isobath_api` | LOGIN、NOINHERIT、`authenticated` のメンバー、`app.public_stats()` の EXECUTE 権限 | FastAPI |
| `authenticated` | `app` のテーブルに対する必要最小限の GRANT。RLS に従う | FastAPI が SET ROLE で使う |
| `isobath_pipeline` | LOGIN、`analysis` スキーマの SELECT だけ | オフラインのパイプライン |
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

    create table app.consents (
      user_id    uuid not null references app.profiles on delete cascade,
      document   text not null check (document in ('terms','privacy','research')),
      version    text not null,
      agreed_at  timestamptz not null default now(),
      primary key (user_id, document, version)
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
      reliability  real not null,
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
      memberships    jsonb,                            -- SEED以降: [{"lineage_id":..,"p":..}]
      created_at     timestamptz not null default now()
    );

    -- 削除と監査
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
| consents | 本人 | 本人 | — | — |
| questions | 全件 | — | — | — |
| survey_sessions | 本人 | 本人 | 本人（status、completed_at のみ） | — |
| survey_session_questions | 本人 | 本人 | — | — |
| answers | 本人 | 本人 | — | — |
| quality_flags | — | 本人 | 本人 | — |
| position_snapshots | 本人 | 本人 | — | — |
| deletion_tombstones、audit_events | — | —（関数経由） | — | — |

「本人」の条件は `user_id = (select auth.uid())` とする。

D-1 によって、アプリのテーブルに書き込めるのは FastAPI だけになる。したがって、`quality_flags` や `position_snapshots` に「本人」の INSERT を許可しても、利用者がそれらを偽造する経路はない。

## 4.4 関数とトリガ

| 名前 | 種別 | 内容 |
|---|---|---|
| `app.on_auth_user_created()` | `auth.users` の AFTER INSERT トリガ | `app.profiles` を作成する |
| `app.delete_me()` | SECURITY DEFINER | `deletion_tombstones(pseudo_id)` と `audit_events` に記録してから、`auth.users` の `auth.uid()` の行を削除する。カスケードでアプリのデータも消える（SEC-DEL-01、D-6） |
| `app.public_stats()` | SECURITY DEFINER、STABLE | 初回測深を完了した人数などの集約値だけを返す |
| `app.latest_answers` | ビュー（security_invoker） | 利用者×項目ごとの最新の回答（ST-POS-04） |

## 4.5 分析用ビュー

    create view analysis.responses as
    select p.pseudo_id, s.id as session_id, s.kind, s.phase, s.item_set_version,
           s.assignment_rule, q.purpose, q.selection_prob,
           a.question_id, a.value, a.response_ms, a.answered_at,
           f.reliability, f.flags
    from app.answers a
    join app.survey_sessions s on s.id = a.session_id
    join app.survey_session_questions q using (session_id, question_id)
    join app.profiles p on p.user_id = a.user_id
    left join app.quality_flags f on f.session_id = a.session_id;

このビューは `user_id`、メールアドレス、認証情報を含まない（SEC-PRV-01）。`analysis.tombstones` は `pseudo_id` だけを返す。

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
    │   │   └── account.py     /v1/me/consents、DELETE /v1/me
    │   ├── survey/
    │   │   ├── assign.py      出題の割り当て（D-8）
    │   │   └── quality.py     オンラインの品質フラグ
    │   ├── inference/
    │   │   ├── artifact.py    成果物の読み書き（パイプラインと共用）
    │   │   └── project.py     事後推定、所属確率
    │   └── drift.py           LATER（ST-DRF-03 までは使わない）
    ├── pipeline/
    │   ├── run.py             エントリポイント
    │   ├── extract.py         analysis.* から取得、品質フィルタ
    │   ├── em.py              欠損を扱う共分散のEM推定
    │   ├── efa.py             EFA（EM共分散を入力）
    │   ├── cluster.py         GMM、Bootstrap
    │   ├── chart.py           密度・等値線 → map.json / contours.svg
    │   └── report.py          共回答数、品質のレポート
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
| `pipeline` | pandas、scipy、scikit-learn、factor_analyzer、matplotlib（等値線の生成） | ローカル / CI |
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
      status = 'completed'
      quality.compute(session)  → quality_flags
      if stage >= PROTO:
          y = latest_answers(user)                 # 全セッションを通した、項目ごとの最新の回答
          snap = project(model, y)                 # §5.8
          INSERT position_snapshots
    COMMIT
    → 200 { position の要約 }

オンラインの品質フラグ（ST-QLT-01）：

| フラグ | 判定 |
|---|---|
| `speeding` | 回答時間の中央値が 1,000ms 未満（しきい値は Pilot のデータで調整する） |
| `straightline` | アンカー項目で、同じ値が90%以上 |
| `attention_fail` | 注意確認項目で、指示と違う値を回答した |
| `inconsistent` | 同じ意味の再質問で、回答の差が3以上 |

`reliability` は、フラグの数に重みを付けて 1.0 から減算した値とする。品質フラグは位置の推定には影響させず、パイプラインの品質フィルタだけで使う（ST-QLT-03）。

## 5.8 位置の推定（ST-POS、D-4）

因子モデル（標準化した項目）を次のように置く。

    y = μ + Λ f + ε,   f ~ N(0, I_k),   ε ~ N(0, Ψ)（Ψ は対角）

観測した項目の集合を o とすると、事後分布は次のとおり。

    Σ_post = (I_k + Λ_o' Ψ_o⁻¹ Λ_o)⁻¹
    f̂      = Σ_post Λ_o' Ψ_o⁻¹ (y_o − μ_o)

- `latent = f̂`、`latent_se = sqrt(diag(Σ_post))`
- 観測していない項目は Λ と Ψ の行から外すだけで済み、補完は要らない（ST-POS-02）。
- `confidence = 1 − mean(diag(Σ_post))`。事前分散が1なので、0〜1の範囲に収まる。回答数が少ないほど小さくなる（FR-POS-02）。
- 海図上の座標は `map_xy = P · f̂ + c` とする。P（2×k）と c は成果物に固定で持たせる。
- 所属確率（SEED以降）は、GMMの各成分の共分散に推定の不確実性を足して計算する。

      p(c | y) ∝ π_c · N(f̂ ; m_c, S_c + Σ_post)

  この式では、推定精度が低いほど所属確率が平らになる（FR-POS-05）。
- `near_boundary` は、所属確率の1位と2位の差が0.2未満のときに真とする。

計算量は O(|o|·k²) で、k は20以下を想定する。numpy だけで1ミリ秒未満で終わる。

## 5.9 モデルの成果物（D-5）

    app/models/
      CURRENT                    例: 2027.01
      chart-2027.01/
        model.npz                mu[p], scale[p], Lambda[p,k], psi[p],
                                 P[2,k], c[2],
                                 gmm_pi[C], gmm_mean[C,k], gmm_cov[C,k,k]   ← SEED以降
        metadata.json

    metadata.json
    {
      "version": "2027.01",
      "stage": "PROTO",
      "item_set_version": "0.1",
      "question_ids": [...],             // model.npz の行の順序
      "k": 6,
      "regions": [{"index":0,"lineage_id":"REGION-A"}],   // SEED以降
      "n_observers": 612,
      "pipeline_commit": "abc1234",
      "seed": 20270101,
      "created_at": "..."
    }

- 起動時に `CURRENT` が指す版を1回だけ読み込み、プロセス内に保持する（NFR-PRF-04）。
- `artifact.py` は読み込みと書き出しの両方を実装し、パイプラインと共用する。形式のずれを防ぐため。
- UNCHARTED と PRE-CHART の段階では、`model.npz` を置かずに metadata だけを置く。API は位置を推定せず、`observer_no` を返す（FR-POS-06）。

## 5.10 API（requirements §8.2 の実装）

| メソッド | パス | 処理 | 主なエラー |
|---|---|---|---|
| GET | `/healthz` | 定数を返す。DBにアクセスしない | — |
| GET | `/v1/meta` | 成果物の metadata、`public_stats()`（60秒間メモリにキャッシュ）、Emergency の状態。`Cache-Control: public, max-age=60` | — |
| POST | `/v1/me/consents` | 同意の記録（SEC-CON-01）。requirements に追加するエンドポイント | 422 |
| POST | `/v1/me/surveys` | `{kind}` を受け取り、セッションを作成する。同意していなければ 403。開いているセッションがあればそれを返す | 403、409、503 |
| GET | `/v1/me/surveys/current` | 開いているセッションと、未回答の項目を先頭から最大20問 | 404 |
| POST | `/v1/me/surveys/{id}/answers` | §5.6 | 404、409、422、503 |
| POST | `/v1/me/surveys/{id}/complete` | §5.7 | 409、503 |
| GET | `/v1/me/position` | 最新のスナップショットに、段階に応じた表示の制御をかけて返す | 404 |
| GET | `/v1/me/history` | `id` をカーソルとして降順に返す。limit は50以下 | — |
| DELETE | `/v1/me` | `app.delete_me()` を呼ぶ | — |

段階による出し分け（`/v1/me/position`）：

| 段階 | 返す値 |
|---|---|
| UNCHARTED / PRE-CHART | `observer_no`、`participants`、`stage` |
| PROTO | 上記に加えて、`position`（map_xy）、`se`、`confidence` |
| SEED 以降 | 上記に加えて、`regions`（lineage_id と membership）、`near_boundary` |

エラーのレスポンスは、`{"error": {"code": "...", "message": "..."}}` の形に統一する。500 のときは内部の詳細を返さない。

## 5.11 ログ（SEC-LOG）

- 1リクエストにつき1行の JSON を出す：`request_id`、`user_hash`（sha256(sub + salt) の先頭16文字）、`endpoint`、`status`、`latency_ms`。
- Authorization ヘッダ、リクエストボディ、例外メッセージに含まれる値は出力しない。uvicorn の access log は無効にし、自前のミドルウェアに一本化する。

## 5.12 オフラインパイプライン（ST-CHT）

    python -m pipeline.run --version 2027.01 --stage PROTO

    extract    analysis.responses から取得する。tombstone と品質フィルタ（reliability < しきい値）で除外する
      ↓
    report     項目ごとの分布、天井効果・床効果、項目ペアの共回答数の行列（ST-PMD-06）
      ↓
    em         欠損を含む多変量正規の平均と共分散を EM で推定する（ST-MIS-02）
      ↓
    efa        EM で得た共分散（相関）行列を入力に、因子数 k を決め、Λ と Ψ を推定する（factor_analyzer）
      ↓
    score      §5.8 の式で全員の f̂ を計算する
      ↓
    align      前の版がある場合、共通の観測点で Procrustes 整列をする（ST-CHT-06）
      ↓
    project    f̂ の上位2主成分から P と c を決める
      ↓
    cluster    GMM（BIC で成分数を選ぶ）と、Bootstrap による安定性の評価（SEED以降）
      ↓
    chart      map_xy の密度 → 等値線を生成する。人口が k 未満のセルは出力しない（FR-CHT-04）
      ↓
    write      app/models/chart-{v}/、static/charts/{v}/、両方の CURRENT / current.json

- 乱数シード、コミットハッシュ、件数を metadata に記録する（ST-CHT-05）。
- 比較尺度（`kind = 'comparison'`）は `extract` の段階で除外する。外的妥当性の相関はレポートにだけ出す（ST-CHT-03）。
- 出力は PR にして、運営者がレポートをレビューしてから merge する（FR-STG-02）。

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
- 登録画面で、3種類の同意事項（SEC-CON-01）への同意を必須にする。最初にログインしたときに `POST /v1/me/consents` で記録する。同意を記録するまで、測深の作成は 403 になる。

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

- 未ログイン時は `/charts/current.json` を、ログイン時は position レスポンスの `chart.version` を見て、`/charts/{version}/map.json` を取得する。Pages と Render のデプロイにずれがあっても、版の一致が保たれる。
- 等値線は、パイプラインが生成した SVG（`contours.svg`）を表示し、その上に自分の `map_xy` を Svelte の SVG 要素で重ねる。描画ライブラリは入れない。
- `StageBanner` が段階ごとの文言を出す（FR-STG-04、FR-POS-04、FR-POS-06）。
- 色や高さの表現に、優劣を連想させるもの（上位／下位、良い／悪い）を使わない（FR-UI-01）。

## 6.8 セキュリティヘッダ（SEC-FE）

`static/_headers`（Cloudflare Pages）：

    /*
      X-Content-Type-Options: nosniff
      Referrer-Policy: strict-origin-when-cross-origin
      Permissions-Policy: camera=(), microphone=(), geolocation=()
      Strict-Transport-Security: max-age=31536000; includeSubDomains
      X-Frame-Options: DENY

    /charts/*
      Cache-Control: public, max-age=31536000, immutable

    /charts/current.json
      Cache-Control: public, max-age=60

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

| 対象 | 設定 |
|---|---|
| Cloudflare Pages | ビルド `pnpm build`、出力 `build/`、本番ブランチ `main` |
| Render | Root Directory `app`、ビルド `uv sync --frozen --no-dev`、起動 `uv run uvicorn isobath.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log`、ヘルスチェック `/healthz` |
| Render ドメイン | カスタムドメイン `api.isobath.jocarium.productions` を設定し、`onrender.com` を Disabled にする（SEC-NET-02） |
| Cloudflare | api レコードを Proxied にする。WAF のマネージドルールと、IP単位の Rate Limit ルールを設定する |
| Supabase | `supabase db push` でマイグレーションを適用する。Data API の公開スキーマは `public` だけにする（`app` と `analysis` は公開しない）。Auth は CAPTCHA（Turnstile）とメール確認を有効にする |
| 項目の投入 | `app/items/items-{v}.csv` を、スクリプトで `app.questions` に upsert する（FR-OPS-01） |

海図を公開する手順（FR-STG-02、FR-OPS-03）：

    pipeline.run → PR（成果物とレポート）→ レビュー → main へ merge
      → Pages が static/charts/ を配信する
      → Render が app/models/CURRENT を読んで再起動する

---

# 8. テスト方針

| 対象 | 方法 | 検証する内容 |
|---|---|---|
| 位置の推定 | pytest | 全問回答したときに、真の因子を十分な精度で復元できること。回答が減るほど SE が増えること。所属確率の合計が1になること |
| 割り当て | pytest | 構成（30＋約60＋品質確認）、重複がないこと、selection_prob の値。大量にシミュレーションしたときに、ブロックのペアの出現頻度が均等になること |
| JWT | pytest | 期限切れ、iss / aud の不一致、alg=none、HS256 を拒否すること |
| RLS | pytest ＋ ローカルの Supabase（`supabase start`） | ユーザーAのトランザクションから、Bのセッションや回答を読めず、書けないこと。割り当てていない項目への INSERT がFKで失敗すること（受け入れ基準3、4） |
| 削除 | pytest ＋ ローカルの Supabase | `delete_me()` の後に、アプリのデータが0件になり、tombstone だけが残ること |
| 成果物 | pytest | `artifact.py` で書いたものを読み戻したとき、完全に一致すること |
| フロントエンド | vitest | draft の再送と重複除去、段階による表示の切り替え |
| E2E | Playwright | 登録 → 初回測深 → 中断 → 再開 → 完了 |

---

# 9. requirements.md への反映事項

本書の設計に伴い、requirements.md の次の箇所を更新する。

| 箇所 | 内容 |
|---|---|
| Q-11 | 決定：直接接続して SET LOCAL する方式（D-2） |
| §8.2 | `POST /v1/me/consents` を追加する |
| §11.1 | `chart_versions`、`regions`、`item_blocks` はMVPではテーブル化しない（D-10） |
| §9.4 Signup | Supabase Auth 側の Rate Limit と CAPTCHA で担保する（D-7） |
