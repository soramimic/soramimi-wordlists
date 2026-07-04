# soramimi-wordlists

[Soramimic](https://github.com/jiroshimaya/soramimic)(空耳作詞支援システム)などで使う単語リスト集。
利用側リポジトリからは git submodule で参照する想定。

## 形式(tidy CSV)

全リストはCSV形式。必須列は `id, original, surface`。

| 列 | 意味 |
|---|---|
| id | 単語のグループID(同じ元単語の行は同じid) |
| original | 元の単語(表示用) |
| surface | 変換結果として表示する表層 |
| pronunciation | 読み(カタカナ)。無い場合はsurfaceから推定される |
| team, type, org_id | リスト固有の付加情報(野球・サッカー等)。`type` は利用側のwhereクエリでの絞り込みに使う |

## リスト一覧

| ファイル | 内容 | 出典・クレジット |
|---|---|---|
| baseball.csv | プロ野球選手(type: family/given/full/registered) | Moto(選手表ニキ)様と協力者の皆様([やきゅうた広場](https://sns.prtls.jp/yakyuuta/home.html)) |
| football.csv | サッカー選手 | ヨロスー様 |
| stations.csv | 駅名 | すきやきすきや様 |
| nations.csv | 国名 | |
| physicist.csv | 物理学者 | |
| sekitsui.csv | 動物(脊椎動物) | |
| pokemon.csv | ポケモン(第9世代まで) | |

## 野球選手表の更新手順

1. 最新の野球選手表を[やきゅうた広場(旧)](https://sns.prtls.jp/yakyuuta/home.html)からダウンロード
2. Sheet1をcsvにして1−4行目を削除。文字コードはutf8。ここでは `new_baseball_raw.csv` とする
   - 使われる列は「氏名」「球団」「フルネーム ふりがな」「姓 フリガナ」「名 フリガナ」のみ
3. 差分csvを作成:
   ```sh
   cd tools
   uv run make_diff_baseball_tidy.py -n new_baseball_raw.csv -c ../baseball.csv -o output.csv
   ```
4. 出力の `score`(NameDividerのスコア。低いほど怪しい)や `note` が「please check」の行を中心に名字分割を目視確認(偽陽性多め)
5. 確認後、`score`/`note` 列を削除して `baseball.csv` に追記する(Google Sheet等の利用推奨)

## メンテナンス

- `tools/` に整備用スクリプト(uv管理)
- 更新したら利用側リポジトリで submodule を更新する:
  ```sh
  git submodule update --remote wordlists
  ```
