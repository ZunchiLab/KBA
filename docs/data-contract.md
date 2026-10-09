# 共通データ契約 v1.0

更新：2026-10-07 JST。[共通仕様](common-spec.md)のデータ項目と旧形式の対応表。

**本書は新規実装の契約。10/8の地方新規予想から予想形式を採用。既存JSONは変換していない。** 旧原本を保持し、アダプターの出力を別ファイルとして保存する。欠損は `null`、未確認は明示した状態で扱い、0や推定値で埋めない。地方結果は当面旧 `schema_version: 1` のままとし、共通結果形式や真の返還精算とは区別する。

## 1. 識別子・日時・出典

| 項目 | 契約 |
|---|---|
| `authority` | `jra` または `nar`。海外は別契約 |
| `date_jst` | `YYYY-MM-DD`、開催地の日付 |
| `venue_key` | 公式コードに対応する安定したキー。例 `tokyo`、`kyoto`、`sonoda`、`ooi` |
| `race_uid` | `authority-date_jst-venue_key-r番号`。例 `nar-2026-10-07-ooi-r11` |
| `official_race_id` | 取得元が確認できる識別子。未取得は `null`。netkeibaのIDを無条件に公式IDと呼ばない |
| `source_race_id` | サイト名・そのサイトのIDをセットで保持 |
| 日時 | オフセット付きISO 8601。取得・固定・公開・購入確認を別項目へ。画面はJSTで表示 |
| `source` | `provider`、`url`、`retrieved_at`、`raw_sha256`、`raw_file`、`encoding` |
| 原文ハッシュ | 受信した元バイト列を保存してSHA-256。デコードや改行変換後のファイルとは区別 |
| 予想の照合ハッシュ | UTF-8・BOMなし・改行LFで正規化。`hash_method: "utf8-no-bom-lf-sha256"`を記録 |

旧JRAの取得処理はCP932の受信バイト列に対するハッシュを記録し、保存HTMLはUTF-8へ変換している。**その保存HTMLのハッシュが旧 `source_hash` と同じだとは扱わない。** 新規取得では元バイト列を先に保存する。

## 2. 開催日の予想JSON

| 項目 | 内容 |
|---|---|
| `schema_version` | `kba.forecast/1` |
| `document_type` | `prediction`。開催後は別ファイルで `review` |
| `authority`, `date_jst` | 区分・開催日 |
| `forecast_version` | 公開予想の版。モデル版は `model_version` に分ける |
| `fixed_at` | 開催日ページの版を固定した時刻。レースごとの確認時刻を上書きしない |
| `phase` | `pre_race`、`remaining_races`、`post_event_presentation`。結果後の再構成を事前予想にしない |
| `venues` | `venue_key`、`label`、公式コードの対応 |
| `races` | 全予想対象レース。会場付き識別子・時刻を必ず持つ |
| `excluded_races` | 対象外Rとその理由。終了済み・見送り・出馬表不足を区別 |
| `budget` | `mode: "example"/"user_specified"`、1日上限、選択した本線の合計、会場配分 |
| `model` | モデル版・指数の定義・未学習／未校正・既知の制約 |
| `publication` | リポジトリ・ブランチ・公開先・原本ハッシュ。公開済みJSON自体のハッシュを自分自身へ入れない |

開催日の統合JSONが大きい場合は、`venues[].forecast_file` から会場別の固定JSONを参照するday manifestを置ける。その場合も元版・固定時刻・ハッシュを記録する。HTMLのタブを理由に、会場別の原本や取得時刻を捨てない。

### 各レース

- `race_uid`、`venue_key`、`race_no`、`official_race_id`、`source_race_id`。
- `name`、`class_text`、`surface`、`distance_m`、`start_at`、`weather`、`going`、`field_size_at_sale_start`。確認できないものは `null`。
- `fixed_at`、`source_checked_at`、`sources[]`、`model_version`。
- `analysis`：本線の展開・別展開、買う／見送る理由、信頼度の定義、波乱指数の定義。未校正の指数は確率にしない。
- `horses[]`：`number`、`frame`、`name`、`source_horse_id`、`jockey`、`status_at_snapshot`、`score`、`score_definition`、`rank`、`mark`、`reasons[]`、`risks[]`、`missing[]`、`evidence_refs[]`。
- JRAの勝・安定・上振れ・調教、地方の近走・転入・級などは、元の意味を保った `model_features` へ保存する。未検証の共通クラス点へ置き換えない。
- `bet_plans[]`：以下の買い目契約。
- `actual_purchase` は固定予想へ後付けしない。実購入記録は別データにする。

