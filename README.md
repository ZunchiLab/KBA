# KBA｜競馬予想ノート

スマートフォンで読む競馬予想の一覧と、発走前に固定した予想の記録です。

- 一覧：[GitHub Pages](https://zunchilab.github.io/KBA/)
- 区分：中央競馬・地方競馬・海外競馬
- 検索：日付、競馬場、タイトル。開催月と区分でも絞り込めます。
- 対応JSONのある予想では、掲載馬の名前でも検索できます。
- 同じ予想の新版は先に表示し、「旧版も表示する」で履歴を開けます。

## フォルダ構成

```text
index.html                  公開する予想一覧（生成ファイル）
predictions/                予想HTML・対応JSON・旧版
assets/css/site.css         一覧ページのスタイル
assets/js/catalog.js        検索・絞り込み
data/catalog.json           一覧のメタデータ（生成ファイル）
scripts/build_catalog.py    一覧を作成するスクリプト
scripts/index.template.html 一覧ページのテンプレート
```

公開済みの予想は `predictions/` 内の元のパスを維持します。既存リンクと過去の判断記録を残すため、旧版を上書き・移動しません。

## 予想を追加するとき

1. HTMLと対応するJSONを `predictions/` へ追加します。
2. 次のコマンドで一覧を更新します。Pythonの標準ライブラリのみを使います。

   ```sh
   python -X utf8 scripts/build_catalog.py
   ```

3. 追加した予想、`index.html`、`data/catalog.json` を同じコミットで保存します。

日付・区分は既存ファイル名から読み取ります。対応JSONがある場合は、競馬場、固定時刻、版、対象レースも反映します。新版の推奨名は `report_YYYYMMDD_nar_ooi_predictions_vN.html` と同名のJSONです。

一覧は生成済みHTMLなので、閲覧時にGitHub APIへアクセスしません。JavaScriptが無効でも予想リンクを開けます。

## 予想の記録について

各ページの確認時刻・対象レース・購入条件を確認してください。主観的な参考点は勝率ではありません。結果判明後の反省や変更は、事前の予想原本と区別して保存します。

## 地方競馬の結果表示（2026-10-07 園田・大井）

今日の2ページの「結果を取得」ボタンで、保存済みの公式着順・払戻・事前◎の着順と掲載買い目の組合せ的中を表示します。未確定・取得失敗・取消による返還は別に表示します。予想JSON、印、順位、点数、保存時の価格条件は変更しません。

- 追加前の公開HTML・JSON原本：`predictions/archive/20261007_original/`。Gitの元コミットのバイト列とSHA-256を保存。
- 結果だけのJSON：`data/results/nar/2026-10-07/sonoda.json`、`ooi.json`。
- 公式結果HTMLの取得原本：`data/results/sources/2026-10-07/`。取得日時とSHA-256は結果JSONに記録。
- 収集対象：`data/results/targets.json`。園田は予想対象の7〜12R、大井は1〜12R。
- 収集：`python -X utf8 scripts/update_nar_results.py --active-only`。発走前は取得せず、着順と払戻が揃うまで未確定とする。確定済みレースは再取得せず、全対象レースの確定後は公式アクセスを止める。訂正の再照合には`--force`を使う。
- 結果更新：`.github/workflows/nar-results.yml`（Update NAR results）が `scripts/watch_nar_results.py` を起動し、本日の対象レースが確定するまで約2分間隔で公式結果を取得・公開する。10分間隔のscheduleは初回以降に起動せず、15:44で結果が止まったため、この継続実行へ変更。scheduleは毎時の復旧用として残すが、通常の取得間隔をscheduleに依存させない。実行中の処理は最長345分、22:05 JSTまたは全対象確定で停止。収集側も**2026-10-07を含む年月日**を確認し、対象日以外は取得しない。ユーザー承認で追加したworkflow権限を使い、結果ファイルだけをコミットする。
- 「結果を取得」は最新の公開JSONを読む。ボタンの押下そのものによる公式サイトへの直接リクエストではない。取得後は画面が表示されている間、1分ごとに公開結果を再読込し、全対象確定後に止める。公式での確定待ち、取得・公開・配信の遅延があるため、表示の更新日時を確認する。約2分更新のデータが6分以上古ければ更新停止の案内を出す。
- 公開ブラウザーはGitHubの公開raw配信から最新mainのJSONを読み、取得できなければPagesの保存済みJSONへフォールバック。`GITHUB_TOKEN`のコミットでPagesの再ビルドが起きなくても結果だけは更新できる。秘密鍵・トークンをHTMLやJavaScriptに含めない。
- 結果取得時に、日付・競馬場・元の予想版・予想JSONのSHA-256・全出走馬を照合する。予想JSONハッシュはUTF-8/BOMなし・改行LFへ正規化し、WindowsとGitHub/Linuxの改行差を吸収。
- 同着は公式払戻の全組合せで判定。競走中止を返還とは扱わず、出走取消・除外は返還として区別する。保存価格を満たさない組合せが当たっても購入対象の的中へ加えない。仮想払戻は、保存価格達成分を直前条件も満たして買った仮定。実収支ではない。

HTMLへの追加は`python -X utf8 scripts/add_results_view.py`。元HTML/JSONを先にアーカイブし、結果UIだけを同じ公開URLへ追加します。カタログは従来どおり`build_catalog.py`で生成します。
