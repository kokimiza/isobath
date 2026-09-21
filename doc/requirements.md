# 人格海図 ISOBATH
## 要件定義書 v1.0

| 項目 | 内容 |
|---|---|
| 対象 | ISOBATH MVP（初期公開フェーズ＝Pilot Phase 1） |
| 作成日 | 2026-09-21 |
| 関連文書 | [concept.md](concept.md)（企画・設計思想）、[observation-domains.md](observation-domains.md)（観測領域定義）、[design.md](design.md)（設計） |
| 優先順位 | 本書と concept.md の記述が矛盾する場合、本書を優先する |

要件IDの表記：

| 接頭辞 | 区分 |
|---|---|
| FR | 機能要件 |
| ST | 統計・測定要件 |
| NFR | 非機能要件 |
| SEC | セキュリティ・プライバシー要件 |
| DR | データ要件 |

要求レベル：

- **MUST**：MVPの完成条件。満たさなければリリースしない。
- **SHOULD**：MVPで実装する。やむを得ない場合は理由を記録して延期できる。
- **LATER**：MVP以降。本書では方針のみ定める。

---

# 1. 目的とスコープ

## 1.1 目的

ISOBATHは、人間をあらかじめ決められた性格タイプへ分類しない。

独自に設計した観測項目群への回答を継続的に集め、その統計的な分布から、人格に関連する潜在構造・個人差・時系列変化を探索的に可視化する。これを「人格海図」と呼ぶ。

利用者は診断される対象ではなく、海図をつくる観測点の一つとして参加する。

## 1.2 位置付け

- ISOBATHは、既存の人格診断尺度を代替するものではない。
- 臨床的・心理学的に確立された尺度であるとは主張しない。
- 医療診断、精神疾患の診断、能力評価、採用適性の判定、人間の優劣判定を目的としない。
- 生成AIによる人格判定を中核機能にしない。結果がどのような計算で得られたかを説明できることを優先する。

## 1.3 MVPのスコープ

MVPは、**planned missing design による初期調査（Pilot Phase 1）を公開サービスとして実施し、観測の蓄積に応じて海図を段階的に形成していくこと**を範囲とする。

| 区分 | MVPに含む | MVPに含まない（LATER） |
|---|---|---|
| アカウント | 登録、ログイン、ログアウト、アカウント削除 | — |
| 測深 | 初回測深、継続測深、セッション、バッチ回答、中断からの再開 | Adaptive出題（Phase 2・3） |
| 項目 | 独自の候補項目群、共通アンカー、ブロック割当、品質確認項目 | Cognitive Tasks、Behavioral Tasks |
| 統計（オフライン） | 項目分析、欠損を考慮したEFA、PCA、GMM、Bootstrap安定性 | CFA、LPA、階層的クラスタリング、Spectral、Multi-model Consensus、未踏域検出 |
| 統計（オンライン） | 既存モデルへの射影、位置、推定精度 | 再測定データが揃うまでDrift判定を行わない |
| 可視化 | 海図の段階表示、現在地、海域と所属確率（Seed以降）、航跡 | 年間航跡レポート、海域の分割・統合イベント |
| 基盤 | Cloudflare Pages、Cloudflare Proxy/WAF、Render Free、Supabase | 分析Workerの分離、Render有料プラン |

---

# 2. 用語

| 用語 | 定義 |
|---|---|
| 測深 | 質問への回答による観測 |
| 初回測深（Initial Survey） | 登録直後に行う約100問の観測 |
| 継続測深（Continuous Survey） | ログイン時などに行う10〜20問の追加観測 |
| 観測項目 | 質問 |
| 観測点 | 利用者 |
| 現在地（Position） | 海図の座標系における利用者の推定位置 |
| 推定精度（Confidence） | 現在地の推定の確からしさ。標準誤差から算出する |
| 海域（Region） | クラスタ |
| 所属確率（Membership） | 利用者が各海域に属する確率 |
| 航跡（Journey） | 現在地の時系列 |
| Drift | 測定誤差を超える、継続的な現在地の変化 |
| 海図（Chart） | 集約された密度・等値線・海域の成果物。版で管理する |
| 海図段階（Chart Stage） | UNCHARTED / PRE-CHART / PROTO / SEED / CHART（§4） |
| 未踏域（UNSURVEYED） | 既存の海図では説明しにくい観測点。海図段階とは別の概念 |
| 観測領域 | 質問を漏れなく作るための設計上の区分（D01〜D16）。因子ではない |
| 共通アンカー | 全参加者が回答する項目 |
| ブロック | アンカー以外の候補項目を分けた出題単位 |
| Item Set Version | 質問項目群の版 |
| linking items | Item Set Versionの間で維持する共通項目 |
| 共回答数 | ある項目ペアの両方に回答した人数 |

> 用語の整理：concept.md では、海図段階の最初の段階と外れ値の扱いの両方に「UNSURVEYED」が使われていた。本書では海図段階を **UNCHARTED（未測量）**、外れ値を **UNSURVEYED（未踏域）** と呼び分ける。

---

# 3. 利用者と利用シナリオ

## 3.1 利用者

| 利用者 | 説明 |
|---|---|
| 観測参加者 | 一般利用者。測深に回答し、自分の現在地・航跡・海図を閲覧する |
| 未登録訪問者 | ランディングページと公開海図を閲覧する |
| 運営者 | 項目の管理、海図の再計算と公開、Emergency Modeの操作を行う |

## 3.2 主要シナリオ

