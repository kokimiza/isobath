# 人格海図 ISOBATH
## System Design Proposal v0.1

> 要件は [requirements.md](requirements.md) に確定版として定める。本書と矛盾する場合は requirements.md を優先する。

---

# 1. 概要

**人格海図 ISOBATH** は、人間をあらかじめ決められた性格タイプへ分類するサービスではない。

利用者の回答や行動を継続的に観測し、その統計的な分布から、人間の人格が形成する「地形」を描いていく。

既存の性格診断では、

- あなたはAタイプ
- あなたは16種類のうち○○
- あなたの性格はこれ

というように、先に分類体系が存在し、その中へ人間を当てはめる。

ISOBATHでは順序を逆転させる。

> **人間を、決められたタイプに分類しない。**
>
> 一人ひとりの回答と行動を観測し、その統計的な分布から、人間の人格がつくる地形を描いていく。
>
> 誰かが参加するたび、海図は少しだけ精密になる。
>
> ときには、これまで誰も観測していなかった領域が見つかる。

ユーザー自身も単なる「診断される対象」ではない。

> **あなたを診断するのではない。  
> あなたも、人間という未知を測る観測点になる。**

これをISOBATHの中核思想とする。

---

# 2. プロダクトコンセプト

## 2.1 人格を「海」として扱う

ISOBATHでは人格空間を、未知の深海を含む巨大な海として表現する。

| 統計・システム上の概念 | ISOBATH上の表現 |
|---|---|
| 性格診断 | 測深 |
| 質問 | 観測項目 |
| 回答 | 観測値 |
| ユーザー | 観測点 |
| 人格ベクトル | 現在地 |
| 次元 | 海底を形成する軸 |
| クラスタ | 海域 |
| 密度 | 地形・海底 |
| クラスタ境界 | 海域境界 |
| 外れ値 | 未踏域候補 |
| 新しいクラスタ | 新海域 |
| PCA等による座標 | 海図上の座標 |
| 時系列変化 | 航跡 |
| 再クラスタリング | 海図改訂 |
| モデルバージョン | 海図版 |
| 不確実性 | 測深精度 |

「深い」「浅い」は優劣を表さない。

深さや座標は統計モデル上の位置を可視化するための表現であり、人間としての価値、能力、正常・異常を示す指標にはしない。

---

# 3. 体験設計

## 3.1 初回測深

新規ユーザーには、登録後に約100問へ回答してもらう。

目的は「タイプを決めること」ではなく、人格空間における初期位置を十分な精度で推定することである。

初回100問を、

**Initial Survey / 初回測深**

と呼ぶ。

完了後、

- 現在人格座標
- 所属可能性の高い海域
- 海域所属確率
- 推定精度
- 周辺地形
- 近傍人口密度

などを表示する。

## 3.2 質問構成：ISOBATH独自観測項目群

質問項目は既存尺度（IPIP-FFM、IPIP-NEO等）の直接利用を前提とせず、**ISOBATH独自の観測項目群として新規設計する。**

既存尺度をそのまま用いると、取得されるデータ空間そのものが既存理論の構成概念に拘束される。ISOBATHは、

> どのような人格構造が存在するかを、観測結果から探索する

ことを重視する。

Big Five、HEXACO等の既存人格モデルは最終的な分類体系として採用しない。既存研究は、

- どのような構成概念が研究されてきたか
- どのような項目表現が回答バイアスを生みやすいか
- 信頼性・妥当性の検証方法
- 再検査信頼性・測定誤差の扱い
- EFA / CFAの利用方法

といった**測定論上の知見および比較基準**として参照する。

観測領域の例：

- 対人関係 / 競争性 / 協調性 / 集団行動
- 不確実性への反応 / 探索傾向 / 意思決定傾向
- 規範志向 / 計画性
- 感情の変動 / 自己評価

観測領域の詳細な定義は [observation-domains.md](observation-domains.md) に定める。観測領域は因子ではなく、質問を漏れなく作るための設計上の区分である。

なお、観測領域の選定自体が一定の理論的前提を含む。完全に理論から自由な観測は存在しないことを自覚し、領域設定の根拠を記録する。

正式版の構成目安：

    約100 questions

    ├─ 約90
    │  独自観測項目
    │
    └─ 約10
       品質確認・逆転・整合性確認等

「100問」は固定値ではない。項目分析の結果が93問なら93問とする。数合わせのために項目を足さない。

## 3.3 項目開発プロセス

正式な100問を最初から固定しない。

1. 既存の人格心理学・心理測定研究を参照し、観測対象領域を広く設定する。
2. 180〜240問程度の候補項目群を作成する。
3. planned missing designによるパイロット調査を実施する（§3.3.1）。
4. 回答分布、項目間相関、天井効果・床効果、回答時間などを確認する。
5. 探索的因子分析等によって潜在構造を探索する。
6. 因子負荷の弱い項目、冗長な項目、交差負荷の大きい項目を整理する。
7. 約100問の正式項目群へ圧縮する（例：候補210 → 項目分析142 → EFA 118 → 再検査 93）。
8. 独立したサンプル（パイロットとは別のholdout）で因子構造、再検査信頼性、測定誤差等を検証する。
9. 質問項目群も海図と同様に版管理する（Item Set Version）。

### 3.3.1 Planned Missing Design

候補を150問程度まで削ると探索範囲を狭めすぎる。一方、全候補を一人に回答させるのは現実的でない。

**候補項目は多く残し、各参加者の回答は約100問に制限する。**

    候補項目総数：210問

    全員共通アンカー     30問
    ブロック割当項目     60問
    品質確認・再測定     10問
    ────────────────
    1人あたり           100問

#### 共通アンカー

全参加者が回答する項目。

- サンプル間の尺度を接続する
- 因子構造を安定させる
- 回答者を同じ潜在空間へ配置する
- 収集途中でも粗い海図を作る

アンカーはデータが存在しない段階で選ぶため、観測領域ごとに均等に割り当てて網羅性を優先する（observation-domains.md §2）。アンカーは後から外しにくいため、Item Set Version間のlinking itemsを兼ねる。

#### ブロック割当

アンカー以外の項目をブロックに分け、balanced incomplete block design（BIBD）に近い形で割り当てる。

    User A   Anchor + Block A + Block C + Block F
    User B   Anchor + Block B + Block D + Block F
    User C   Anchor + Block A + Block D + Block E
    User D   Anchor + Block B + Block C + Block E

