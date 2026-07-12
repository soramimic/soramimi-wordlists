#!/usr/bin/env python3
"""physicist.csv を広義の「科学者」リスト scientist.csv に置き換え・拡張する。

出典: Wikidata(職業P106が物理/化学/数学/天文/生物/計算機科学/地学のいずれか,
sitelinks>=20 ≒ 多言語版20版以上に記事がある著名層)と、Wikipedia日本語版記事
の冒頭文(CC BY-SA 4.0)。

- 旧 physicist.csv の全行(id/original/surface/pronunciation/type/image/image_page)
  はそのまま引き継ぎ、新列 field/era/birth_year/nobel/gender/country/status を付与
- 未収録の著名科学者を追記(読み・姓名分割は update_physicist.py と同じ方式)
- 既存行の読み・id・表記は絶対に書き換えない

新列(詳細は docs/adr/00009):
- field:   分野(物理/化学/数学/天文学/生物学/計算機科学/地学)を優先順で並べた
  単一列のスラッシュ区切り多値(例 物理/数学)。切り詰めなし、無ければNA。
  ソラミミック側の部分一致演算子 field~=物理 で1列のまま絞れる前提
- era:     時代区分(古代/中世/近世/近代/現代/NA)。生年basis
- birth_year: 西暦生年(紀元前は「前287」形式、不明はNA)
- nobel:   科学系ノーベル賞受賞者か(yes/no、既存で照合不能はNA)
- gender:  男性/女性/その他/NA
- country: 市民権のある国の日本語ラベル(複数は"/"、不明はNA)
- status:  物故/存命/NA
- description: 主な業績の短い説明(記事冒頭1〜2文≒80字、なければWikidataのja
  description、どちらも無ければNA。ASCIIカンマ・二重引用符は除去)

環境変数 SCIENTIST_CACHE を指定すると、Wikidata/Wikipedia の取得結果(属性
attrs と記事冒頭 extracts)をそのパスに pickle キャッシュし、2回目以降は再取得
せず読み込む(開発用。CI では未設定=常に再取得)。

usage: python3 tools/update_scientist.py
"""

import csv
import datetime
import os
import pickle
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wpnames import (DISAMBIG, KATA2HIRA, KATAKANA, fetch_extracts,
                     parse_person, sparql, write_csv_no_trailing_newline)

OLD_CSV = Path(__file__).resolve().parent.parent / "physicist.csv"
NEW_CSV = Path(__file__).resolve().parent.parent / "scientist.csv"
MIN_SITELINKS = 20
CURRENT_YEAR = datetime.date.today().year
CACHE = os.environ.get("SCIENTIST_CACHE")  # 開発用: 取得結果の pickle キャッシュ先
DESC_MAX = 80  # description の最大文字数(1〜2文)

# 対象職業(P106)→ 日本語フィールドラベル。並び順が field の安定した出力順。
OCCUPATIONS = [
    ("Q169470", "物理"),
    ("Q593644", "化学"),
    ("Q170790", "数学"),
    ("Q11063", "天文学"),
    ("Q864503", "生物学"),
    ("Q82594", "計算機科学"),
    ("Q520549", "地学"),
]
FIELD_ORDER = {label: i for i, (_, label) in enumerate(OCCUPATIONS)}

# era 境界(生年basis。明快な丸め値。変更容易にするためここに集約。ADR 00009 参照)
#   古代: 生年 <= 500 / 中世: 501-1500 / 近世: 1501-1700 /
#   近代: 1701-1900 / 現代: 1901-
def era_of(year: int) -> str:
    if year is None:
        return "NA"
    if year <= 500:
        return "古代"
    if year <= 1500:
        return "中世"
    if year <= 1700:
        return "近世"
    if year <= 1900:
        return "近代"
    return "現代"


def norm(title: str) -> str:
    """既存 original との照合キー(曖昧回避サフィックス除去+全半角空白除去)。"""
    return DISAMBIG.sub("", title).replace("　", "").replace(" ", "")


def image_pair(url: str):
    # カンマ等を含むファイル名はCSVを壊すので必ずURLエンコード
    fname = urllib.parse.quote(
        urllib.parse.unquote(url.rsplit("/", 1)[1]).replace(" ", "_"))
    return ("http://commons.wikimedia.org/wiki/Special:FilePath/" + fname,
            "https://commons.wikimedia.org/wiki/File:" + fname)