**S1. 初期測量隊として参加する（UNCHARTED〜PRE-CHART期）**

1. ランディングページで、海図がまだ形成中であることを知る。
2. 登録し、同意事項（§10.1）に同意する。
3. 初回測深（約100問）に回答する。途中で中断し、後日再開できる。
4. 完了後、自分の観測番号・参加人数・海図形成の進捗を見る。現在地はまだ表示されない。

**S2. 暫定海図の上で現在地を知る（PROTO / SEED期）**

1. 初回測深を完了する。
2. 暫定射影上の現在地と推定精度を見る。SEED以降は、海域と所属確率も見る。
3. 画面上で「暫定海図であり、大きく改訂される可能性がある」ことが明示される。

**S3. 継続して観測する**

1. ログイン時に、10〜20問の継続測深が提示される。
2. 回答すると現在地が再推定され、航跡に記録される。
3. 海図が改訂された場合、CHART UPDATE として、自分の変化（PERSONAL UPDATE）とは区別して通知される。

**S4. 退会する**

1. 設定画面からアカウントを削除する。
2. 本人のデータは削除され、次回の海図改訂から分析対象外となる（§10.3）。

---

# 4. 海図段階

海図は観測の蓄積に応じて段階的に形成される。**収集している過程そのものをサービスの成長過程として見せる。**

| 段階 | 目安N | オフライン統計処理 | 利用者への提示 |
|---|---|---|---|
| UNCHARTED（未測量） | 〜299 | 収集のみ | 観測番号、参加人数、項目単位の集計、形成の進捗 |
| PRE-CHART | 300〜 | 項目品質と回答分布の確認 | 上記に加えて、回答分布 |
| PROTO | 500〜 | 最初のEFA / PCA（アンカーとブロック内の構造が中心） | 少数次元への暫定射影上の現在地。**海域は表示しない** |
| SEED | 1,000〜 | GMM、Bootstrap安定性 | 暫定海域、所属確率 |
| （SEED改訂） | 2,000〜3,000 | 項目削減、モデル比較、再現性の検証 | SEED改訂版 |
| CHART 1.0 | 安定性の確認後 | 正式な項目群による正式な海図 | 正式な海図 |

- **FR-STG-01 (MUST)**：システムは、現在の海図段階を一つだけ持ち、全画面とAPIで参照できること。
- **FR-STG-02 (MUST)**：段階の移行は自動では行わない。運営者が再計算の結果をレビューし、公開操作によって行う。
- **FR-STG-03 (MUST)**：段階の移行は総人数だけで判断しない。項目ペアの共回答数と推定精度を判断材料に含める（ST-PMD-06）。
- **FR-STG-04 (MUST)**：PROTO段階とSEED段階の海図は「暫定海図」と表示する。「人類の海図」とは呼ばない。
- **FR-STG-05 (MUST)**：CHART 1.0 への移行条件は、次のすべてを満たすこととする。
  - Nが項目数に応じた最低必要数以上である
  - 独立サンプル（holdout）で因子構造が再現される
  - Bootstrap安定性がしきい値以上である
  - 複数のクラスタリング手法の間で合意が安定している（LATERの手法を含む）

---

# 5. 機能要件

## 5.1 アカウント

| ID | 要求 | レベル |
|---|---|---|
| FR-ACC-01 | Supabase Authによる登録、ログイン、ログアウトができること | MUST |
| FR-ACC-02 | 登録時にメールアドレスの確認を行うこと | MUST |
| FR-ACC-03 | 登録時に、利用規約・プライバシーポリシー・統計利用について同意を取得し、同意したバージョンと日時を記録すること（§10.1） | MUST |
| FR-ACC-04 | 利用者が自分でアカウントを削除できること（§10.3） | MUST |
| FR-ACC-05 | 登録できる年齢の下限を設けること（値は未決事項 Q-04） | MUST |

## 5.2 測深セッション

| ID | 要求 | レベル |
|---|---|---|
| FR-SUR-01 | 測深はSurvey Session単位で行う。セッションの種別は initial（初回）と continuous（継続）とする | MUST |
| FR-SUR-02 | セッション作成時に、サーバが出題する項目を決め、survey_session_questions に記録すること。クライアントは出題内容を指定できない | MUST |
| FR-SUR-03 | 初回測深の構成は、アンカー30問、ブロック割当60〜70問、品質確認5〜10問とし、合計約100問とする（ST-PMD-01） | MUST |
| FR-SUR-04 | 質問は1回に最大20問ずつ取得できること。初回測深も分割して取得する | MUST |
| FR-SUR-05 | 回答は5〜10問ごとにまとめて送信すること。1問ごとには送信しない | MUST |
| FR-SUR-06 | 送信済みの回答はサーバに保存し、中断したセッションを後日再開できること | MUST |
| FR-SUR-07 | 未送信の回答はブラウザに一時保存し、再読み込みしても失われないこと | SHOULD |
| FR-SUR-08 | 割り当てられていない項目への回答、同じ項目への二重回答、値域外の値は拒否すること | MUST |
| FR-SUR-09 | 項目ごとに回答時間（表示から回答まで）を記録すること | MUST |
| FR-SUR-10 | 出題順はランダムにすること。観測領域の順に並べない | MUST |
| FR-SUR-11 | セッションの完了を明示的な操作で確定すること。完了時に現在地を再推定する（PROTO以降） | MUST |
| FR-SUR-12 | 同時に開いておけるセッションは、1人1つまでとすること | MUST |

## 5.3 継続測深

