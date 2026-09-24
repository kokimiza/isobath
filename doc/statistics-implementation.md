# Python統計実装・検証手順

統計的な正本は [statistics.md](statistics.md)。旧conceptのEFA/PCA/GMM処理や人数段階は実装対象にしない。数理核、保存形式、サービス接続ごとに失敗するテストを追加してから実装した。

## 環境と実行

Python 3.12以上、uvのロックファイルを使用する。APIは従来の実行時依存だけ、日次処理は`inference`グループ、研究処理は`pipeline`グループを追加する。SciPy 1.18、ArviZ 1.3のAPIを確認した。配列は`allow_pickle=False`で読み、成果物の形状・数値・成分対応・確率和を検証する。

```powershell
cd app
uv sync --frozen --group pipeline
uv run --no-sync pytest
uv run --no-sync ruff check .
uv run --no-sync python -m pipeline.run --help
```

PostgreSQL統合テストは、隔離したテストサーバの接続文字列を`ISOBATH_TEST_PG`に設定して実行する。テスト専用の`isobath_test`データベースを作り直すため、運用サーバを指定しない。

## 推定と成果物

### 自動運用（2026-09-24）

`pnpm batch` / GitHub Actions は `python -m isobath.scheduled` を実行する。
接続は既存の `NIGHTLY_DATABASE_URL` のみ。`DB_PULL_DATABASE_URL`、追加のSecret、
ローカルDBのresetや本番回答のseedは不要。

- 最初の成功バッチで質問設計の事前分布から `PRIOR` モデルを生成する。項目版0.2の
  各領域で、正方向の共通項目の最小IDを符号アンカーとする。固定seedの32ドローを
  保存する。架空の回答者や観測済みの海域を作らず、画面には「暫定海図（未校正）」と表示する。
- 毎晩、締め前に完了した回答を固定モデルへ配置する。PRIORでは各外側ドローにつき
  2チェイン・ウォームアップ32・保存32の軽量な近似を使う。集団校正済みの位置や、
  本評価を通過した精度とは扱わない。
- 初回から14日後、その後は前回試行から14日経過した最初のバッチで `pipeline.autofit`
  を起動する。n=1でも人数による分岐はしない。既存の4チェイン診断、拡張再推定、
  個人信用領域の精度判定をすべて通った場合だけ採用する。
- 再推定は10分で打ち切る。失敗・不合格・時間切れなら現行モデルを維持し、その日の
  位置更新を続ける。新モデルによる位置計算が失敗しても、トランザクションを戻して現行版で再試行する。
- 採用モデルと非公開の個人別結果は `batch_runs.model_bundle` にまとめ、日次結果と
  同じトランザクションで保存する。次回はDBから復元する。個票やモデルをCIの公開artifact/cacheへ出さない。
  新しいbundleは採用時だけ保存する。再実行は同じ締めの成功を確認してスキップする。
- 再推定は `app.questions`、`app.answers`、`app.survey_sessions` と既存の
  `app.batch_research_key` を使う。研究同意版2の有効な人だけが対象。削除した人は
  回答・セッションのカスケード削除で除外される。年齢・性別の副次研究回帰と品質スコア抽出は行わない。
  それらは従来の研究用パイプラインで扱う。

事前に `20260924000000_scheduled_models.sql` を適用する。バッチロールの権限は追加しない。
APIロールは従来の列だけにSELECTを限定し、非公開bundleへのアクセスを防ぐ。
`app/models/CURRENT` は手動研究CLI用のままで、自動運用の採用版はDBの成功バッチが正本。
質問票の版を変える場合は自動的に旧尺度を流用せずエラーにするため、新版の初期化手順を別途用意する。

### 手動の研究用推定

```powershell
uv run --group pipeline python -m pipeline.run fit --version 2026.10 --item-set-version 0.2 --cutoff 2026-10-01T01:00:00+09:00 --sign-anchors <各領域1個の項目ID、合計16個>
```

`PIPELINE_DATABASE_URL`には`analysis`ビューだけを読める研究ロールを設定する。符号アンカーは明示指定し、共通出題アンカー全件を符号制約にしない。`--input`による非公開JSONを使う場合は`responses`、`questions`、最新同意の`participants`、`tombstones`が必要で、回答日時・完了日時はタイムゾーン付きISO形式とする。DB・JSONとも項目版、同意、削除、締め、最新回答、人格項目への限定を適用する。