def _clean_ws(s: str) -> str:
    """改行・タブ・連続空白を1つの半角空白に潰して1行にする。"""
    return re.sub(r"[\s　]+", " ", (s or "").replace("\n", " ")
                  .replace("\t", " ").replace("\r", " ")).strip()


def _sanitize_desc(s: str) -> str:
    """CSVパーサを壊す文字を除去(ASCIIカンマ→読点、二重引用符→削除)。"""
    s = _clean_ws(s).replace('"', "").replace(",", "、")
    return s[:DESC_MAX].strip()


def make_description(intro: str, wd_desc: str) -> str:
    """記事冒頭の1〜2文(≒DESC_MAX字)を description にする。無ければ Wikidata
    の ja description、どちらも無ければ NA。"""
    text = _clean_ws(intro)
    summary = ""
    if text:
        for seg in re.split(r"(?<=。)", text):
            if summary and len(summary) + len(seg) > DESC_MAX:
                break
            summary += seg
            if len(summary) >= DESC_MAX * 0.6:
                break
        summary = summary or text
    if not summary:
        summary = wd_desc or ""
    return _sanitize_desc(summary) or "NA"


def parse_birth(iso: str):
    """P569のISO日時 -> (表示用文字列, 数値年)。紀元前は「前287」/ 負の数値年。"""
    if not iso:
        return None, None
    try:
        if iso.startswith("-"):
            y = int(iso[1:].split("-")[0])
            return f"前{y}", -y
        y = int(iso.split("-")[0])
        return str(y), y
    except ValueError:
        return None, None


def field_value(labels) -> str:
    """分野ラベル集合 -> 単一 field 値(優先順のスラッシュ区切り多値)。該当が
    無ければ "物理"(呼び出し側で出自デフォルトに使う)。切り詰めはしない。
    ソラミミック側の部分一致演算子 field~=物理 で1列のまま絞り込める前提。"""
    ordered = sorted(set(labels), key=lambda x: FIELD_ORDER[x])
    return "/".join(ordered) if ordered else "物理"


def fetch_person_set() -> dict:
    """QID -> {"title", "fields"(優先順ラベルのリスト)} を返す(sitelinks>=20)。"""
    qid_fields = {}  # qid -> set(label)
    qid_title = {}   # qid -> ja title
    for occ, label in OCCUPATIONS:
        q = f"""
SELECT ?p ?title WHERE {{
  ?p wdt:P106 wd:{occ} ; wikibase:sitelinks ?n .
  ?a schema:about ?p ; schema:isPartOf <https://ja.wikipedia.org/> ;
     schema:name ?title .
  FILTER(?n >= {MIN_SITELINKS})
}}"""
        data = sparql(q)
        n = 0
        for b in data["results"]["bindings"]:
            qid = b["p"]["value"].rsplit("/", 1)[1]
            qid_title[qid] = b["title"]["value"]
            qid_fields.setdefault(qid, set()).add(label)
            n += 1
        print(f"  {label}(wd:{occ}): {n}人", flush=True)
    persons = {}
    for qid, labels in qid_fields.items():
        ordered = sorted(labels, key=lambda x: FIELD_ORDER[x])
        persons[qid] = {"title": qid_title[qid], "fields": ordered}
    print(f"科学者集合: {len(persons)}人(distinct QID)", flush=True)
    return persons