| ID | 要求 | レベル |
|---|---|---|
| FR-CON-01 | 初回測深の完了後、ログイン時に10〜20問の継続測深を提示すること | MUST |
| FR-CON-02 | Pilot期間中の継続測深は、次の2種類で構成すること。<br>(a) 未回答ブロックの項目：共回答数を増やすため<br>(b) 過去に回答した項目の再出題：再検査信頼性を推定するため | MUST |
| FR-CON-03 | 再出題する項目は、前回の回答から一定期間（例：14日以上）空けて出題すること | SHOULD |
| FR-CON-04 | 継続測深への回答は任意とし、回答しなくても他の機能を使えること | MUST |
| FR-CON-05 | 継続測深の出題間隔の下限を設けること。例：前回の完了から24時間以上 | MUST |

## 5.4 現在地の表示

| ID | 要求 | レベル |
|---|---|---|
| FR-POS-01 | PROTO以降、現在地を海図の座標系上に表示すること | MUST |
| FR-POS-02 | 現在地と一緒に推定精度を表示すること。不確実性を隠さない | MUST |
| FR-POS-03 | SEED以降、最尤海域と上位の所属確率を表示すること | MUST |
| FR-POS-04 | 「あなたは○○型です」と断定しないこと。「現在の海図では、この海域との類似度が最も高く観測されています」のように表現する | MUST |
| FR-POS-05 | 海域の境界付近にいる場合や推定精度が低い場合は、その旨を表示すること | MUST |
| FR-POS-06 | UNCHARTED段階とPRE-CHART段階では、現在地の代わりに観測番号・参加人数・形成の進捗を表示すること | MUST |

## 5.5 航跡と変化

| ID | 要求 | レベル |
|---|---|---|
| FR-JNY-01 | 現在地を推定するたびにスナップショットを保存し、航跡として時系列で表示すること | MUST |
| FR-JNY-02 | 本人の変化（PERSONAL UPDATE）と海図の改訂（CHART UPDATE）を、別のイベントとして区別して表示すること | MUST |
| FR-JNY-03 | 異なる版の海図の上で推定した座標を、同じ座標系にあるかのように並べて表示しないこと。版をまたぐ場合は、再射影した座標を使うか、版の境界を明示する | MUST |
| FR-JNY-04 | Drift判定（「海流を検出しました」）は、ST-DRF の条件を満たすまで表示しないこと。それまでは航跡の表示だけとする | MUST |
| FR-JNY-05 | 年間の航跡レポート、「越境」「定着度」の表示 | LATER |

## 5.6 海図の表示

| ID | 要求 | レベル |
|---|---|---|
| FR-CHT-01 | 海図は、生成済みの版付き静的成果物（JSON / SVG）として Cloudflare Pages から配信すること。APIで動的に生成しない | MUST |
| FR-CHT-02 | 公開する海図には、他人の個別の観測点を含めないこと。含めてよいのは、密度・等値線・海域・集約統計だけとする | MUST |
| FR-CHT-03 | 自分の現在地は、クライアント上で海図に重ねて表示すること | MUST |
| FR-CHT-04 | 人口が極端に少ない領域は、集約するか表示しないこと（しきい値 k は Q-06） | MUST |
| FR-CHT-05 | 未登録の訪問者も公開海図と段階情報を閲覧できること | MUST |
| FR-CHT-06 | 海図の版と、その版の観測数を表示すること | MUST |

## 5.7 画面

| パス | 画面 | 認証 |
|---|---|---|
| `/` | ランディング、現在の海図段階、参加人数 | 不要 |
| `/survey/initial` | 初回測深 | 必要 |
| `/survey` | 継続測深 | 必要 |
| `/chart` | 人格海図 | 不要（ログイン中は現在地を重ねる） |
| `/journey` | 航跡 | 必要 |
| `/profile` | 現在地、推定精度、海域 | 必要 |
| `/settings` | アカウント、同意の状態、データ削除 | 必要 |
| `/status` | 障害・混雑案内 | 不要 |

- **FR-UI-01 (MUST)**：「深い／浅い」、座標、海域を、優劣や正常・異常を示すものとして表現しないこと。
- **FR-UI-02 (MUST)**：APIが停止しているときや混雑しているときも、ランディング・海図・障害案内は表示できること。表現は世界観に沿わせる（例：「測量船へのアクセスが集中しています」）。
- **FR-UI-03 (MUST)**：Cold Start による待ち時間を表示すること（例：「測量船を起動しています……」）。
- **FR-UI-04 (MUST)**：UIは日本語を基本とする。英語UIに対応する場合も、MVPの観測項目は日本語だけとする（ST-ITM-07）。

## 5.8 運営機能

| ID | 要求 | レベル |
|---|---|---|
| FR-OPS-01 | 項目マスタ（版、区分、アンカー、ブロック）を、スクリプトまたはSQLで投入・更新できること。管理画面は作らない | MUST |
| FR-OPS-02 | 再計算はローカルまたはCIのPythonスクリプトで実行し、成果物として海図とモデルを出力すること | MUST |
| FR-OPS-03 | 海図とモデルの公開、段階の移行は、成果物をデプロイする操作で行うこと | MUST |
| FR-OPS-04 | Emergency Modeを設定値で切り替えられること（NFR-AVL-03） | MUST |

---

# 6. 統計・測定要件

## 6.1 観測項目