単純ランダムより、特定の項目ペアの共回答数が極端に少なくなることを防ぐ。

ブロック内の出題順・ブロック順はランダム化し、順序効果・疲労効果を相殺する。

共回答数の見積もり（例：180問 = 20問 × 9ブロック、1人3ブロック）：

| 項目ペア | 共回答率 | N=1,000時 |
|---|---|---|
| アンカー × アンカー | 1 | 1,000 |
| アンカー × ブロック | 1/3 | 約333 |
| 同一ブロック内 | 1/3 | 約333 |
| 異なるブロック間 | 1/12 | 約83 |

異なるブロック間の相関推定はN=1,000でも粗い（SE ≈ 0.11）。初期のEFAはアンカー＋ブロック内構造を主に用いる。

#### 欠損データの扱い

設計的に欠損を発生させるため、Phase 1では欠損を概ねMCARとみなせる。

| 用途 | 手法 |
|---|---|
| 探索初期の相関行列の確認 | pairwise deletion |
| 正式なEFA / CFA | FIML / Multiple Imputation / 因子分析側のmissing-data handling |

pairwise deletionのみで正式な因子分析を行わない。

#### 段階的な出題配分

    Phase 1  広域測量
    海底が何も分からない
    → ブロックを均等に割り当てる

    Phase 2  精密測量
    質問143と質問177の関係がよく分からない
    → 推定精度の低い項目ペアへの共回答を優先的に増やす

    Phase 3  重点測量
    因子候補F7を構成する項目が弱い
    → F7周辺の項目を重点的に出題する

Phase 2以降は出題が観測データに依存するため、欠損はMCARではなくMARとなる。出題規則が観測済み情報のみに依存する限りFIML / MIは妥当だが、pairwise deletionは偏りうる。

したがって、セッションごとに

- 出題フェーズ
- 割当ブロック / 項目
- 出題規則のバージョン
- 選択確率

を記録し、後から出題過程を再現・検証できるようにする。

Phase 3の仕組みは、継続測深（§4）のAdaptive Question Selectionへそのまま発展させる。

### パイロット期の外的比較尺度

独自項目だけでは「この軸は何を測っているのか」を説明できない。

パイロット期に限り、既存の短尺尺度（public domainのもの）を**比較専用**として併用する。

    海図構築
    → 独自項目のみ

    外的妥当性の検討
    → 独自軸 × 既存尺度の相関

    未知のAxis 7
       ↓
    既存尺度Xとは弱い負相関
    既存尺度Yとは中程度の正相関
    既存尺度では十分説明されない

比較尺度の回答は海図の学習データに含めない。第三者による日本語訳は利用条件を確認し、原則として自前で翻訳する。

### パイロット参加者の負担

planned missing designにより1人あたり約100問に抑える。分割回答・途中保存（Resume）を前提とし、パイロットそのものをISOBATHの最初の公開フェーズとして扱う（§57.1）。

### Item Set Versionと航跡

項目群を改訂すると、版をまたいだ座標は直接比較できない。

- 版をまたいで維持する共通項目（linking items）を確保し、等化（equating）を行う。
- Drift判定は、等化されていない項目版をまたいで行わない。

## 3.4 観測手段のロードマップ

    v1
    Questionnaire

    v2
    + Cognitive Tasks

    v3
    + Behavioral Tasks

MVPは質問紙のみで人格海図を成立させる。

---

# 4. 継続測深

ISOBATHは一度診断して終了するサービスにしない。

ログイン時などに10～20問程度の追加観測を提示する。

これを、

**Continuous Survey / 継続測深**

とする。

追加回答によって人格座標を再推定する。

結果、

- 前回とほとんど変わらない
- 同一海域内を移動する
- 海域境界へ近づく
- 別の海域へ移動する
- 従来の海域では説明しにくくなる

といった変化が発生する。

---

# 5. 「性格が変わる」ことを楽しむ

ISOBATHでは人格を永久固定値とは扱わない。

一般的な性格診断では、

> 前回INTPだったのに今回はENTPになった

という現象が「診断のブレ」のように扱われることがある。

ISOBATHでは逆に、それ自体を体験へ取り込む。

例：

> **海流を検出しました**
>
> 過去90日間、あなたの観測点は継続的に南東方向へ移動しています。
>
> 珊瑚海域 61% → 44%  
> 外洋海域 31% → 49%
>
> 現在、海域境界付近を航行しています。

海域が変わった場合：

> **越境**
>
> 最新の測深により、現在地の最尤海域が変更されました。
>
> 珊瑚海域 → 外洋海域
>
> 珊瑚海域には284日間滞在していました。

変わらないこともコンテンツとする。

> **定着度 96.8%**
>
> 417日間、同じ海域を観測しています。
>
> 現在の海図上では非常に安定した観測点です。

したがって、

- 動くユーザーは「航海」を楽しむ
- 動かないユーザーは「定着」を楽しむ

という両立が可能になる。

---

# 6. 航跡

ユーザーの人格座標を時系列で保存する。

    Initial ●
             \
              ● Day 14
               \
                ● Day 31
                 |
                 ● Day 62
                  \
                   ● Today

長期利用者には、

**「あなたの一年間の航跡」**

を生成する。

単一の性格タイプよりも、

> 自分は一年間でどこからどこへ移動したのか

を振り返ることをISOBATHの主要体験とする。

---

# 7. 二種類の変化

ISOBATHでは必ず次の二つを区別する。

## 7.1 Personal Drift

本人の回答傾向が時間とともに変化した場合。

    User
      A → A → A → B → B

これを本人の「航跡」とする。

## 7.2 Chart Revision

ユーザー全体が増えたことで人格空間そのものの推定が変化した場合。

    Chart 2027.04
         ↓
    +184,291 observations
         ↓
    Chart 2027.05

同じ回答を持つ人でも、海図の精度向上によって所属海域の解釈が変わる可能性がある。

UIでは、

    PERSONAL UPDATE
    あなたの航跡に変化があります。

    CHART UPDATE
    新しい観測によって人格海図が改訂されました。

と明確に分ける。

---

# 8. 「人格変化」と「測定精度向上」を区別する

追加質問によって分類が変わっても、

「本人の人格が変化した」

とは限らない。

単に初期100問では情報が不足していて、追加観測によって本来の位置が精密化された可能性がある。