def fetch_attrs(qids: list) -> dict:
    """QID -> 属性dict。P569/P570/P21/P27/P166(nobel)/P18 をバッチ取得。"""
    attrs = {}
    for i in range(0, len(qids), 200):
        batch = qids[i:i + 200]
        values = " ".join(f"wd:{q}" for q in batch)
        q = f"""
SELECT ?p (MIN(?birth) AS ?b) (MAX(?death) AS ?d) (MIN(?genderL) AS ?g)
  (GROUP_CONCAT(DISTINCT ?countryL; SEPARATOR="||") AS ?countries)
  (MAX(?nobelV) AS ?nobel) (MIN(?img) AS ?image)
  (SAMPLE(?wdesc) AS ?desc) WHERE {{
  VALUES ?p {{ {values} }}
  OPTIONAL {{ ?p wdt:P569 ?birth . FILTER(isLiteral(?birth)) }}
  OPTIONAL {{ ?p wdt:P570 ?death . FILTER(isLiteral(?death)) }}
  OPTIONAL {{ ?p wdt:P21 ?gender . ?gender rdfs:label ?genderL .
             FILTER(LANG(?genderL)="ja") }}
  OPTIONAL {{ ?p wdt:P27 ?country . ?country rdfs:label ?countryL .
             FILTER(LANG(?countryL)="ja") }}
  OPTIONAL {{ ?p wdt:P166 ?a . ?a wdt:P31 wd:Q7191 . BIND("yes" AS ?nobelV) }}
  OPTIONAL {{ ?p wdt:P18 ?img }}
  OPTIONAL {{ ?p schema:description ?wdesc . FILTER(LANG(?wdesc)="ja") }}
}} GROUP BY ?p"""
        data = sparql(q)
        for bnd in data["results"]["bindings"]:
            qid = bnd["p"]["value"].rsplit("/", 1)[1]
            attrs[qid] = build_attr(bnd)
        print(f"  属性取得 {min(i + 200, len(qids))}/{len(qids)}", flush=True)
    return attrs


def build_attr(bnd: dict) -> dict:
    birth_iso = bnd.get("b", {}).get("value")
    death_iso = bnd.get("d", {}).get("value")
    birth_disp, birth_num = parse_birth(birth_iso)
    gender_raw = bnd.get("g", {}).get("value")
    gender = {"男性": "男性", "女性": "女性"}.get(gender_raw, "その他" if gender_raw else "NA")
    countries_raw = bnd.get("countries", {}).get("value", "")
    cs = set()
    for c in countries_raw.split("||"):
        c = c.strip().replace(",", " ")  # ラベル内カンマはパーサを壊すので除去
        if c:
            cs.add(c)
    # 出力順を安定化(WDQSのGROUP_CONCAT順は非決定的で年次PRのノイズになる)
    country = "/".join(sorted(cs)) if cs else "NA"
    nobel = "yes" if bnd.get("nobel", {}).get("value") == "yes" else "no"
    # status: 没年あり=物故 / 生年既知で(現在-生年)>120=物故 / 生年既知=存命 / 不明=NA
    if death_iso:
        status = "物故"
    elif birth_num is not None:
        status = "物故" if (CURRENT_YEAR - birth_num) > 120 else "存命"
    else:
        status = "NA"
    img = bnd.get("image", {}).get("value")
    return {
        "birth_year": birth_disp or "NA",
        "era": era_of(birth_num),
        "gender": gender,
        "country": country,
        "nobel": nobel,
        "status": status,
        "image": image_pair(img) if img else None,
        "wd_desc": bnd.get("desc", {}).get("value", ""),
    }


COLS = ["id", "original", "surface", "pronunciation", "type",
        "field", "era", "birth_year", "nobel", "gender", "country", "status",
        "description", "image", "image_page"]
# 既存行に付与/保持する新列
NEW_FIELDS = ["field", "era", "birth_year", "nobel", "gender", "country",
              "status", "description"]


def fetch_all(persons: dict):
    """attrs と 全人物の記事冒頭 extracts を取得(キャッシュ対応)。"""
    if CACHE and Path(CACHE).exists():
        with open(CACHE, "rb") as fh:
            attrs, extracts = pickle.load(fh)
        print(f"キャッシュから読み込み: {CACHE}", flush=True)
        return attrs, extracts
    attrs = fetch_attrs(sorted(persons))
    titles = sorted({p["title"] for p in persons.values()})
    print(f"記事冒頭を取得中... {len(titles)}件", flush=True)
    extracts = fetch_extracts(titles)
    if CACHE:
        with open(CACHE, "wb") as fh:
            pickle.dump((attrs, extracts), fh)
        print(f"キャッシュ保存: {CACHE}", flush=True)
    return attrs, extracts