| ID | 要求 | レベル |
|---|---|---|
| ST-ITM-01 | 観測項目は、既存尺度を直接利用しない独自の項目群とすること | MUST |
| ST-ITM-02 | 候補項目は、observation-domains.md の16観測領域に基づき、220〜240問を作成すること | MUST |
| ST-ITM-03 | 観測領域は項目作成のための区分であり、分析には使わないこと。分析は項目単位で行う | MUST |
| ST-ITM-04 | 項目の作成は、observation-domains.md §5 の共通規則に従うこと。<br>・5件法<br>・1項目で1つの内容<br>・各領域の1/3〜1/2を逆転項目にする<br>・臨床症状、能力、政治・宗教、違法行為を扱わない | MUST |
| ST-ITM-05 | 各項目は、item_id、domain、facet、keyed、anchor、item_type、text_ja、item_set_version を持つこと | MUST |
| ST-ITM-06 | 項目群を版で管理すること。版を改訂するときは linking items を維持すること | MUST |
| ST-ITM-07 | MVPの項目は日本語だけとする。多言語化は、測定不変性を検証してから行う | MUST |
| ST-ITM-08 | 最終的な項目数は統計的品質で決める。数合わせのために項目を足さない（「約100問」） | MUST |
| ST-ITM-09 | 品質確認項目は人格項目とは別に管理し、人格モデルの分析変数に含めないこと | MUST |

## 6.2 Planned Missing Design

| ID | 要求 | レベル |
|---|---|---|
| ST-PMD-01 | 1人あたりの構成は、共通アンカー30問、ブロック割当60〜70問、品質確認5〜10問とすること | MUST |
| ST-PMD-02 | アンカーは各観測領域に均等に割り当てること（14領域に2問、D11とD13に1問） | MUST |
| ST-PMD-03 | ブロックは観測領域ごとに作らず、各ブロックに全領域の項目を層化して配置すること | MUST |
| ST-PMD-04 | ブロックの組み合わせは、balanced incomplete block design に近い形で均等に割り当てること（Phase 1） | MUST |
| ST-PMD-05 | セッションごとに、出題フェーズ、割り当てたブロックと項目、出題規則の版、選択確率を記録すること | MUST |
| ST-PMD-06 | 項目ペアごとの共回答数を集計し、再計算のたびに報告すること | MUST |
| ST-PMD-07 | 推定精度の低い項目ペアを優先するPhase 2、因子候補の周辺を重点的に出題するPhase 3 | LATER |

共回答数の目安（アンカー以外200問＝20問×10ブロック、1人3ブロック）：

| 項目ペア | 共回答率 | N=1,000のとき |
|---|---|---|
| アンカー × 全項目 | 3/10以上 | 300以上 |
| 同じブロック内 | 3/10 | 約300 |
| 異なるブロック間 | 1/15 | 約67 |

## 6.3 欠損データ

| ID | 要求 | レベル |
|---|---|---|
| ST-MIS-01 | 探索の初期段階で相関行列を確認する用途に限り、pairwise deletion を使ってよい | MUST |
| ST-MIS-02 | 正式なEFA、PCA、モデル推定では、FIML、多重代入法、またはEMで推定した共分散を使うこと。pairwise deletion だけで正式な分析をしない | MUST |
| ST-MIS-03 | 継続測深に戻ってくる利用者は、特性に偏りがある可能性がある。回答の欠損が設計によるもの（MCAR）か、離脱によるものかを区別して記録すること | SHOULD |

## 6.4 データ品質

| ID | 要求 | レベル |
|---|---|---|
| ST-QLT-01 | 次の兆候を検出し、quality_flags に記録すること。<br>・極端に短い回答時間<br>・全問同じ回答（ストレートライン）<br>・注意確認項目への誤答<br>・同じ意味の再質問での不一致<br>・矛盾するペアへの同時肯定 | MUST |
| ST-QLT-02 | 品質フラグから、セッションごとに回答信頼度スコアを算出すること | MUST |
| ST-QLT-03 | 低品質の回答は削除しない。Raw Observation → Quality Flag → Validated Dataset のように、分析用データセットから除外する | MUST |
| ST-QLT-04 | 低品質の回答と「珍しい人格」を区別すること。品質検査を先に行う | MUST |
| ST-QLT-05 | 登録の急増や分布の急変を検知できる指標を出すこと（Sybil攻撃・Data Poisoningへの対策） | SHOULD |

## 6.5 海図の生成（オフライン）

| ID | 要求 | レベル |
|---|---|---|
| ST-CHT-01 | 再計算はHTTPリクエストから実行しないこと | MUST |
| ST-CHT-02 | パイプラインは次の順で行う。<br>品質フィルタ → 標準化 → 項目分析 → EFA（欠損を考慮）→ PCA → GMM → Bootstrap安定性 → 密度・等値線の生成 | MUST |
| ST-CHT-03 | 比較尺度の回答（ST-EXT-01）は、海図の学習データに含めないこと | MUST |
| ST-CHT-04 | アカウント削除の tombstone があるユーザーを学習データから除外すること | MUST |
| ST-CHT-05 | 各版について、使用したデータの件数、Item Set Version、パイプラインのコードの版、乱数シードを metadata に記録し、再現できるようにすること | MUST |
| ST-CHT-06 | 版を改訂するときは、共通の観測点を使って Procrustes 法で座標系を整列し、PCA軸の反転や回転を補正すること | MUST |
| ST-CHT-07 | 海域には、版をまたいで同じ海域を指す region_lineage_id を付けること。対応付けは、重心の距離、所属の重なり、Hungarian法で行う | SHOULD |
| ST-CHT-08 | 海域の分割・統合を lineage のイベントとして記録すること | LATER |
| ST-CHT-09 | CFA、LPA、階層的クラスタリング、Spectral、Multi-model Consensus、未踏域の検出 | LATER |

