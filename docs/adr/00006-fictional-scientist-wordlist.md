# ADR 00006: fictional_scientist リストの追加(画像はGitHub Release配布)

- Status: accepted
- Date: 2026-07-06
- Supersedes: none
- Superseded by: none

## Context

`fictional-scientists` プロジェクトで、AI生成による架空の科学者1000人分の人物データと肖像「カード」画像(名前・生没年・主な業績などのテキストを画像内に合成済み)を作成した。これを `fictional_scientist.csv` として本リポジトリに取り込みたい。

既存の人名リスト(baseball/football/stations/physicist)は実在人物であり、`image`/`image_page` はいずれも Wikimedia Commons 上の画像を指す前提で、`tools/validate_csvs.py` も `^https?://commons\.wikimedia\.org/` のみを許可している。しかし今回の画像は:

- 実在しない架空人物のAI生成画像であり、Wikimedia Commons の収録基準(実在の被写体・出典明記等)になじまない
- カード内に名前・生没年・業績テキストを合成済みであり、soramimic-video 側で毎回テキストをオーバーレイする現行の仕組みとは前提が異なる

ため、既存の枠組みをそのまま流用せず、画像のホスティング方法と、利用側(soramimic-video)への影響を整理する必要がある。

## Decision

1. **画像は本リポジトリのGitHub Releaseアセットとしてホストする**(Wikimedia Commonsではない)。
   - `image`: `https://github.com/soramimic/soramimic-wordlists/releases/download/fictional-scientist-v1/fs_NNNN.jpg`
   - `image_page`: `https://github.com/soramimic/soramimic-wordlists/releases/tag/fictional-scientist-v1`(ライセンス・クレジットの確認先)
   - `tools/validate_csvs.py` の許可URLを、`https://commons.wikimedia.org/` に加えて `https://github.com/soramimic/soramimic-wordlists/releases/` で始まるものも許可するよう拡張する(any-httpsにはせず、明示的なプレフィックス許可リストのまま維持)。
2. **カード画像には名前・生没年・主な業績等のテキストを生成時点で合成しておく。** soramimic-video 側でテキストオーバーレイのロジックを追加・変更する必要をなくし、既存の画像利用フロー(URLを1枚絵として表示するだけ)を変更せずに済ませる。
3. **人口統計・経歴系の列(`birth_year`, `death_year`, `nationality`, `field`, `achievement`)は、動画用の別リストに切り出さず、`fictional_scientist.csv` 本体の `image_page` 列より後ろに追加する。** ADR 00005 で baseball/football/physicist に「付加情報(替え歌動画用)」として `image`/`image_page` を同一CSVに同居させた前例を踏襲し、リストを分割しない。
4. **画像はすべてAI生成の架空人物であり、実在人物の肖像・氏名を利用したものではない。** ライセンス・クレジット表記はCommonsのファイルページに相当するものとしてReleaseのタグページ(`image_page`)に記載し、利用側はそこを確認すること。

## Consequences

- `tools/validate_csvs.py` の許可URLが増えるが、明示的なプレフィックス一致のままなので、無関係なURLの誤登録を防ぐバリデーションの強度は維持される
- 画像アセットの実体(1000枚のカード画像)は本リポジトリのGitHub Releaseに置かれるため、リポジトリ本体(git管理下のファイル)のサイズは増えない
- 画像の生成・Releaseへのアップロードは `fictional-scientists` 側のプロセスが担当し、本リポジトリでは `fictional_scientist.csv` を受け取って配置するのみ(baseball/football/physicist のような自動更新バッチの対象外)
- 将来、画像を差し替える場合はReleaseアセットの上書きまたは新タグの発行が必要。CSVの `image` URLとタグ名の対応が崩れないよう、リリースタグ(`fictional-scientist-v1` 等)はバージョニングして管理する
