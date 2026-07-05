#!/usr/bin/env python3
"""physicist.csv に著名な物理学者を追記する(既存行は書き換えない)。

出典: Wikidata(職業=物理学者, sitelinks>=20 ≒ 多言語版20版以上に記事がある
著名層)と、Wikipedia日本語版記事の冒頭文(CC BY-SA 4.0)。

- 既存の手選びリスト(367人)の行と読みはそのまま保持し、未収録の人だけ追加
- 日本人等の漢字名: 冒頭「姓 名(せい めい、」からfamily/fullを生成(読みはひらがな)
- カタカナ名: 名前がそのまま読み。姓は最後の区切り(・/=)の後ろ
- ラテン文字イニシャル入り等、読みを機械決定できない名前はスキップして報告

usage: python3 tools/update_physicist.py
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wpnames import (DISAMBIG, KATA2HIRA, KATAKANA, fetch_extracts,
                     parse_person, sparql, write_csv_no_trailing_newline)

CSV_PATH = Path(__file__).resolve().parent.parent / "physicist.csv"
MIN_SITELINKS = 20
QUERY = f"""
SELECT ?p ?title WHERE {{
  ?p wdt:P106 wd:Q169470 ; wikibase:sitelinks ?n .
  ?a schema:about ?p ; schema:isPartOf <https://ja.wikipedia.org/> ;
     schema:name ?title .
  FILTER(?n >= {MIN_SITELINKS})
}}"""


def main() -> int:
    data = sparql(QUERY)
    titles = sorted({b["title"]["value"] for b in data["results"]["bindings"]})
    if not 800 <= len(titles) <= 4000:
        print(f"error: implausible physicist count: {len(titles)}", file=sys.stderr)
        return 1

    old_rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    existing = {r["original"] for r in old_rows}

    candidates = [t for t in titles
                  if DISAMBIG.sub("", t).replace("　", "").replace(" ", "") not in existing]
    extracts = fetch_extracts(candidates)

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
        # 既存の規約: 日本人名の読みはひらがな、カタカナ名はそのまま
        if not KATAKANA.match(original):
            f_y = f_y.translate(KATA2HIRA)
            full_y = (f_y + g_y.translate(KATA2HIRA))
            full_s = original
        rows = []
        if f_s and f_s != full_s:
            rows.append((f_s, f_y, "family"))
        rows.append((full_s, full_y, "full"))
        for surface, pron, typ in rows:
            added.append({"id": str(next_id), "original": original,
                          "surface": surface, "pronunciation": pron, "type": typ})
        print(f"added: {original}")
        next_id += 1

    cols = ["id", "original", "surface", "pronunciation", "type"]
    write_csv_no_trailing_newline(CSV_PATH, cols, old_rows + added)

    print(f"physicist.csv: +{len({r['id'] for r in added})}人 ({len(added)}行), "
          f"要確認 {len(flagged)}")
    for t in flagged:
        print(f"  要確認: {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