## 6.6 現在地の推定（オンライン）

| ID | 要求 | レベル |
|---|---|---|
| ST-POS-01 | 現在地は、デプロイ済みのモデルへの射影だけで算出すること。オンラインで再学習しない | MUST |
| ST-POS-02 | 一部の項目にしか回答していない利用者でも、現在地を推定できること。欠けている項目は、モデルの共分散に基づく条件付き期待値などで扱う | MUST |
| ST-POS-03 | 現在地と一緒に、推定の標準誤差（SE）を算出すること。推定精度はSEから導く | MUST |
| ST-POS-04 | 現在地の推定には、各項目の最新の回答を使うこと | MUST |
| ST-POS-05 | 所属確率は、GMMの事後確率として算出すること（SEED以降） | MUST |

## 6.7 Drift

| ID | 要求 | レベル |
|---|---|---|
| ST-DRF-01 | 座標の単純な距離でDriftと判定しないこと | MUST |
| ST-DRF-02 | 再検査信頼性 r は、ISOBATHの再測定データ（FR-CON-02 (b)）から推定すること。文献値は使わない | MUST |
| ST-DRF-03 | r が推定できるまで、Drift判定を行わないこと | MUST |
| ST-DRF-04 | Drift判定の基準は Reliable Change（Sdiff = SD × √(2(1−r))）とし、測定誤差を超える同じ方向の変化が3セッション続いたときに初めてDriftと認定すること | SHOULD |
| ST-DRF-05 | 誤差共分散を考慮した多次元の判定（D² = Δ'ΣΔ⁻¹Δ） | LATER |
| ST-DRF-06 | 等化していない Item Set Version をまたいで、Drift判定をしないこと | MUST |

## 6.8 外的比較尺度

| ID | 要求 | レベル |
|---|---|---|
| ST-EXT-01 | Pilot期間に限り、public domain の既存の短尺尺度を、比較専用として一部の参加者に任意で出題できること | SHOULD |
| ST-EXT-02 | 比較尺度は、独自の軸の解釈（外的妥当性の検討）だけに使うこと。利用者の画面に既存の類型名を表示しない | MUST |
| ST-EXT-03 | 第三者による翻訳は、利用条件を確認してから使うこと。原則として自前で翻訳する | MUST |

---

# 7. システム構成

    Browser
       │
       ▼
    Cloudflare Pages ── SvelteKit（静的ビルド）、海図の静的成果物
       │
       ├──► Supabase Auth ── JWT
       │
       ▼
    Cloudflare（DNS / Proxy / WAF / Rate Limit）
       │  api.isobath.jocarium.productions
       ▼
    Render Free ── FastAPI（JWTの検証、測深、射影）
       │  User JWT
       ▼
    Supabase PostgreSQL（RLS / 制約）

    Offline（ローカル / CI）
    Supabase ─(Server Secret)─► 統計パイプライン ─► モデル・海図の成果物 ─► デプロイ

| コンポーネント | 責務 |
|---|---|
| SvelteKit（adapter-static） | UI、可視化、未送信回答の一時保存 |
| Cloudflare Pages | 静的コンテンツの配信、海図の成果物の配信、セキュリティヘッダ |
| Cloudflare | API入口の防御、Rate Limit |
| FastAPI | 測深ロジック、入力検証、射影、推定精度の算出 |
| Supabase Auth | 認証 |
| Supabase PostgreSQL | 永続データ、RLS、制約 |
| 統計パイプライン（Python） | 海図の再計算、モデルの成果物の生成 |

- フロントエンド：`isobath.jocarium.productions`
- API：`api.isobath.jocarium.productions`

---

# 8. API要件

## 8.1 共通

| ID | 要求 | レベル |
|---|---|---|
| FR-API-01 | 全エンドポイントに `/v1/` を付けること | MUST |
| FR-API-02 | ユーザーIDはJWTの `sub` から決めること。クライアントに user_id を指定させない | MUST |
| FR-API-03 | 利用者本人のリソースは `/v1/me/...` の下に置くこと | MUST |
| FR-API-04 | 全件取得を禁止すること。一覧はカーソルでページングする | MUST |
| FR-API-05 | FastAPIはHTML・CSS・JavaScript・画像を配信しないこと | MUST |
| FR-API-06 | 全APIのレスポンスに、現在の海図段階と海図の版を参照できる手段を用意すること（`/v1/meta`） | MUST |

## 8.2 エンドポイント

| メソッド | パス | 概要 | サイズの目標 |
|---|---|---|---|
| GET | `/healthz` | `{"status":"ok"}`。DBや統計処理を実行しない | — |
| POST | `/v1/me/consents` | 同意の記録（SEC-CON-01） | — |
| GET | `/v1/meta` | サービスの状態、海図段階、海図の版、参加人数、Emergency Level | < 1 KB |
| POST | `/v1/me/surveys` | セッションの作成（種別 initial / continuous） | < 2 KB |
| GET | `/v1/me/surveys/current` | 進行中のセッションと、次の最大20問 | < 15 KB |
| POST | `/v1/me/surveys/{id}/answers` | バッチ回答（最大20件）。正常時は 204 | — |
| POST | `/v1/me/surveys/{id}/complete` | セッションの完了、現在地の再推定 | < 2 KB |
| GET | `/v1/me/position` | 現在地、推定精度、海域、所属確率、段階 | < 2 KB |
| GET | `/v1/me/history?cursor=&limit=` | 航跡。limitの上限は50 | < 10 KB / ページ |
| DELETE | `/v1/me` | アカウントの削除 | — |