def main() -> int:
    persons = fetch_person_set()
    if not 2000 <= len(persons) <= 12000:
        print(f"error: implausible scientist count: {len(persons)}", file=sys.stderr)
        return 1
    attrs, extracts = fetch_all(persons)

    # 照合キー(正規化タイトル)-> {qid, field, attr, desc}
    by_key = {}
    for qid, p in persons.items():
        key = norm(p["title"])
        by_key[key] = {
            "qid": qid, "field": field_value(p["fields"]),
            "attr": attrs.get(qid, {}),
            "desc": make_description(extracts.get(p["title"], ""),
                                     attrs.get(qid, {}).get("wd_desc", "")),
        }

    # 2回目以降は生成済みの scientist.csv を正とし、初回のみ physicist.csv から移行
    source = NEW_CSV if NEW_CSV.exists() else OLD_CSV
    print(f"既存データ読み込み元: {source.name}", flush=True)
    old_rows = list(csv.DictReader(source.open(encoding="utf-8")))
    for r in old_rows:
        r.setdefault("image", "")
        r.setdefault("image_page", "")
    existing = {r["original"] for r in old_rows}

    # 既存行への新列付与 + 空欄画像のバックフィル
    matched = 0
    for r in old_rows:
        info = by_key.get(r["original"])
        if info:
            matched += 1
            r["field"] = info["field"]
            a = info["attr"]
            r["era"] = a.get("era", "NA")
            r["birth_year"] = a.get("birth_year", "NA")
            r["nobel"] = a.get("nobel", "no")
            r["gender"] = a.get("gender", "NA")
            r["country"] = a.get("country", "NA")
            r["status"] = a.get("status", "NA")
            r["description"] = info["desc"]
            if not r["image"] and a.get("image"):
                r["image"], r["image_page"] = a["image"]
        elif r.get("field"):
            # scientist.csv 再実行時: Wikidata非一致行は既存の付加情報を保持する
            for c in NEW_FIELDS:
                r.setdefault(c, "NA")
        else:
            # physicist.csv からの初回移行: 出自が物理学者なので field=物理、他はNA
            r["field"] = "物理"
            r["era"] = r["birth_year"] = r["nobel"] = "NA"
            r["gender"] = r["country"] = r["status"] = r["description"] = "NA"
    print(f"既存 {len(old_rows)}行, Wikidata一致 {matched}行", flush=True)

    candidates = [p["title"] for p in persons.values()
                  if norm(p["title"]) not in existing]
    print(f"新規候補 {len(candidates)}件", flush=True)

    next_id = max(int(r["id"]) for r in old_rows) + 1
    added, flagged = [], []
    for title in candidates:
        parsed = parse_person(DISAMBIG.sub("", title), extracts.get(title, ""))
        if parsed is None:
            flagged.append(title)
            continue
        f_s, f_y, g_s, g_y, full_s, full_y, _reg = parsed
        original = full_s.replace(" ", "")
        if original in existing:
            continue
        existing.add(original)
        # 既存規約: 日本人漢字名の読みはひらがな、カタカナ名はそのまま
        if not KATAKANA.match(original):
            f_y = f_y.translate(KATA2HIRA)
            full_y = (f_y + g_y.translate(KATA2HIRA))
            full_s = original
        info = by_key.get(norm(title), {})
        a = info.get("attr", {})
        base = {
            "field": info.get("field", "物理"),
            "era": a.get("era", "NA"),
            "birth_year": a.get("birth_year", "NA"),
            "nobel": a.get("nobel", "no"),
            "gender": a.get("gender", "NA"),
            "country": a.get("country", "NA"),
            "status": a.get("status", "NA"),
            "description": info.get("desc", "NA"),
        }
        img, img_page = a.get("image") or ("", "")
        rows = []
        if f_s and f_s != full_s:
            rows.append((f_s, f_y, "family"))
        rows.append((full_s, full_y, "full"))
        for surface, pron, typ in rows:
            row = {"id": str(next_id), "original": original, "surface": surface,
                   "pronunciation": pron, "type": typ, **base,
                   "image": img, "image_page": img_page}
            added.append(row)
        next_id += 1

    write_csv_no_trailing_newline(NEW_CSV, COLS, old_rows + added)

    n_people = len({r["id"] for r in added})
    max_fields = max((len(r["field"].split("/")) for r in old_rows + added
                      if r["field"] not in ("NA", "")), default=0)
    print(f"\nscientist.csv: 既存{len(old_rows)}行 + 新規{n_people}人({len(added)}行) "
          f"= {len(old_rows) + len(added)}行", flush=True)
    print(f"単一field列(スラッシュ区切り)・切り詰めなし。最大分野数: {max_fields}", flush=True)
    print(f"要確認(読み機械決定不能) {len(flagged)}件", flush=True)
    for t in flagged[:50]:
        print(f"  要確認: {t}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
