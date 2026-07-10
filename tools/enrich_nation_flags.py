#!/usr/bin/env python3
"""nations.csv に国旗画像(Wikimedia Commons)を付与する。

nations_map.csv(cca3 -> id)で管理された ISO 3166-1 alpha-3 コードから
Wikidata(P298=cca3, P41=国旗)を引き、各国の image / image_page / wikidata を埋める。
コンゴ(COG/COD)・ギニア(GIN/GNQ=赤道ギニア)など同名別国も cca3 で確実に区別できる。

- 既存の image が空の行だけ埋める(冪等)。original/surface/status は変更しない。
- 画像は現行旗(Wikidata P41 のtruthy値)。アフガニスタン等は現政府の旗になる点に注意。
- URLフォーマットと末尾改行なしは wpnames のヘルパに合わせる。

usage: python3 tools/enrich_nation_flags.py
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wpnames import sparql, write_csv_no_trailing_newline  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "nations.csv"
MAP_PATH = ROOT / "tools" / "nations_map.csv"
COLS = ["id", "original", "surface", "status", "image", "image_page", "wikidata"]
MIN_EXPECTED = 180  # 主権国家の国旗はこれ以上取れるはず。下回ったらWDQS部分応答とみなす


def cca3_to_flag() -> dict[str, tuple[str, str, str]]:
    """ISO 3166-1 alpha-3(P298) -> (qid, image_url, image_page)。

    国旗(P41)とcca3(P298)を持ち、主権国家(Q3624078)または国(Q6256)である
    itemに限定して、cca3・国旗・QIDを1本のSPARQLで取る(2段階呼び出しはWDQSの
    部分応答で国が抜けるため一発にする。デンマークのようにP31がQ6256のみの国も
    拾うため両方許可)。ファイル名の空白は _ に、その他(カンマ等)は %エンコードの
    ままにして image/image_page を組む(素朴なCSVパーサを壊さない)。
    """
    data = sparql(
        "SELECT ?c ?cca3 ?flag WHERE { "
        "VALUES ?type { wd:Q3624078 wd:Q6256 } "
        "?c wdt:P31 ?type; wdt:P298 ?cca3; wdt:P41 ?flag }"
    )
    bindings = data["results"]["bindings"]
    if len(bindings) < MIN_EXPECTED:
        raise RuntimeError(
            f"WDQSの応答が少なすぎます({len(bindings)}件)。部分応答の可能性。再実行してください"
        )
    out: dict[str, tuple[str, str, str]] = {}
    for b in bindings:
        cca3 = b["cca3"]["value"]
        if cca3 in out:
            continue  # 同一cca3に複数(旧旗item等)が来たら先勝ち
        qid = b["c"]["value"].rsplit("/", 1)[-1]
        fname = b["flag"]["value"].rsplit("/", 1)[-1].replace("%20", "_")
        out[cca3] = (
            qid,
            "http://commons.wikimedia.org/wiki/Special:FilePath/" + fname,
            "https://commons.wikimedia.org/wiki/File:" + fname,
        )
    return out


def main() -> int:
    id_to_cca3 = {}
    with open(MAP_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            id_to_cca3[row["id"]] = row["cca3"]

    cca3_flag = cca3_to_flag()

    with open(CSV_PATH, encoding="utf-8") as f:
        rows = [dict(r) for r in csv.DictReader(f)]

    filled = 0
    missing = []
    for r in rows:
        for c in COLS:
            r.setdefault(c, "")
        if r.get("image"):
            continue  # 既に画像がある行は触らない(冪等)
        hit = cca3_flag.get(id_to_cca3.get(r["id"], ""))
        if hit:
            r["wikidata"], r["image"], r["image_page"] = hit
            filled += 1
        else:
            missing.append(f"{r['id']}:{r['original']}")

    write_csv_no_trailing_newline(CSV_PATH, COLS, rows)
    print(f"国旗を付与: {filled}/{len(rows)}")
    if missing:
        print("画像なし:", missing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