10/9の地方追加項目（互換の任意項目）：`analysis.win_view`・`place_view` は人手で記述した勝つ／圏内の説明、`win_candidates`・`place_candidates` は評価上の候補。`popular_compare` は保存時の単勝最小値との比較。`horses[].comparison` の `suitability`・`recency`・`last_actual_start`・`days_since_actual_start`・`position`・`roles`・`ticket_review` は全頭の比較と採否理由。`past[].full_name`・`additional_source` は省略競走名を補う公式原文で、元の `name` を保持する。

## 3. 買い目

### 券種の正規化

| `kind` | 画面名・旧形式の別名 | 数字の意味・順序 |
|---|---|---|
| `win` | 単勝 | 馬番1つ |
| `place` | 複勝 | 馬番1つ |
| `wide` | ワイド | 馬番2つ・順不同 |
| `quinella` | 馬連・馬複・馬連複・`umaren` | 馬番2つ・順不同 |
| `exacta` | 馬単・馬連単・`umatan` | 馬番2つ・1→2着 |
| `trio` | 三連複・3連複 | 馬番3つ・順不同 |
| `trifecta` | 三連単・3連単・`tierce` | 馬番3つ・1→2→3着 |
| `bracket_quinella` | 枠連・枠複・枠連複・`wakuren` | 枠番2つ・順不同。同枠の組合せもある |
| `bracket_exacta` | 枠単・枠連単 | 枠番2つ・着順指定。同枠の組合せもある |

`number_type` は `horse` / `bracket`。馬番用の「同じ番号を使わない」処理を枠式へ適用しない。WIN5は `legs[]` の5つの `race_uid` と候補馬を順番どおり保持する別商品で、単一レースの買い目へ混ぜない。

### プランと各点

| 項目 | 内容 |
|---|---|
| `plan_id` | レース内で一意 |
| `role` | `main` 本線、`alternative` 代案、`reference` 説明用 |
| `selected_for_example` | 例示の予算へ含める案か。別券種の全案を自動で加算しない |
| `kind`, `number_type`, `ordered` | 正規化した券種・番号種別・順序指定 |
| `method`, `groups` | `individual` / `box` / `formation` と元の候補群 |
| `tickets[]` | 重複除去済みの全点。各点の `numbers`・`example_stake_yen` |
| `points`, `maximum_example_yen` | 点数と全点購入時の金額例。券種を問わず再計算できる形 |
| `reason`, `stop_conditions[]` | 買う根拠・購入を止める条件 |
| 各点の `market` | `lower_odds`、`upper_odds`、`checked_at`、`source`。取得できなければ `null` |
| 各点の `minimum_odds` | 価格下限。設定がなければ `null` |
| 各点の `price_condition_at_snapshot` | 保存時に達成 `true`、不達成 `false`、比較不能 `null` |

価格条件達成は購入証明ではない。直前の取消・価格・馬場の再確認と、ユーザーの実購入記録を分けて扱う。

旧JRAには点ごとの保存価格や最低オッズがない。変換時に `true` や推測値を補完しない。旧JRAの券種ごとの掲載案は代案として保持し、どれが本線だったか未指定なら `selected_for_example: null` とする。

## 4. 結果JSON（会場別）

| 項目 | 内容 |
|---|---|
| `schema_version` | `kba.results/1` |
| `authority`, `date_jst`, `venue_key` | 固定予想の対象と照合 |
| `forecast_ref` | 公開ファイル・版・正規化SHA-256・ハッシュ方法 |
| `updated_at` | 結果データが変わった時刻 |
| `last_poll_at` | 最新の取得試行時刻。既知の公式確認時刻と区別 |
| `published_at` | 公開が確認できる場合の時刻。不明なら `null` |
| `races[]` | 下記のレース結果 |

各レースは `race_uid`、`status`、`official_confirmed`、`source`、`source_checked_at`、`rows_complete` を持つ。