回答リクエストの例：

    POST /v1/me/surveys/{id}/answers
    {
      "answers": [
        {"question_id": 14, "value": 4, "response_ms": 3120},
        {"question_id": 27, "value": 2, "response_ms": 2480}
      ]
    }

現在地レスポンスの例（SEED段階）：

    {
      "chart": {"version": "2027.03", "stage": "SEED"},
      "position": [0.31, -0.82],
      "se": [0.12, 0.15],
      "confidence": 0.81,
      "regions": [
        {"lineage_id": "REGION-A", "membership": 0.62},
        {"lineage_id": "REGION-C", "membership": 0.31}
      ],
      "near_boundary": true
    }

PROTO段階では `regions` を返さない。UNCHARTED段階とPRE-CHART段階では、`position` の代わりに `observer_number` を返す。

## 8.3 海図の成果物

    /charts/{version}/map.json
    /charts/{version}/contours.svg
    /charts/current.json      （短時間だけキャッシュする。現在の版と段階を指す）

- 版付きのパスは immutable として扱い、長期間キャッシュする。
- 利用者の個別座標を含めない。

---

# 9. 非機能要件

## 9.1 性能とリソース

| ID | 要求 | レベル |
|---|---|---|
| NFR-PRF-01 | APIレスポンスのサイズは、§8.2 の目標以内とすること | MUST |
| NFR-PRF-02 | FastAPIが常駐して持つモデルは、推論に必要なパラメータだけとすること（スケーラ、PCA成分、因子負荷、GMMパラメータ、海域のメタデータ）。数MB〜数十MBを目標にする | MUST |
| NFR-PRF-03 | FastAPIのプロセス内に、学習データや全ユーザーの座標を保持しないこと | MUST |
| NFR-PRF-04 | モデルは起動時に一度だけ読み込むこと。リクエストのたびにDBから取得しない | MUST |
| NFR-PRF-05 | Cold Startからの復帰を除き、position API の p95 レイテンシを 500ms 以内とすること | SHOULD |
| NFR-PRF-06 | Render Free（0.1 CPU / 512MB RAM）で、メモリ不足にならずに動くこと | MUST |

## 9.2 可用性と費用

| ID | 要求 | レベル |
|---|---|---|
| NFR-AVL-01 | **費用の上限を可用性より優先する。** オートスケールを使わず、混雑したら 429 / 503 で止まることを許容する | MUST |
| NFR-AVL-02 | Render Free のスリープ（15分間アクセスがないと停止し、復帰に約1分かかる）を、仕様として許容する | MUST |
| NFR-AVL-03 | Emergency Mode を、設定値 `SIGNUP_ENABLED`、`SURVEY_WRITE_ENABLED`、`READ_ONLY_MODE` で段階的に切り替えられること。<br>NORMAL → L1: Rate Limit強化 → L2: 新規登録停止 → L3: 回答受付停止 → L4: API停止 | MUST |
| NFR-AVL-04 | APIが停止していても、Cloudflare Pages の静的な画面は表示できること | MUST |
| NFR-AVL-05 | 有料プランへ移行するかは、利用者数ではなく、持続的な需要（継続的な5xx、p95の悪化、毎日の安定した利用）で判断する | — |

## 9.3 リソースの上限

| ID | 要求 | レベル |
|---|---|---|
| NFR-LIM-01 | リクエストボディの最大サイズ、配列の最大件数（answers は最大20件）、文字列の最大長、ページサイズの上限を設定すること | MUST |
| NFR-LIM-02 | DBクエリとAPIにタイムアウトを設定すること | MUST |

## 9.4 Rate Limit

| API | 方針 |
|---|---|
| GET position / meta | 比較的緩い。meta はキャッシュを優先する |
| GET history / surveys/current | 中程度 |
| POST answers | 厳格 |
| POST surveys（作成） | 厳格 |
| Signup | 非常に厳格。Supabase Auth が直接受け付けるので、Auth 側の Rate Limit と CAPTCHA で担保する |

- **NFR-RL-01 (MUST)**：認証後は、User ID、IPアドレス、エンドポイント、時間窓を組み合わせて制限すること。超過したときは 429 を返す。

## 9.5 監視

| ID | 要求 | レベル |
|---|---|---|
| NFR-OBS-01 | 次の値を監視すること。<br>・リクエスト数/分、p50・p95 レイテンシ、429・4xx・5xx の件数<br>・Render の CPU・メモリ<br>・Supabase の DBサイズ・接続数 | MUST |
| NFR-OBS-02 | ISOBATH固有の指標を監視すること。<br>・新規登録数、測深の完了率、回答数/分、品質フラグの発生率<br>・共回答数の分布、海図段階 | MUST |

## 9.6 運用と開発

| ID | 要求 | レベル |
|---|---|---|
| NFR-DEV-01 | フロントエンドは pnpm-lock.yaml、バックエンドは uv.lock で依存関係を固定すること | MUST |
| NFR-DEV-02 | 依存関係の更新、脆弱性スキャン、Secretスキャンを定期的に行うこと | SHOULD |
| NFR-DEV-03 | 本番ブランチへの merge を、本番への反映の単位とすること | MUST |
| NFR-DEV-04 | 本番環境と開発環境の Credential を分けること | MUST |

