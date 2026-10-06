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
