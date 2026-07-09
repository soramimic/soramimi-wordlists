# soramimic-wordlists

[Soramimic](https://github.com/jiroshimaya/soramimic)(空耳作詞支援システム)などで使う単語リスト集。
利用側リポジトリからは git submodule で参照する想定。

## 形式(tidy CSV)

全リストはCSV形式。必須列は `id, original, surface`。
**フィールドにカンマ・引用符を含めないこと**(利用側のパーサはクオート非対応の素朴なsplit。URL中のカンマ等は%エンコードする)。
**ファイル末尾に改行を入れないこと**(soramimic側のパーサが最終空行で落ちる)。

| 列 | 意味 |
|---|---|
| id | 単語のグループID(同じ元単語の行は同じid) |
| original | 元の単語(表示用) |
| surface | 変換結果として表示する表層 |
| pronunciation | 読み(カタカナ)。無い場合はsurfaceから推定される |
| team, type, org_id | リスト固有の付加情報(野球・サッカー等) |
| class | sekitsui固有: 大分類(魚類/両生類/爬虫類/鳥類/哺乳類、分類不明はNA) |
| extinct | sekitsui固有: 絶滅種か(yes/no)。IUCN絶滅・野生絶滅、または化石タクソンをyesとする |
| type1, type2 | pokemon固有: ポケモンのタイプ(でんき等)。単タイプは type2=NA |
| status | nations/stations: `current`(現存)/`former`(廃止・脱退・旧称)。stationsは改名前の旧駅名を `renamed` で区別する |
| prefecture, city | stations固有: 駅の所在都道府県・市区町村(同名駅の区別用。1行=1駅) |
| image, image_page | 写真のURL(Wikimedia Commons直リンクまたは本リポジトリのGitHub Releaseアセット)と、ライセンス・作者の確認先ページ(stations/baseball/football/physicist/fictional_scientist/fictional_anime_character)。利用時はimage_pageのクレジット条件に従うこと |
| wikidata | stations固有: 駅のWikidata QID(差分更新の永続キー) |
| birth_year, death_year, nationality, field, achievement | fictional_scientist固有: 生年・没年・国籍・分野・主な業績(AI生成の架空人物情報) |
| title, org_name, role_in_org, first_year, species, cv_name, description | fictional_anime_character固有: 作品名・所属・役割・初登場年・種族・声優名・紹介文(AI生成の架空キャラ情報) |

## リスト一覧

| ファイル | 内容 | 出典・クレジット |
|---|---|---|
| baseball.csv | プロ野球選手・歴代(type: family/given/full/registered) | Moto(選手表ニキ)様と協力者の皆様([やきゅうた広場](https://sns.prtls.jp/yakyuuta/home.html))。現役の新規追加は[Wikipedia](https://ja.wikipedia.org/) (CC BY-SA 4.0)で自動更新 |
| football.csv | サッカー選手(J1〜J3・歴代) | ヨロスー様。現役の新規追加はWikipediaで自動更新 |
| stations.csv | 駅名(現役駅+路面電車・索道。所在地・写真URL付き) | [Wikidata](https://www.wikidata.org/)/[Wikipedia](https://ja.wikipedia.org/) (CC BY-SA 4.0) で自動更新。旧リストはすきやきすきや様 |
| nations.csv | 国名(国連加盟国) | [mledoze/countries](https://github.com/mledoze/countries) で自動更新 |
| physicist.csv | 物理学者(手選び+著名層) | Wikidata/Wikipediaで自動更新 |
| sekitsui.csv | 動物(脊椎動物) | [Wikidata](https://www.wikidata.org/) (CC0) で自動更新 |
| pokemon.csv | ポケモン(地方のすがた・メガ・キョダイマックス含む) | [PokéAPI](https://github.com/PokeAPI/pokeapi) で自動更新 |
| fictional_scientist.csv | AI生成による架空の科学者1000人(名前・読み・生没年・国籍・分野・主な業績・肖像カード画像) | jiroshimaya/fictional-scientists プロジェクトによる自動生成(実在人物とは無関係)、画像は本リポジトリのReleaseで配布 |
| fictional_anime_character.csv | AI生成による架空アニメ『蒼穹の螺旋航路』の登場キャラ1000人(名前・読み・所属・初登場年・種族・声優名・紹介文・肖像カード画像) | jiroshimaya/fictional-scientists プロジェクトによる自動生成(実在の作品・人物とは無関係)、画像は本リポジトリのReleaseで配布 |

## 自動更新(pokemon / nations)

ネット上の公開データから自動更新できるリストは、GitHub Actions
(`.github/workflows/update-wordlists.yml`)で年1回(1月上旬)バッチ実行し、
差分があればPRが作られる(要リポジトリ設定: Settings > Actions > General >
「Allow GitHub Actions to create and approve pull requests」)。
手動実行は Actions タブの workflow_dispatch から。ローカルでは:

```sh
python3 tools/update_pokemon.py    # PokéAPIの公式CSVから全件再生成(id=全国図鑑No-1)
python3 tools/update_nations.py    # 国連加盟国の増減を検出し新規のみ追記
python3 tools/update_stations.py   # Wikidata/Wikipediaと突き合わせ、新駅追記+status更新
python3 tools/update_baseball.py   # NPB現役ロースターから未収録選手を追記
python3 tools/update_football.py   # J1〜J3ロースターから未収録選手を追記
python3 tools/update_physicist.py  # Wikidataの著名物理学者(sitelinks>=20)を追記
python3 tools/update_sekitsui.py   # Wikidataの脊椎動物(rank=種・カタカナ和名)を追記
python3 tools/enrich_images.py     # 画像が空の人物行にCommons画像を遡及付与
```

- pokemon: 全件再生成。フォームは「ライチュウ（アローラのすがた）」形式で
  表記ゆれ3行を同一idで収録。種とフォームは別ポケモンとして別id
  (詳細は ADR 00002)
- nations: 既存行の表記・idは変更しない。新規加盟の追記と status の更新のみ。
  ISOコードとの対応は `tools/nations_map.csv` で管理(詳細は ADR 00003)
- stations: 1行=1駅(Wikidata QIDが永続キー)。既存行は書き換えず、新駅の追記と
  status の更新のみ。新駅の読みはWikipedia冒頭文から抽出(詳細は ADR 00004)
- baseball/football/physicist: 既存データ(歴代名鑑・手選び)は保持し、
  未収録の現役選手・著名物理学者だけ追記。姓名分割済みの読みは記事冒頭
  「姓 名(せい めい、」から取得(詳細は ADR 00005)
- sekitsui: Wikidataの脊椎動物(rank=種・日本語ラベルがカタカナ)を綱ごとに
  取得し、未収録の和名だけ追記。和名がそのまま読みになるので読み抽出は不要。
  `class` 列に大分類(魚類/両生類/爬虫類/鳥類/哺乳類)、`extinct` 列に絶滅種か
  (yes/no)を付与し、化石種も含める(詳細は ADR 00007)
- 自動更新の対象外は fictional_scientist(外部プロジェクトで生成したCSVを
  取り込む方式。詳細は ADR 00006)

設計判断の記録は [docs/adr/](docs/adr/) を参照。

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