---

# 10. セキュリティ・プライバシー要件

## 10.1 同意

| ID | 要求 | レベル |
|---|---|---|
| SEC-CON-01 | 登録時に、次の3点について同意を取得すること。<br>・利用規約<br>・プライバシーポリシー<br>・回答を統計分析と海図の生成に使うこと | MUST |
| SEC-CON-02 | 同意した文書の版と日時を記録すること。文書が改訂されたときは、再同意を求められること | MUST |
| SEC-CON-03 | 非医療・非診断であることを、登録前と結果画面に明示すること | MUST |

## 10.2 認証・認可

| ID | 要求 | レベル |
|---|---|---|
| SEC-AUTH-01 | 認証は Supabase Auth に任せること。FastAPIでパスワードを扱わない | MUST |
| SEC-AUTH-02 | FastAPIはJWTの署名、`exp`、`iss`、`aud`、`sub`、許可した署名アルゴリズムを検証すること | MUST |
| SEC-AUTH-03 | 通常のAPIは、検証したものと同じ User JWT の権限でDBにアクセスし、RLSを有効にすること。方法は、PostgREST に User JWT を付けるか、直接接続してトランザクション内で `SET LOCAL ROLE authenticated` と `request.jwt.claims` を設定するかのどちらかとする | MUST |
| SEC-AUTH-04 | 回答を保存するときは、「割り当ての検証」と「INSERT」を一つのトランザクションで行うこと | MUST |
| SEC-AUTH-05 | service_role 相当の Credential は、オフラインの統計処理と運営処理だけに使うこと。ブラウザと通常のAPIには渡さない | MUST |
| SEC-AUTH-06 | ブラウザに渡すのは、Supabase の Publishable Key だけとすること | MUST |

## 10.3 アカウント削除

| ID | 要求 | レベル |
|---|---|---|
| SEC-DEL-01 | 削除は次の順で行うこと。<br>認証情報 → 回答の生データ → 現在地と航跡 → 分析対象外を示す tombstone の作成 | MUST |
| SEC-DEL-02 | 削除したユーザーの生データは保持しないこと | MUST |
| SEC-DEL-03 | 公開済みの海図は、さかのぼって作り直さないこと。次の改訂から、そのユーザーを除外する | MUST |
| SEC-DEL-04 | tombstone には、除外に必要な仮名IDだけを持たせ、個人を特定できる情報を持たせないこと | MUST |
| SEC-DEL-05 | DBのバックアップ（PITRなど）に削除済みのデータが残る期間を、プライバシーポリシーに明記すること | MUST |

## 10.4 データの分離

| ID | 要求 | レベル |
|---|---|---|
| SEC-PRV-01 | 統計分析用のデータセットには、仮名IDだけを使うこと。メールアドレス、OAuthの情報、氏名を含めない | MUST |
| SEC-PRV-02 | 回答データは、プライバシー性の高い情報として扱うこと | MUST |
| SEC-PRV-03 | モデルや公開成果物から、個人のデータを復元できない設計にすること | MUST |

## 10.5 入口とOriginの防御

| ID | 要求 | レベル |
|---|---|---|
| SEC-NET-01 | APIは Cloudflare Proxy を経由させ、WAF・Bot対策・Rate Limit を有効にすること | MUST |
| SEC-NET-02 | Render の `onrender.com` サブドメインを無効にし、Cloudflare を迂回して Origin に届く経路をなくすこと | MUST |
| SEC-NET-03 | CORS で許可するのは、本番の Origin（`https://isobath.jocarium.productions` と `www`）と、開発用の `http://localhost:5173` だけとすること。`*` を使わない。CORS を認可の代わりにしない | MUST |
| SEC-NET-04 | 登録時に、CAPTCHA または同等の Bot 対策を行うこと | SHOULD |

## 10.6 フロントエンド

| ID | 要求 | レベル |
|---|---|---|
| SEC-FE-01 | Cloudflare Pages で次のヘッダを設定すること。<br>CSP、`X-Content-Type-Options: nosniff`、Referrer-Policy、Permissions-Policy、HSTS | MUST |
| SEC-FE-02 | XSS を主要な脅威として扱うこと。外部の JavaScript SDK、広告、Analytics を安易に追加しない | MUST |

## 10.7 キャッシュ

| 対象 | Cache-Control |
|---|---|
| `/v1/me/*` | `private, no-store` |
| `/v1/meta`、`/charts/current.json` | 短時間の public キャッシュ |
| `/charts/{version}/*` | immutable、長期間 |

## 10.8 ログ

| ID | 要求 | レベル |
|---|---|---|
| SEC-LOG-01 | ログに次を記録しないこと。<br>JWT、Refresh Token、Authorization ヘッダ、パスワード、Secret、回答の内容、メールアドレス | MUST |
| SEC-LOG-02 | ログに記録するのは、request_id、user_hash、endpoint、status、latency_ms など、運用に必要な項目に限ること | MUST |

## 10.9 Secret

| ID | 要求 | レベル |
|---|---|---|
| SEC-SCR-01 | Secret を Git に保存しないこと。`.env` と `*.secret` は追跡対象から外す | MUST |
| SEC-SCR-02 | FastAPI の Secret は Render の Environment Variables で管理すること | MUST |

---

# 11. データ要件

## 11.1 テーブル