内部的には少なくとも、

    Position
    現在人格座標

    Confidence
    座標推定の確信度

    Drift
    時系列的な人格変化量

を別々に管理する。

したがって、

> 海図が精密になりました

と、

> あなたの航跡に変化があります

を別のイベントとして扱う。

## 8.1 Drift判定

座標の単純距離で「性格が変わった」と判定しない。

    Observed Change
    =
    True Change
    + Measurement Error
    + Temporary State

として扱う。

### MVP：Reliable Change

各尺度の再検査信頼性 `r` を用い、

    Sdiff = SD × sqrt(2 × (1 - r))

を基に、変化量が通常の測定誤差を超えているかを判定する。

独自項目群を採用するため文献値は利用できない。`r` はISOBATH利用者の再測定データから推定する。十分な再測定データが蓄積するまでDrift判定は行わず、航跡の表示のみとする。

### 将来：多次元判定

    Δ = x(t2) - x(t1)

    D² = Δ' ΣΔ⁻¹ Δ

誤差共分散を含むMahalanobis型の変化判定とする。

継続測深は10～20問のため、現在地は「全項目の最新回答」から推定し、推定誤差（SE）はセッションごとに算出する。ΣΔもセッション単位で持つ。

### 継続性の要件

一回閾値を超えただけではDrift認定しない。

    Session 1    ──●
    Session 2      ●
    Session 3        ●
    Session 4         ●
                        ↑

    測定誤差を超える同方向の変化が
    3セッション継続

した場合に初めて、

> 海流を検出しました

とする。単発の場合は、

> 今回の測深では位置に揺らぎがあります

程度の表現に留める。

---

# 9. 統計設計

ISOBATHでは一つのクラスタリング手法だけを「真実」としない。

複数の統計手法によって繰り返し観測される構造を人格海図として採用する。

基本原則：

> **ISOBATHは人格類型を定義しない。  
> 複数の統計的測量によって、繰り返し観測される人格構造だけを海図に記載する。**

---

# 10. 統計処理パイプライン

    Questionnaire（Cognitive Tasksはv2以降）
                │
                ▼
        Data Quality Check
                │
                ▼
          Standardization
                │
                ▼
      ┌───────────────────┐
      │ Measurement Model │
      │ EFA / CFA         │
      └─────────┬─────────┘
                │
                ▼
      ┌───────────────────┐
      │ Personality Space │
      │ PCA / FactorScore │
      └─────────┬─────────┘
                │
                ▼
    ┌─────────────────────────┐
    │ Parallel Survey Methods │
    │                         │
    │ k-means                 │
    │ Hierarchical            │
    │ GMM                     │
    │ LPA                     │
    │ Spectral Clustering     │
    └────────────┬────────────┘
                 │
                 ▼
        Statistical Validation
                 │
        ┌────────┼────────┐
        │        │        │
     BIC/AIC  Stability  Silhouette
                 │
                 ▼
          Consensus Model
                 │
                 ▼
        Personality Chart

---

# 11. PCAと因子分析の役割

PCAと因子分析は同一目的で使わない。

## PCA

観測された回答の分散を圧縮し、人格空間を扱いやすい座標へ変換する。

ISOBATHで言えば、

**測量座標系**

に近い。

## 因子分析

複数の質問に共通する潜在的な構造を推定する。

ISOBATHで言えば、

**海底がなぜその地形になっているかを調査する地質調査**

に近い。

探索段階ではEFA、モデル確認にはCFAを利用する。

---

# 12. クラスタリング

複数手法を並行利用する。

### k-means

高速で大規模データへ適用しやすい。

ただし球状・等分散に近いクラスタを仮定するため、単独では人格構造を決定しない。

### Gaussian Mixture Model

所属を確率として表現できる。

例：

    海域07  62%
    海域12  31%
    海域03   7%

これは「境界の曖昧な人格海図」というISOBATHの思想と特に相性が良い。

### Latent Profile Analysis

連続指標から潜在的なプロフィール群を探索する。

### Hierarchical Clustering

海域を階層的に表現できる。

    大分類：2海域
        ↓
    中分類：4海域
        ↓
    詳細：9海域

というズームレベルによる地形表示へ利用できる。

### Spectral Clustering

通常のユークリッド距離だけでは発見しにくい非線形構造を探索する。

大規模化した場合には近似手法を検討する。

---

# 13. Consensus Map

各モデルが異なる結果を出すことを隠さない。

例：

    k-means       8 regions
    GMM          11 regions
    LPA           9 regions
    Spectral     10 regions
    Hierarchical  9 regions

そのうえで、

    海域A
    5 / 5 models support

    海域B
    4 / 5 models support

    海域C
    2 / 5 models support

のようにモデル間合意度を算出する。

「海域Aという人格タイプが存在する」と断定するのではなく、

> 異なる統計的測量方法でも、この位置には繰り返し高密度領域が観測される

という形で表現する。

---

# 14. 未踏域

新しいユーザーが既存人格空間では説明しにくい場合でも、その一人だけで新しい人格タイプを作らない。

次のような指標を組み合わせる。

- PCA等による unexplained residual
- Mahalanobis Distance
- Local Outlier Factor
- Isolation Forest
- 周辺観測密度
- クラスタ所属確率
- モデル間合意度

異常度が高い場合、

**UNSURVEYED / 未踏域**

として扱う。

その後、多数のユーザーが近傍へ集積した場合に、

    未踏域
       ↓
    新海域候補
       ↓
    複数モデルで再現
       ↓
    安定性検証
       ↓
    海図へ記載

という過程を踏む。

---

# 15. データ品質

外れた回答を即座に「珍しい人格」とみなさない。

以下を先に検査する。

- 極端に短い回答時間
- 全質問で同一回答
- ランダム回答の疑い
- 矛盾した回答
- Botによる回答
- 大量アカウント生成
- 同一主体による統計汚染
- 不正なAPI直接操作

これらは人格的な外れ値とは区別する。

ISOBATHにおいて重要なセキュリティ資産は、

**人格データそのものの完全性**

でもある。

---

# 16. システム構成