- `rows[]`：`number`、`name`、`finish: integer/null`、`runner_status`、`official_status_text`、`time`、`margin`、`last_3f`、`final_popularity`、`final_win_odds`。
- `runner_status`：`finished` / `withdrawn` / `excluded` / `did_not_finish` / `disqualified` / `unknown`。元の表示文言を残す。
- `payouts[]`：`kind`、`number_type`、`numbers`、`yen_per_100`、`popularity`。同着の複数的中を全て保存する。
- `payouts_status`：券種別に `pending` / `partial` / `confirmed`。払戻未掲載を0円として扱わない。
- `refunds[]`：公式で確認した券種・番号・返還率・理由・出典。`refund_status`が未確認なら返還判定を保留する。
- `refresh_error`：失敗した時刻・理由。以前の確定結果を消して `error` のみへ置き換えない。
- 非公式を使う場合は `official_confirmed: false` と情報源を明示し、公式確定の集計へ入れない。

速報で未掲載の馬は `finish: null`。不的中・取消・返還を推定しない。確定判定には対象馬の照合と必要な公式払戻・返還の確認を使う。

## 5. 購入記録

今後の取込用契約は `schema_version: "kba.purchases/1"`。固定予想と別ファイルにする。

- 記録：`id`、`recorded_at`、`authority`、`date_jst`、`venue_key`、`venue_label`、`race_uid`、`forecast_ref`。
- 状態：`planned` / `skipped` / `purchased`。`purchased` は `user_reported: true` など、申告記録だと分かる項目を保持する。
- 内容：`kind`、全点の `numbers` と `stake_yen`、点数、合計、価格確認時刻、各点の購入時価格（不明は `null`）、採否理由。
- 予算：レース上限・1日上限。予定金額と購入済み金額を区別する。
- 実結果：後から公式結果へ照合し、的中・不的中・返還・未確定、払戻・返還額・差引を別項目へ保存する。

**現在の補助ページは互換を保って `schema_version: 1` の端末記録を出力する。** 新規記録に `authority` と `field_size_at_sale_start` を追加。`date`、`venue`、`race`、日本語 `kind`、`tickets[].stake_yen`、`total_yen`、`checked_at_local`、`checked_at_timezone` を上記へ変換する取込処理は未実装。区分・固定予想へのリンクがない旧記録を自動推定で結び付けない。

## 6. 旧JSONからの対応表

| 共通項目 | 旧JRA（10/4） | 旧地方（10/7） |
|---|---|---|
| 開催日 | `target_date` | `date_jst` |
| 予想版・固定時刻 | ファイルの公開版／`model_version`、`generated_at` | `version`、`fixed_at` |
| レース | `races[].key`、`venue`、`no` | `races[].venue_key`、`race` |
| サイトのレースID | `race_id`はnetkeiba由来。出典付きで保持 | `baba_code`・日付・R、公式URL |
| 発走 | `time`に開催日とJSTを付加 | `start_at`または日付付き`start` |
| 馬番・印・順位 | `horses[].num`、`mark`、`rank` | `horses[].number`、`mark`、`rank` |
| 評価の根拠・懸念 | `reason[]`、`concern[]`、特徴・近走 | `reason`、`risk`、`past`、根拠ID |
| 指数 | `score/win/place/upside`と各定義 | `score`と`score_method` |
| 買い目 | `bets[].type/tickets/stake_each/points/cost` | `bets[].type/tickets[]/yen_per_ticket/points` |
| 価格 | 未取得は `null` | `tickets[].price/minimum_odds/price_condition_at_snapshot/source` |
| 結果のレース | `races`が`T1/K1`等をキーにした辞書 | 会場別JSONのレース一覧 |
| 結果の着順 | `horses[].num/finish/status` | `rows[].number/finish`等 |
| 公式払戻 | `payouts`辞書の英語券種→文字列組合せ→円 | `refunds`配列の日本語券種・組合せ・`yen_per_100` |
| 返還 | 旧`refund_notes`の一般文言を自動判定に使わない | `refunds`は払戻配列名。真の返還情報と区別して変換 |

JRAの `tierce` は三連単、地方の旧 `refunds` は**払戻金**。名称だけで意味を取り違えない。どちらも公式原文と対応を残す。

## 7. 導入時の記録

変換したファイルには `origin` として元ファイル・元版・元ハッシュ・変換処理の版・変換日時を残す。取得後・結果判明後の時刻を、元の予想固定時刻へ転記しない。

形式の変更は互換性を保って版を上げ、共通仕様と両チャットの参照指示も同時に更新する。ここにある項目の存在だけで、校正・取得・購入照合が実装済みだとは扱わない。