| テーブル | 内容 | RLS |
|---|---|---|
| profiles | アプリ内のプロフィール。仮名ID、観測番号 | 本人のみ |
| consents | 同意した文書、版、日時 | 本人のみ |
| questions | 項目マスタ（ST-ITM-05）。区分：candidate / formal / comparison / quality | 公開読み取り |
| item_blocks | ブロックの定義と所属する項目 | 公開読み取り |
| survey_sessions | セッション（種別、状態、Item Set Version、出題規則の版、フェーズ） | 本人のみ |
| survey_session_questions | 割り当てた項目（ブロック、選択確率、出題順） | 本人のみ |
| answers | 回答（値、回答時間、回答日時） | 本人のみ |
| quality_flags | 品質フラグと回答信頼度 | 本人には見せない |
| position_snapshots | 現在地、SE、海図の版、推定日時 | 本人のみ |
| region_memberships | 所属確率（スナップショット単位） | 本人のみ |
| chart_versions | 海図の版、段階、観測数、Item Set Version、公開日時 | 公開読み取り |
| regions | 海域（chart_version、cluster_id、region_lineage_id） | 公開読み取り |
| region_lineage_events | 海域の継承・分割・統合（LATER） | 公開読み取り |
| deletion_tombstones | 削除したユーザーの仮名IDと削除日時 | サーバのみ |
| audit_events | 重要な操作の記録 | サーバのみ |

## 11.2 制約

| ID | 要求 | レベル |
|---|---|---|
| DR-01 | `answers.value` に `CHECK (value BETWEEN 1 AND 5)` を設定すること | MUST |
| DR-02 | answers に、survey_session_id と question_id の外部キー、`UNIQUE(survey_session_id, question_id)` を設定すること | MUST |
| DR-03 | 利用者が所有するテーブルでは、`user_id` を `NOT NULL` にすること | MUST |
| DR-04 | answers から survey_session_questions への参照、またはトリガで、割り当てていない項目への回答をDBの側でも拒否すること | MUST |
| DR-05 | RLS のポリシーは、SELECT・INSERT・UPDATE・DELETE ごとに明示的に定義すること | MUST |
| DR-06 | 同時に開いておけるセッションを1人1つにする制約を設けること（部分一意インデックスなど） | MUST |

MVPでは `chart_versions`、`regions`、`item_blocks` をテーブル化せず、成果物の metadata と `questions.block_no` で代替する（design.md D-10）。

入力検証は、Svelte → Pydantic → 業務ロジックの検証 → PostgreSQL の制約 → RLS の多層で行う。

## 11.3 モデルの成果物

    model/
      chart-{version}/
        scaler
        pca
        factor-model
        gmm            （SEED以降）
        regions        （SEED以降）
        metadata       （ST-CHT-05）

---

# 12. MVPの受け入れ基準

1. 新規利用者が登録と同意を済ませ、初回測深の約100問を中断・再開しながら完了できる。
2. 出題が planned missing design（アンカー30問、層化したブロック、品質確認項目）に従い、出題の記録がセッションごとに残る。
3. 割り当てられていない項目への回答、二重回答、値域外の値が、API と DB の両方で拒否される。
4. 他の利用者のデータを、API からも、FastAPI の実装を迂回したDBクエリからも取得できない（RLS の検証テスト）。
5. オフラインのパイプラインが、Supabase のデータから、品質フィルタと欠損を考慮した分析を経て、版付きのモデルと海図を再現可能に出力する。
6. 海図段階（UNCHARTED → PRE-CHART → PROTO → SEED）の切り替えが、成果物のデプロイだけで画面と API に反映される。
7. PROTO以降は、現在地と推定精度が表示される。SEED以降は、海域と所属確率が表示される。どの段階でも断定的な表現を使わない。
8. アカウントを削除すると、本人のデータが消え、tombstone によって次の再計算から除外される。
9. Emergency Mode の各レベルで、期待したとおりに機能が止まる。API が止まっても、静的な画面は表示される。
10. `onrender.com` への直接アクセスが 404 になる。

---

# 13. 未決事項

| ID | 事項 | 決定が必要な時期 |
|---|---|---|
| Q-01 | 候補項目の作成と確定（まず D01 で試作し、作成規則を検証してから全領域に広げる） | Pilot開始前 |
| Q-02 | Pilot で使う比較尺度の選定と、その翻訳 | Pilot開始前 |
| Q-03 | 年齢や性別などの属性を収集するか。測定不変性の検証には有用だが、プライバシーの負担が増える | Pilot開始前 |
| Q-04 | 登録できる年齢の下限 | 公開前 |
| Q-05 | PROTO / SEED / CHART 1.0 の定量的なしきい値（共回答数、Bootstrap安定性、SE） | PROTO移行前 |
| Q-06 | 公開する海図で、集約または非表示にする人口のしきい値 k | PROTO移行前 |
| Q-07 | 版をまたぐ航跡の見せ方：旧座標を新しい版に再射影するか、版の境界で区切るか | 最初の海図改訂前 |
| Q-08 | 自己評価の水準（高い／低い）を観測するか。現在の D09 は変動だけを扱っている | 項目作成時 |
| Q-09 | 継続測深で再出題する割合と間隔（FR-CON-02・FR-CON-03） | Pilot開始前 |
| Q-10 | バックアップの保持期間と、プライバシーポリシーの文言 | 公開前 |
| ~~Q-11~~ | 決定済み：直接接続して SET LOCAL する方式。アプリのテーブルは PostgREST に公開しない（design.md D-1、D-2） | — |