初期構成を以下に決定する。

    ┌─────────────────────────────┐
    │ Cloudflare Pages            │
    │                             │
    │ SvelteKit                   │
    │ Static Frontend             │
    └──────────────┬──────────────┘
                   │
                   │ HTTPS / JSON
                   ▼
    ┌─────────────────────────────┐
    │ Cloudflare                  │
    │                             │
    │ DNS                         │
    │ Proxy                       │
    │ WAF                         │
    │ Rate Limit                  │
    └──────────────┬──────────────┘
                   │
                   ▼
    ┌─────────────────────────────┐
    │ Render Free                 │
    │                             │
    │ Python                      │
    │ FastAPI                     │
    │ Statistical Survey Engine   │
    └──────────────┬──────────────┘
                   │
                   ▼
    ┌─────────────────────────────┐
    │ Supabase                    │
    │                             │
    │ Auth                        │
    │ PostgreSQL                  │
    │ RLS                         │
    └─────────────────────────────┘

役割を明確に分離する。

| Component | Responsibility |
|---|---|
| SvelteKit | UI / Visualization |
| Cloudflare Pages | 静的コンテンツ配信 |
| Cloudflare | API保護・Rate Limit |
| FastAPI | 業務ロジック・個人座標計算 |
| Python Analysis | 統計処理 |
| Supabase Auth | 認証 |
| Supabase PostgreSQL | 永続データ |
| PostgreSQL RLS | 行レベル認可 |

---

# 17. SvelteKit

フロントエンドはSvelteKitを採用する。

Cloudflare Pagesから静的配信する。

主な画面：

    /
    Landing

    /survey/initial
    初回測深

    /survey
    継続測深

    /chart
    人格海図

    /journey
    航跡

    /profile
    現在人格情報

    /settings
    アカウント・データ管理

FastAPI側にHTMLや画像を配信させない。

---

# 18. FastAPI

FastAPIは、

**JSON API + Statistical Survey Engine**

に専念する。

担当：

- Survey Session生成
- 質問選択
- 回答受付
- 入力検証
- ユーザー現在地計算
- 既存モデルへの射影
- Drift計算
- Confidence計算
- History取得
- Chart Version通知

HTML、CSS、JavaScript、画像などは原則配信しない。

---

# 19. オンライン処理と海図再計算を分離する

ユーザーアクセスごとに、

- PCA再学習
- GMM再学習
- Spectral Clustering
- 全ユーザー再クラスタリング

を実行してはいけない。

通常APIでは、

    New Answers
        ↓
    Feature Update
        ↓
    Existing Model
        ↓
    Projection
        ↓
    Current Position

だけを実行する。

全体再測量は別処理とする。

    All Valid Observations
            ↓
    Statistical Pipeline
            ↓
    Chart Revision
            ↓
    Model Artifact
            ↓
    New Deployment

初期段階では再測量処理をローカルまたはCI上のPythonスクリプトとして実行してもよい。

成長後はBackground Worker / Job環境へ分離する。

---

# 20. モデルアーティファクト

最新人格海図モデルを、

    model/
      chart-2026.09/
        scaler
        pca
        factor-model
        gmm
        regions
        metadata

のようなバージョン付きアーティファクトとして管理する。

FastAPI起動時に読み込み、メモリ上へ保持する。

通常リクエストごとにDBからモデル全体を取得しない。

これによって、

- レイテンシ削減
- DB負荷削減
- 外部通信削減
- モデル再現性確保

を実現する。

## 20.1 メモリ制約

Render Free Web Serviceは 0.1 CPU / 512MB RAM。

FastAPIプロセスへ以下を保持しない。

    巨大なpandas DataFrame
    training dataset
    全ユーザー座標

保持するのは推論に必要な、

    Scaler parameters
    PCA components
    Factor loadings
    GMM parameters
    Region metadata

のみ。学習済みモデルだけをロードし、数MB～数十MB程度を目標とする。

## 20.2 Cold Start

Render Freeは15分間inbound trafficがなければspin downし、次回リクエストで起動する（約1分）。

MVPではCold Startを仕様として許容し、

> 測量船を起動しています……

といったUIで表現する。

---

# 21. Supabase

Supabaseには、

**Auth + PostgreSQL + RLS**

を担当させる。

Render PostgreSQLは利用しない。

Supabase Authがユーザー認証を行う。

    SvelteKit
        ↓
    Supabase Auth
        ↓
    Access Token / JWT
        ↓
    FastAPI

FastAPIはJWTを検証した上でユーザーを確定する。

---

# 22. API設計原則

APIは、

**帯域・CPU・DBアクセスを有限資源として扱う。**

Render側で大量データを配信しない。

基本原則：

1. 必要なデータだけ返す
2. 全件取得を禁止する
3. ページングする
4. 変更されないものは静的配信する
5. 回答をまとめて送る
6. モデル全体をクライアントへ送らない
7. 他ユーザーの個票を送らない
8. 大規模統計処理をHTTPリクエストから実行しない

---

# 23. API Version

APIは最初からバージョンを付ける。

    /v1/...

将来モデルやレスポンス構造を変更しても互換性を管理できるようにする。

---

# 24. 主要API

## Metadata

    GET /v1/meta

現在のサービス・海図バージョンなど。

目標レスポンス：

    < 1 KB

---

## Current Survey

    GET /v1/me/surveys/current

現在割り当てられているSurvey Sessionを取得する。

一度に10～20問程度。

初回100問も20問程度ずつ分割取得可能とする。

目標：

    < 10～15 KB

---

## Batch Answers

    POST /v1/me/surveys/{survey_id}/answers

回答は一問ごとにPOSTしない。

例えば5～10問ごとにまとめて同期する。

Request例：

    {
      "answers": [
        {"question_id": 14, "value": 4},
        {"question_id": 27, "value": 2},
        {"question_id": 91, "value": 5}
      ]
    }

正常時は、

    HTTP 204 No Content

を基本とする。

毎回巨大な「更新後人格データ」を返さない。

---

## Complete Survey

    POST /v1/me/surveys/{survey_id}/complete

Survey完了を確定する。

必要に応じて再推定を実行する。

---

## Current Position

    GET /v1/me/position

例：

    {
      "chart": "2026.09",
      "region": "R12",
      "membership": 0.62,
      "confidence": 0.91,
      "position": [0.31, -0.82],
      "drift": 0.14
    }

目標：

    < 2 KB

---

## History

    GET /v1/me/history?cursor=xxxxx&limit=20

Cursor Paginationを利用する。

全履歴を一括取得させない。

目標：

    < 10 KB / page

---

## Current Chart

    GET /v1/chart/current

返すのは、

    {
      "version": "2026.09"
    }

程度。

人格海図そのものをRenderから配信しない。

---

# 25. 人格海図の配信

