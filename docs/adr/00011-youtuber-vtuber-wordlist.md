# ADR 00011: youtuber / vtuber リストの追加

- Status: accepted
- Date: 2026-07-24
- Supersedes: none
- Superseded by: none

## Context

空耳作詞の題材として YouTuber・VTuber の名前リストが欲しい。VTuber 名(兎田ぺこら・宝鐘マリン・葛葉など)は音が特徴的で読みも立っており、YouTuber 名(HIKAKIN・はじめしゃちょーなど)もカタカナ・ひらがな読みが強い。ポケモンや駅名と同様「広く知られた固有名詞」であり、変換結果が刺さりやすいジャンルである。

取得は scientist.csv(ADR 00009)と同じ方式が流用できる: Wikidata の職業(P106)で対象を絞り、ja.wikipedia の記事の有無を足切りに使い、記事冒頭文から読みを抽出する。

固有の考慮点:

- **実在人物性**: YouTuber は実在人物。記事名(=活動名)のみを収録し、本名などの個人情報は取得・収録しない。
- **企業IP**: VTuber 名は各社(カバー・ANYCOLOR 等)の知的財産だが、名称と読みのみの非商用ファンメイドリストはポケモンと同じ位置づけとする。アバター画像は各社の著作物で Wikimedia Commons にほぼ存在しないため、**画像列は持たない**(実在 YouTuber も Commons 写真がごく少数のため同様)。
- **変動の激しさ**: VTuber は卒業・引退・転生が多い。`status`(current/former)を最初から持たせる。年 1 回の自動更新では鮮度が落ちるのは既知の割り切り。

## Decision

**youtuber.csv と vtuber.csv の 2 ファイル**を追加し、`tools/update_youtuber.py` / `tools/update_vtuber.py`(共通処理は `tools/yt_common.py`)で生成・追記する。ファイルを分けるのは、所属事務所・活動開始年といった付加情報の性質が違い、利用側でも別リストとして選びたいジャンルのため。

**対象**:

| リスト | P106 | 備考 |
|---|---|---|
| youtuber.csv | Q17125263(YouTuber) | P106 に Q55155641 を併せ持つ者(VTuber)は除外 |
| vtuber.csv | Q55155641(バーチャルYouTuber) | |

いずれも **ja.wikipedia に記事があること**を足切りとする(scientist の sitelinks>=20 に相当する著名性フィルタ。登録者数での足切りは API 依存が増えるため採らない)。国内・海外は区別しない(ホロライブ EN/ID などの海外勢も ja 記事があれば入る)。

**QID フェイルセーフ**: 実行冒頭で各 QID の ja/en ラベルを取得し、期待キーワード(YouTuber / virtual・バーチャル)を含むことを確認してから走る。QID の取り違えで無関係な集合を取り込む事故を防ぐ。

**列**: `id, original, surface, pronunciation, type, org, debut_year, status`(両ファイル共通)。

- **type**: 「兎田ぺこら」のように記事冒頭「姓 名（せい めい、」形式で姓名分割できる名前は family/given/full の 3 行。「HIKAKIN」「キズナアイ」のようなハンドル型は full のみ。あだ名(ぺこーら等)は機械的に取れる出典が無いため収録しない(将来の手動拡張は妨げない)。
- **pronunciation**: カタカナ(README の既定。baseball/football と同じ)。かな・カタカナ名は自身から変換、漢字・ラテン文字名は記事冒頭「名前（よみ、」から抽出。機械決定できない名前はスキップし「要確認」としてログに出す。
- **org**: 所属事務所・グループ。Wikidata の P108(雇用者)/P463(所属団体)/P1416(所属機関)の ja ラベルをソート済みスラッシュ区切り多値で(例 `ホロライブ`)。無ければ NA。ソラミミックの部分一致演算子 `org~=ホロライブ` で絞る前提(ADR 00009 の field と同じ)。
- **debut_year**: 活動開始年。P2031(活動期間の開始)の西暦年。無ければ NA。
- **status**: `current`(活動中)/`former`(卒業・引退・活動終了)。P2032(活動期間の終了)があれば former。**更新は current→former の一方向のみ**(nations/stations と同じ思想。手動で former にした行を自動で current に戻さない)。

**追記専用**: 既存行の original/surface/pronunciation/id は書き換えない。自動更新で行うのは未収録者の追記と status の一方向更新のみ。初回実行はファイルが無い状態から全件生成する(同じスクリプトで冪等)。

**妥当性ガード**: 取得人数が youtuber 200〜20,000・vtuber 100〜10,000 の範囲外なら失敗として中断する(初回生成後、実測に合わせて狭めてよい)。

## Consequences

- baseball/football/scientist と同様、年次バッチ(update-wordlists)で著名 YouTuber・VTuber が自動追記される。`org~=` `status=` `debut_year` でのフィルタ利用ができる。
- **P106 依存の限界**: Wikidata に職業タグが付いていない人物は取りこぼす。逆に副業的にタグが付いた人物(芸能人と YouTuber の兼業など)も入る。ja 記事がある著名層に限っており、題材リストとしては許容する。
- **カタカナ複数語名の姓名順**: parse_person(wpnames)は「名・姓」の洋順を仮定する。ホロライブ EN 等の「姓・名」順のカタカナ名(ワトソン・アメリア等)では family と given のラベルが入れ替わる。空耳素材としては表層が取れていれば実害が小さいため既知の限界として許容する。
- **鮮度**: 卒業・引退の反映は年 1 回のバッチ頼みで遅れる。必要なら手動で status を former に直してよい(自動更新は上書きしない)。
- **実在人物への配慮**: youtuber は活動名のみで本名は収録しない。README の実在人物リストの注意書き(パブリシティ権)の対象に youtuber を加える。vtuber は企業 IP のキャラクター名リストであることを README に明記する。
- グループ(東海オンエア等)・チャンネル名は P106 の職業モデルに乗らないため今回は対象外。需要があれば別途検討する。