4チェインの診断、級数上限を広げた再推定、個人信用領域の精度を通過してから`models/chart-{version}`を作る。不合格は終了コード2で、診断結果は非公開の作業先に残す。`CURRENT`は変更しない。`--warmup`、`--draws`、`--saved-draws`で計算を増やす。既存の版は上書きできない。前版とのID継承には`--previous`を指定する。

`--private-root`（既定`.private-statistics`）には分割、2次元ドロー、仮名ID、学習者の同時事後を保存する。公開成果物やGitへ含めない。移送・保管には研究データ管理規程の非公開保管先を使う。日次処理側で同じ非公開ディレクトリを`PRIVATE_STATISTICS_DIR`に指定する。モデルだけを配備し、この受渡しを省いた場合は日次処理を失敗させる。GitHub Actionsで運用する場合もこの非公開受渡しを別途構成する必要があり、リポジトリへの個人ドロー同梱では代替しない。

DBの`20260923000000_statistics_v3.sql`は、信用領域・未対応確率・推論種別・2次元ドロー用の非公開列と、バッチ専用の限定的な研究キー照合関数を追加する。通常API・利用者ロールへ照合関数を公開しない。学習時と回答が一致する同意者には保存した同時事後、それ以外にはcut推論を使う。項目版が違う座標を密度図へ混在させない。

## 仕様とテスト

2026-09-23追加：`20260923010000_research_demographics.sql` により出生年月・性別を専用の非公開テーブルへ保存する。プライバシー・研究説明書は版2。旧版の研究同意は自動更新せず、再同意まで研究抽出と日次の密度集計から除外する。既存アカウントに属性は推測・補完しない。

登録は `/auth/signup`（事前情報・同意）→ `/auth/register`（Google優先／メール代替）→ 共通コールバックで進む。属性をAuthへ送らず、24時間有効のタブ内ドラフトを認証後の `POST /v1/me/registration` で保存する。このAPIは同意イベントと属性を同じDBトランザクションで確定し、未完了登録を解除する。未完了状態では測深・通常の同意追加を許可しない。ドラフト消失時は `/consent` で再入力できる。ローカルDBマイグレーション、API、Web、同意文書は同時に更新する。実環境へのマイグレーション適用・デプロイは別工程である。

`test_signup_auth.py` は使い捨てのGoTrue/DBを `ISOBATH_AUTH_TEST_URL` / `ISOBATH_AUTH_TEST_PG` で指定した場合のみ実行する。通常のSupabaseアカウントや本番DBを指定しない。`test_db_rls.py` は従来の `ISOBATH_TEST_PG` を使う。Google本体への自動ログインは行わず、Playwrightで認可リダイレクト・PKCEコールバック・ドラフト消去を検証する。

`fit` は `analysis.research_demographics` を同じ読み取りトランザクションで取得し、`--cutoff` を日本時間へ変換した先月末を基準に年齢を導出する。JSON入力では `demographics`（`pseudo_id,birth_year,birth_month,gender`）と**現在の版2同意者** `demographic_participants` を明示する。解析直前の同意・削除台帳との照合は従来どおり必須で、古い同意スナップショットを再利用しない。

研究専用のcut回帰は `pipeline/demographics.py`。`fit` が非公開の `chart-<version>/demographic-regression.json` と `demographic-coefficients.npy` に平均・区間・診断と係数ドローを保存する。公開モデルに年齢・性別・係数を同梱しない。完全ケースが0人なら推定しない。推定値は探索的な関連であり、因果効果や一般人口への推論ではない。通常の海図・個人推定へはフィードバックしない。