これは重要な設計原則とする。

禁止：

    GET /map

    → ユーザー100万人分の座標JSON

代わりに、

    Analysis
       ↓
    Density / Contour Generation
       ↓
    Aggregated Chart
       ↓
    Static JSON / SVG
       ↓
    Cloudflare

とする。

海図は、

**動的APIレスポンスではなく生成済み成果物**

として扱う。

例：

    /charts/2026.09/map.json
    /charts/2026.09/contours.svg

バージョン付きURLにすることで長期間キャッシュ可能になる。

---

# 26. Cache Policy

### 個人情報API

    /v1/me/*

は、

    Cache-Control: private, no-store

を基本とする。

### 公開メタデータ

    /v1/chart/current

などは短時間キャッシュ可能とする。

### バージョン付き人格海図

    /charts/2026.09/*

はimmutableな静的資産として扱う。

---

# 27. 過剰アクセス対策

ISOBATHでは、

**可用性より先に費用上限を守る**

という運用方針を採用する。

アクセスが100倍になった場合、

「自動的に100倍のサーバを購入する」

のではなく、

> 混雑したら止まる

ことを許容する。

---

# 28. Cloudflareによる入口防御

APIの公開URLを、

    api.isobath.jocarium.productions

とする。

    Client
      ↓
    Cloudflare
      ↓
    Render

Cloudflare側で、

- Rate Limiting
- WAF
- Bot対策
- 異常トラフィック遮断

を実施する。

Renderデフォルトドメインへの直接アクセスは無効化し、Cloudflareを迂回してOriginへ到達できない構成とする。

---

# 29. Rate Limit

エンドポイントごとに制限を変える。

例：

| API | 基本方針 |
|---|---|
| GET position | 比較的緩い |
| GET history | 中程度 |
| GET questions | 中程度 |
| POST answers | 厳格 |
| Survey作成 | 厳格 |
| Signup | 非常に厳格 |
| Public metadata | Cache優先 |

単純なIP制限だけにしない。

認証後は、

- User ID
- IP Address
- Endpoint
- 時間窓

などを組み合わせる。

Rate Limit超過時は、

    HTTP 429 Too Many Requests

を返す。

---

# 30. Emergency Mode

アクセス急増時に段階的に機能を落とせるようにする。

    NORMAL

        ↓

    LEVEL 1
    Rate Limit強化

        ↓

    LEVEL 2
    新規登録停止

        ↓

    LEVEL 3
    回答受付停止
    Read Only

        ↓

    LEVEL 4
    API停止

それでもCloudflare Pages側の、

- Landing Page
- 人格海図
- 障害案内

は表示可能とする。

環境変数または設定値：

    SIGNUP_ENABLED
    SURVEY_WRITE_ENABLED
    ANALYSIS_ENABLED
    READ_ONLY_MODE

などで制御する。

---

# 31. FastAPIリソース制御

APIには明示的に上限を設定する。

- Request Body最大サイズ
- 配列最大件数
- 文字列最大長
- DB Query timeout
- API timeout
- 最大ページサイズ
- Survey Answers最大数

攻撃者から、

    answers = 10000000件

のようなJSONを送られても処理しない。

---

# 32. 認証

認証はSupabaseへ委譲する。

FastAPIでパスワードを管理しない。

    Supabase Auth
        ↓
    JWT
        ↓
    FastAPI
        ↓
    JWT verification

検証項目：

- Signature
- exp
- iss
- aud
- sub
- 許可された署名アルゴリズム

ユーザーIDは必ずJWTから取得する。

---

# 33. BOLA / IDOR対策

悪いAPI：

    POST /answers

    {
      "user_id": "other-user",
      ...
    }

良いAPI：

    POST /v1/me/surveys/{id}/answers

FastAPI側で、

    JWT.sub
       ↓
    authenticated_user_id

を確定する。

クライアントからuser_idを指定させない。

---

# 34. 認可

認可は二段構えとする。

    JWT
     ↓
    FastAPI Authorization
     ↓
    Supabase RLS

FastAPIの実装ミスだけで他ユーザーの情報が流出しないようにする。

## 34.1 RLSを実際に効かせる経路

FastAPIがサーバ権限でDBへ接続するとRLSはバイパスされ、二段構えにならない。

通常処理では、FastAPIが検証したものと**同じUser JWT**でDBへアクセスする。

    SvelteKit
       ↓
    Supabase Auth
       ↓
    User JWT
       ↓
    FastAPI（JWT検証）
       ↓
    同じUser JWT
       ↓
    Supabase Data API / PostgREST
       ↓
    RLS

実装の選択肢：

- Supabase Data API（PostgREST）へUser JWTを付与して呼ぶ
- Postgresへ直接接続し、トランザクション内で `SET LOCAL ROLE authenticated` と `request.jwt.claims` を設定する

後者は複数文をトランザクションにまとめられる（例：割当検証＋回答INSERTを原子的に実行）。いずれの場合もRLSはユーザー権限で評価される。

権限の使い分け：

    通常API
    → User JWT
    → RLS ON

    全体統計バッチ
    → Server Secret
    → RLS bypass

---

# 35. Row Level Security

ユーザー所有データについて、

    user_id = auth.uid()

を基本条件にする。

対象：

- profiles
- survey_sessions
- answers
- position_snapshots
- history

SELECT / INSERT / UPDATE / DELETEは操作ごとに明示的なPolicyを定義する。

---

# 36. 権限分離

ブラウザ：

    Supabase Publishable Key

FastAPI：

    User JWT（RLS適用）

統計再計算・管理処理：

    Admin / Elevated Credential

とする。

強い権限をブラウザへ絶対に配布しない。

service_role相当の強力なCredentialは通常ユーザーAPIで極力利用しない。

---

# 37. Question Integrity

クライアントが好きなquestion_idへ回答できないようにする。

    Survey Session
          ↓
    Assigned Questions
          ↓
    Answer Validation

DB上で、

    survey_session_questions

を持つ。

回答時に、

> この質問は本当にこのSurvey Sessionへ割り当てられたか

を検証する。

---

# 38. DB制約

アプリケーションだけにデータ完全性を任せない。

例：

    CHECK answer BETWEEN 1 AND 5

    FOREIGN KEY question_id

    FOREIGN KEY survey_session_id

    UNIQUE(survey_session_id, question_id)

    NOT NULL user_id

防御を、

    Svelte Validation
           ↓
    Pydantic
           ↓
    Business Validation
           ↓
    PostgreSQL Constraint
           ↓
    RLS

と重ねる。

---

# 39. データモデル

主要テーブル：

## profiles

アプリ内ユーザープロフィール。

Supabase Authとは分離する。

## questions

質問マスタ。`item_set_version`、候補／正式／比較専用／品質確認の区分、linking itemフラグを持つ。

## survey_sessions

一回の測深セッション。

## survey_session_questions

そのセッションへ割り当てた質問。割当ブロック、出題フェーズ、出題規則バージョン、選択確率を併せて記録する（§3.3.1）。

## answers

回答。

## feature_snapshots

各時点の特徴量。

## position_snapshots

人格座標履歴。

## chart_versions

人格海図バージョン。

## regions

各海域。`chart_version` + `cluster_id` と、版をまたいで同一海域を表す `region_lineage_id` を分離して持つ（§57.2）。

## region_lineage_events

海域の継承・分割・統合履歴。

## region_memberships

海域所属推定。

## quality_flags

回答品質に関するフラグ。

## audit_events

重要操作記録。

---

# 40. 個人情報と人格情報の分離

認証情報と統計分析データを可能な限り分離する。

    Supabase Auth
        │
        │ UUID
        ▼
    Profile
        │
        │ Pseudonymous ID
        ▼
    Statistical Dataset

統計解析データへ、

- メールアドレス
- OAuth情報
- 氏名

などを持ち込まない。

人格回答は高いプライバシー性を持つ情報として扱う。

---

# 41. 公開海図のプライバシー

公開人格海図には、

**他人の個別観測点を表示しない。**

表示するのは、

- Density
- Contour
- Region
- Aggregate Statistics

のみ。

ユーザー自身の座標だけをクライアント上で重ねる。

これにより、

「この点は特定ユーザーである」

という推測を困難にする。

人口の極端に少ない領域については集約・非表示も検討する。

---

# 41.1 アカウント削除と学習済み海図

削除操作：

    Account deletion
          ↓
    Identity deletion
          ↓
    Raw answers deletion
          ↓
    Position / history deletion
          ↓
    analysis exclusion tombstone

ポリシー：

> **削除後、そのユーザーの生データは保持しない。既存の集約済み海図については遡及再生成せず、次回海図改訂から除外する。**

- 生成済みの海図（例：Chart 2026.09）を削除の瞬間に再学習はしない。
- 次回改訂（例：Chart 2026.10）の生成時に、tombstoneを参照して削除済みユーザーを除外する。
- モデル・公開成果物から個人データを復元できる設計にしない。公開成果物は density / contour / aggregate region のみとする（§41）。
- DBバックアップ（Supabase PITR等）に削除済みデータが残る期間を明記する。

---

# 42. ログ

ログへ以下を記録しない。

- JWT
- Refresh Token
- Authorization Header
- パスワード
- service_role等のSecret
- 回答本文
- メールアドレス

ログ例：

    request_id=...
    user_hash=...
    endpoint=/v1/me/position
    status=200
    latency_ms=84

必要十分な運用ログだけを保持する。

---

# 43. フロントエンドセキュリティ

Cloudflare Pages側でセキュリティヘッダを設定する。

基本方針：

    Content-Security-Policy

    X-Content-Type-Options: nosniff

    Referrer-Policy

    Permissions-Policy

    Strict-Transport-Security

外部JavaScript SDKをむやみに追加しない。

特に認証JWTを扱うため、

**XSSを主要脅威として扱う。**

第三者広告・Analytics等を導入する場合もCSPを崩さないことを優先する。

---

# 44. CORS

本番APIは、

    https://isobath.jocarium.productions
    https://www.isobath.jocarium.productions

など必要なOriginだけ許可する。

開発環境は別設定とする。

    http://localhost:5173

`*` は使用しない。

CORSを認証・認可の代替にはしない。

---

# 45. Secret管理

SecretはGitへ保存しない。

    .env
    *.secret

等はリポジトリ対象外とする。

FastAPI側SecretはRender Environment Variablesで管理する。

本番・開発環境でCredentialを分離する。

---

# 46. 統計モデル汚染対策

ISOBATH固有のセキュリティ対策として、

**Data Poisoning / Sybil Attack**

を想定する。

例：

    Attacker
       ↓
    10,000 fake accounts
       ↓
    Artificial Answers
       ↓
    Chart Retraining
       ↓
    Fake Personality Region

これを防止する。

候補対策：

- Email Verification
- CAPTCHA
- Signup Rate Limit
- 回答速度検査
- 重複パターン検査
- 品質スコア
- 急激な分布変化検知
- Chart生成前の品質フィルタ

異常データは即削除するのではなく、

    Raw Observation
        ↓
    Quality Flag
        ↓
    Validated Dataset

と分ける。

---

# 47. ソフトウェアサプライチェーン

依存ライブラリを必要以上に増やさない。

Frontend：

    pnpm-lock.yaml / package-lock.json

Backend：

    uv.lock / requirements lock

などでバージョンを固定する。

定期的に、

- Dependency Update
- Vulnerability Scan
- Secret Scan

を行う。

---

# 48. デプロイ

Frontend：

    Git Repository
         ↓
    Cloudflare Pages
         ↓
    SvelteKit Static Build

Backend：

    Git Repository
         ↓
    Render
         ↓
    FastAPI

本番ブランチへのmergeを本番反映の基本単位とする。

---

# 49. Render Origin保護

RenderにはカスタムAPIドメインのみを割り当てる。

    api.isobath.jocarium.productions

Cloudflare Proxyを経由させる。

Render標準ドメインは無効化する。

Renderではカスタムドメインを設定したサービスの `onrender.com` サブドメインをDisabledにでき、アクセスは404となりアプリへ到達しない。

    api.isobath.jocarium.productions
           ↓
    Cloudflare
           ↓
    Render Custom Domain

    xxxx.onrender.com
           ↓
    404

これによって、

    Attacker
       ↓
    xxx.onrender.com
       ↓
    Cloudflare回避

という経路を閉じる。

---

# 50. Health Check

軽量な、

    GET /healthz

を実装する。

レスポンス：

    {
      "status": "ok"
    }

程度とする。

通常のHealth Checkで、

- 大量SQL
- 統計処理
- 外部API

を実行しない。

---

# 51. Observability

最低限、次を監視する。

### Application

- Requests / min
- p50 latency
- p95 latency
- HTTP 429
- HTTP 4xx
- HTTP 5xx

### Render

- CPU
- Memory
- Outbound Traffic

### Supabase

- DB size
- DB connections
- Query latency
- Auth usage

### ISOBATH

- New users
- Survey completion
- Answers / min
- Quality flags
- Chart version
- Statistical drift

---

# 52. バズ時の運用

例えばSNS等で突然アクセスが100倍になった場合：

    Traffic Spike
         ↓
    Cloudflare Cache
         ↓
    Cloudflare Rate Limit
         ↓
    FastAPI Resource Limit
         ↓
    Render single service
         ↓
    429 / 503

という順で負荷を止める。

重要なのは、

**オートスケールして無制限に金を使わないこと。**

サービス停止を許容する。

---

# 53. API停止時のUX

APIが停止してもCloudflare Pagesは稼働する。

ユーザーには、

> 現在、測量船へのアクセスが集中しています。
>
> 人格海図の閲覧は引き続き利用できます。
> 測深はしばらくしてから再度お試しください。

などの画面を表示する。

「サーバが死んだ」ではなく、ISOBATHの世界観に沿って障害を表現してもよい。

---

# 54. Render Freeから有料への移行判断

単純に「ユーザー○人」で判断しない。

次を判断材料とする。

- Free運用枠への継続的接近
- p95 latency悪化
- Cold StartがUX上無視できない
- 継続的な5xx
- 継続的なRate Limit発生
- 毎日安定した利用者が存在する
- SNSバズが一過性ではない

バズした瞬間に有料化するのではなく、

> 持続的需要である

と確認してから移行する。

---

# 55. 有料化後

Phase 2では、

    Cloudflare Pages
           +
    Cloudflare WAF
           +
    Render Paid
           +
    Supabase
           +
    Separate Analysis Worker

へ拡張する。

統計処理をFastAPI Web Processから分離する。

---

# 56. 将来的な分析基盤

データ量増加後：

    FastAPI
       │
       └── Online Inference

    Analysis Worker
       │
       ├── EFA
       ├── CFA
       ├── PCA
       ├── k-means
       ├── GMM
       ├── LPA
       ├── Hierarchical
       ├── Spectral
       └── Consensus

とする。

Web APIと統計再計算を物理的にも分離する。

---

# 57. チャートバージョニング

人格海図は必ずバージョン管理する。

例：

    ISOBATH Chart 2026.09
    ISOBATH Chart 2026.10
    ISOBATH Chart 2027.01

過去の海図も保存する。

海域数が、

    2027 : 9 regions
    2028 : 11 regions
    2030 : 7 regions

のように増減しても隠さない。

それは統計モデルが失敗したというより、

**人類に関する観測が増え、海図が改訂された履歴**

として扱う。

## 57.1 Seed Chart

独自項目群を採用するため、既存の公開人格データをSeed学習データとして利用できない。

ISOBATHは既成の海図を提示せず、観測が蓄積するまでを**未測量期間**として扱う。

「一般公開前に数千人集める」のではなく、**収集中そのものをサービスの成長過程にする**。パイロット（§3.3.1）がそのままISOBATHの最初の公開フェーズとなる。

| 段階 | 目安N | 統計処理 | 提示内容 |
|---|---|---|---|
| UNCHARTED（未測量） | 〜299 | 観測開始 | 観測番号・参加人数・項目単位の集計 |
| Pre-Chart | 300〜 | 項目品質・回答分布の確認 | 回答分布・海図形成の進捗 |
| Proto Chart | 500〜 | 最初のEFA / PCA（アンカー＋ブロック内構造中心） | 少数次元への暫定射影。海域は表示しない |
| Seed Chart 0.1 | 1,000〜 | Bootstrap開始 | 暫定海域・所属確率 |
| — | 2,000〜3,000 | 項目削減・モデル比較・再現性検証 | Seed Chart改訂 |
| 正式項目群候補 | 3,000〜 | 約100問の正式版候補 | — |
| Chart 1.0 | 統計的安定性を確認後 | — | 正式海図 |

人数は目安にすぎない。planned missing designでは項目ペアごとの共回答数が実効的な標本となるため、段階移行は総人数ではなく共回答数と推定精度で判定する（§3.3.1）。

### 未測量期間の体験

「何も見せない」とはしない。未測量期間そのものをコンテンツにする。

> **あなたは第37観測点です。**
>
> この海はまだ測量されていません。

> 現在 428 人が測深に参加しています。
> 人格海図はまだ「Proto Chart」です。

初期参加者は「初期測量隊」として扱い、「人類の海図をみんなで作る」過程を共有する。

Proto / Seed Chartは「人類の海図」とは呼ばない。

> **暫定海図 / Seed Chart**
>
> ISOBATHの初期観測から作成されています。
> 観測が増えるにつれて、この海図は大きく改訂される可能性があります。

### Chart 1.0の条件

人数ではなく**海図の安定性で判定する**。

    N >= 項目数に応じた最低必要数
    AND 独立サンプルで因子構造が再現
    AND bootstrap stability >= 閾値
    AND 複数clusteringのconsensusが安定

## 57.2 海域IDの継承

`cluster_id` を海域の恒久IDにしない。

    chart_version
    cluster_id
    region_lineage_id

を分離する。

    Chart 2027.01  cluster 3  → lineage: REGION-A
    Chart 2027.02  cluster 8  → lineage: REGION-A

であれば、ユーザーには同じ海域として見せる。

### 版更新時の処理

1. 座標系の整列：PCA等の反転・回転を補正する。

        Old latent space
                ↓
        共通anchor observations
                ↓
        Procrustes alignment
                ↓
        New latent space

2. 海域の対応付け：

    - centroid距離
    - 共通ユーザーのmembership overlap
    - Jaccard overlap
    - 所属確率分布

    から旧海域と新海域を対応付ける。最適マッチングにはHungarian algorithm等を用いる。

3. 分割・統合の記録：

        A → A        継承
        A → B + C    split
        A + B → C    merge

    を `region_lineage_events` に記録し、

    > **海域Aが二つの海域に分割されました。**

    といったChart Updateとして提示する。

---

# 58. 科学的姿勢

ISOBATHは、

「あなたの本当の人格をAIが見抜く」

というサービスにはしない。

生成AIによる人格判定も中核機能にはしない。

使用するのは、

- 回答データ
- 数値特徴量
- 統計モデル
- 古典的Machine Learning
- 可視化

である。

重要なのは「AIか否か」ではなく、

**どういう計算によって結果が得られたのか説明できること**

である。

## 58.1 学術的位置付け

ISOBATHは既存の人格診断尺度を代替することを目的としない。初期段階から臨床的・心理学的に確立された人格尺度であるとは主張しない。

本システムは、

**独自に設計した観測項目群から得られる回答分布を用いて、人格に関連する潜在構造・個人差・時系列変化を探索的に可視化する統計的観測システム**

として位置付ける。

既存人格尺度は、外的妥当性の検討や結果解釈の比較対象として利用する（§3.3）。

目的は既存理論の再現ではなく、

> 観測データからどのような人格構造が再現性をもって現れるのか

を継続的に検証し、その変化を人格海図として記録することにある。

---

# 59. 非医療・非診断

ISOBATHは、

- 医療診断
- 精神疾患診断
- 能力評価
- 採用適性判定
- 人間の優劣判定

を目的としない。

人格海図上の位置は、

**観測された回答パターンの統計的位置**

である。

---

# 60. UX上の重要原則

ISOBATHでは、

「あなたは○○型です」

という断定をなるべく避ける。

代わりに、

> 現在の海図では、この海域との類似度が最も高く観測されています。

と表現する。

また、

> 現在地は境界付近です。

> この位置の推定にはまだ不確実性があります。

> 新しい測深によって位置が変化する可能性があります。

と不確実性そのものをUIへ出す。

---

# 61. MVP

最初の完成条件を次とする。

## Account

- Supabase Auth
- Signup
- Login
- Logout
- Account deletion

## Survey

- Initial 100 questions
- Continuous 10～20 questions
- Survey Session
- Batch Answer
- Resume

## Statistics

- 候補項目群（180〜240問）・Item Set Version
- Planned Missing Design（共通アンカー＋ブロック割当、Phase 1）
- 出題記録（フェーズ・ブロック・規則バージョン・選択確率）
- UNCHARTED / Pre-Chart / Proto / Seed Chartの段階表示
- Standardization
- PCA
- Initial clustering
- GMM
- Position
- Confidence
- Drift

## Visualization

- Current Position
- Region
- Membership Probability
- Personal Journey
- Global Chart

## Infrastructure

- Cloudflare Pages
- SvelteKit
- Cloudflare Proxy
- FastAPI
- Render Free
- Supabase Auth
- Supabase PostgreSQL
- RLS

## Security

- JWT Verification
- RLS
- Rate Limit
- CSP
- CORS
- Request Validation
- DB Constraints
- Secret Management
- Logging Policy
- Data Quality Detection

---

# 62. MVP以降

ユーザー数とデータ品質が十分になった段階で、

- EFA
- CFA
- LPA
- Hierarchical Clustering
- Spectral Clustering
- Bootstrap Stability
- Multi-model Consensus
- Unknown Region Detection
- Adaptive Question Selection

を順次導入する。

最初から全アルゴリズムを同時実装することを目的にしない。

統計モデルを追加しても、

**海図という一つのプロダクト体験へ統合されること**

を優先する。

---

# 63. 最終アーキテクチャ

    ┌────────────────────────────────────────────┐
    │              USER / Browser                │
    └────────────────────┬───────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────┐
    │ Cloudflare Pages                           │
    │                                            │
    │ SvelteKit                                  │
    │ Landing / Survey / Chart / Journey         │
    │ CSP / Security Headers                     │
    └─────────────┬──────────────────────────────┘
                  │
          ┌───────┴─────────┐
          │                 │
          ▼                 ▼
    Supabase Auth       Cloudflare
       JWT              WAF / Rate Limit
          │                 │
          └──────┬──────────┘
                 │
                 ▼
    ┌────────────────────────────────────────────┐
    │ Render Free                                │
    │                                            │
    │ FastAPI                                    │
    │ JWT Verification                           │
    │ Input Validation                           │
    │ Survey Logic                               │
    │ Online Statistical Inference               │
    │ Drift / Confidence                         │
    └────────────────────┬───────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────┐
    │ Supabase PostgreSQL                        │
    │                                            │
    │ RLS                                        │
    │ FK / UNIQUE / CHECK                        │
    │ User Data                                  │
    │ Survey Data                                │
    │ Position History                           │
    └────────────────────┬───────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────┐
    │ Statistical Survey Engine                  │
    │                                            │
    │ Quality Control                            │
    │ PCA / EFA / CFA                            │
    │ k-means / GMM / LPA                        │
    │ Hierarchical / Spectral                    │
    │ Stability / Consensus                      │
    └────────────────────┬───────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────┐
    │ ISOBATH CHART                              │
    │                                            │
    │ Versioned Aggregate Map                    │
    │ Density / Contour / Regions                │
    │                                            │
    │ → Static delivery from Cloudflare          │
    └────────────────────────────────────────────┘

---

# 64. プロジェクト原則

ISOBATHの開発判断に迷った場合は、以下を優先する。

1. 人間を既存タイプへ押し込まない。
2. 人格は固定値ではなく、継続観測する。
3. 個人の移動と海図の改訂を区別する。
4. 統計的不確実性を隠さない。
5. 一つのアルゴリズムを真実としない。
6. 未知の領域を無理に既存海域へ分類しない。
7. 珍しい回答と不正・低品質回答を区別する。
8. 個人データより集約データを公開する。
9. 重い処理をユーザーリクエストから切り離す。
10. Renderから巨大データを配信しない。
11. バズしたら無制限にスケールするのではなく、まず止める。
12. 認証・認可・入力検証・DB制約を多層化する。
13. 統計モデルそのものの完全性もセキュリティ資産として扱う。
14. インフラより人格海図そのものの研究と体験へ開発資源を使う。
15. 海図は完成しない。

---

# 65. ISOBATH

人間の人格を16個の箱へ分けるのではない。

100個でもない。

何種類存在するのかさえ最初には決めない。

観測する。

測る。

人が増える。

海図が変わる。

自分も変わる。

昨日まで何もなかった場所に、新しい海域が見つかることもある。

昨日まで別々だと思われていた海域が、実は一つの巨大な地形だったと分かることもある。

その変化そのものを記録する。

**人格海図 ISOBATHは、人格を診断するサービスではない。**

**人間という未知の地形を、参加者全員で測り続けるサービスである。**
```