| statistics.md | 実装 | テスト |
|---|---|---|
| §12.1 | `demographics.py`、`data.py`、`sampler.py` | `test_demographics.py`：月境界・共役事後・欠測・上流不変性。`test_db_rls.py`：必須入力・権限・同意版・撤回・削除 |
| §2.2、§4.2.1 | `pipeline/mfm.py` | `test_statistics_math.py`：全分割の確率和、既知の同群確率、上限拡張、K復元・未観測質量 |
| §3、§4.2 | `niw.py`、`partitions.py`、`sampler.py` | NIW予測と周辺尤度比、split-merge単独の定常分布と全列挙の比較、順序制約、符号アンカー、N=1 |
| §5、§6 | `coordinates.py`、`lineage.py`、`inference/regions.py` | 回答確率を保つ尺度変換、固定射影、ラベル不変VI、Jaccard継承、歪んだ分布の楕円含有率、独立チェインの領域検証 |
| §7、§7.1 | `artifact.py`、`project.py`、`training.py` | cutの等重み、未観測/対応失敗、保存往復、危険なパス・欠損配列の拒否、同時事後の受渡し |
| §0、§9 | `research.py`、`study.py`、`validation.py` | 回答者ホールドアウト、正規/t比較モデル、因子を積分した予測、Wilson区間、所属校正、事前生成 |
| §4.3、§9.3 | `diagnostics.py`、`run.py` | 定数量と停止したチェインの区別、不合格時の成果物作成禁止、CURRENTの保持 |
| §1、§8、§10 | `data.py`、`private.py`、`nightly.py` | 同意・tombstone・項目版・最新時刻、非公開ドロー、DB/RLS、締め・冪等性 |

## 研究検証コマンド

```powershell
uv run --group pipeline python -m pipeline.run validate --mode prior --repetitions 1000 --output .private-statistics/prior.json
uv run --group pipeline python -m pipeline.run validate --mode sbc --repetitions 1000 --output .private-statistics/sbc.json
uv run --group pipeline python -m pipeline.run validate --mode recovery --condition one --people 300 --items 230 --dimensions 16 --repetitions 1000 --output .private-statistics/recovery-one.json
```

`recovery`の他条件は`separated`、`overlap`、`skew`、`heavy_tail`、`local_dependence`、`careless`。前二つだけ真のK=3、それ以外はK=1とし、群数の誤りと分布の誤指定を混同しない。学習者の領域被覆と、新しい人のcut領域被覆・回答数別の面積/分散を分けて記録する。結果には推定の収束可否も含め、収束しなかった反復を黙って捨てない。

`study`は`fit`と同じ入力指定に`--sizes 100 300 1000 --repetitions 100 --output ...`を付ける。回答者の学習・評価・独立再現用プールを分け、再標本化のたびにMFM・単一正規・多変量tを再推定する。`sensitivity`は事前分布の指定範囲を比較する。`hierarchy`は親海域の選択を含めた全手続きを連続帰無モデルにも適用し、海域間の最大統計量と独立標本で検証する。階層性の結論には、帰無検証だけでなく`study`のプロフィール・安定性基準も必要。

**今回実行したのは実装テストと縮小モデルのCLI動作確認であり、1,000反復の本評価ではない。** 初期事前の妥当性、90問の人格回答（初回98問から品質確認8問を除く）での実データ性能、大人数での計算時間、構造安定化は未認定である。短い実行には`acceptance_run=false`を記録する。

## 数理上の確認と実装上の選択

- 分割事前、Kの条件付き復元、既存/新成分の予測は[Miller–Harrison原論文](https://jwmi.github.io/publications/MFM.pdf)を参照。周辺化自体は事前変更を意味しない。
- split-mergeは5回の補助スキャンの後、最終制限Gibbsスキャンの順逆提案確率をMH比へ入れる。補助分割はアンカーと対象集合だけから生成する。小標本の全分割比較で検証する。
- 部分周辺化では更新順序が重要である。[van Dyk–Park](https://www.ma.imperial.ac.uk/~dvandyk/Research/08-jasa-pcg.pdf)に従い、分割更新後は成分パラメータを再生成してから次の因子更新へ渡す。
- 順序制約付き閾値事前は、平均の違う正規変数を単純にソートした分布とは違う。事前生成には順序条件を満たすまでの棄却、推定には正しい区間での切断正規を使う。SciPyの[truncnorm](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.truncnorm.html)の境界は標準化して渡す。
- NumPyの[数値配列読み込み](https://numpy.org/doc/stable/reference/generated/numpy.load.html)ではpickleを許さず、展開サイズにも上限を置く。
