#!/usr/bin/env python3
"""plant.csv(植物の和名)に未収録の種を追記する(既存行は書き換えない)。

出典: Wikidata(taxon, rank=種 Q7432, 日本語ラベル)。ライセンスは CC0。
sekitsui.csv(脊椎動物)と同じ設計。和名(surface)がそのまま読み
(pronunciation)になるので読み抽出は不要。日本語ラベルがカタカナのものだけを
対象にする。

- `class` 列に大分類(双子葉/単子葉/裸子植物/シダ植物/コケ植物/藻類)を持たせる。
  被子植物は数十万種と巨大で一括クエリすると WDQS がタイムアウトするため、
  **目(order)ごとに分割**して取得する。被子植物の目一覧は実行時に Wikidata から
  取得し、単子葉植物 Q78961 配下の目を「単子葉」、それ以外の被子植物の目を
  「双子葉」に分類する(双子葉は多系統だが、伝統的な2分類として運用)
- 非被子植物(裸子/シダ/コケ/藻類)は正式な門・綱の QID を直接指定して取得する。
  コケ・藻類は非公式グループ(bryophyte Q29993 / algae Q37868)が P171 の親
  タクソンにならないため、門ごと(蘚類/苔類/ツノゴケ類、紅藻/緑藻/褐藻/珪藻/
  車軸藻)に分けて束ねる
- 化石種・絶滅種(rank=種で登録されているもの)も対象に含め、`extinct` 列
  (yes/no)で区別する。判定は sekitsui と同じ(IUCN絶滅/野生絶滅、または化石
  タクソン Q23038290)

usage: python3 tools/update_plant.py
"""

import csv
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wpnames import sparql, write_csv_no_trailing_newline

CSV_PATH = Path(__file__).resolve().parent.parent / "plant.csv"

SPECIES = "wd:Q7432"   # taxon rank = 種
ORDER = "wd:Q36602"    # taxon rank = 目
ANGIOSPERM = "Q25314"  # 被子植物
MONOCOTS = "Q78961"    # 単子葉植物

# 非被子植物: 正式な門・綱QID -> class列の大分類。非公式グループ(コケ植物
# Q29993 / 藻類 Q37868)は P171 の親にならないので門ごとに分ける
CLADES = {
    "Q133712": "裸子植物",   # 裸子植物 Gymnospermae
    "Q178249": "シダ植物",   # シダ植物 Pteridophyta
    "Q157819": "シダ植物",   # ヒカゲノカズラ植物 Lycophyta
    "Q25347": "コケ植物",    # 蘚類 Bryophyta
    "Q189808": "コケ植物",   # 苔類 Marchantiophyta
    "Q191156": "コケ植物",   # ツノゴケ類 Anthocerotophyta
    "Q103169": "藻類",       # 紅藻 Rhodophyta
    "Q264543": "藻類",       # 緑藻 Chlorophyta
    "Q184573": "藻類",       # 褐藻 Phaeophyceae
    "Q9642991": "藻類",      # 珪藻 Bacillariophyta
    "Q133219": "藻類",       # 車軸藻 Charophyta
}

KATAKANA = re.compile(r"^[ァ-ヶー・]+$")
UNKNOWN = "NA"          # 分類が引けなかった既存行の class
# 収集総数がこれを下回ったら取得失敗とみなして中断する(妥当性ガード)。
# 実測は被子植物 6,025 + 裸子/シダ/コケ/藻類 で計 約6,500種
MIN_TOTAL = 4000


def fetch_orders(parent: str) -> set:
    """parent(被子植物/単子葉)配下の rank=目 の QID 集合。"""
    query = f"""
SELECT DISTINCT ?o WHERE {{
  ?o wdt:P171* wd:{parent} ; wdt:P105 {ORDER} .
}}"""
    data = sparql(query)
    return {b["o"]["value"].rsplit("/", 1)[-1]
            for b in data["results"]["bindings"]}


def fetch_taxa(qid: str) -> dict:
    """QID配下の種(カタカナ和名) -> 絶滅フラグ(bool)。絶滅は IUCN(P141)が
    絶滅種/野生絶滅、または instance of(P31)が化石タクソンのいずれか。
    sekitsui.update_sekitsui.fetch_taxa と同じ。"""
    query = f"""
SELECT DISTINCT ?l (BOUND(?ext) AS ?extinct) WHERE {{
  ?t wdt:P171* wd:{qid} ; wdt:P105 {SPECIES} ; rdfs:label ?l .
  FILTER(LANG(?l) = "ja")
  OPTIONAL {{ ?t wdt:P141 ?i . FILTER(?i IN (wd:Q237350, wd:Q239509)) }}
  OPTIONAL {{ ?t wdt:P31 ?f . FILTER(?f = wd:Q23038290) }}
  BIND(COALESCE(?i, ?f) AS ?ext)
}}"""
    data = sparql(query)
    result = {}
    for b in data["results"]["bindings"]:
        name = b["l"]["value"]
        if not KATAKANA.match(name):
            continue
        ext = b["extinct"]["value"] == "true"
        result[name] = result.get(name, False) or ext
    return result


def main() -> int:
    # 被子植物の目を実行時に取得し、単子葉/双子葉に振り分ける
    monocot_orders = fetch_orders(MONOCOTS)
    all_orders = fetch_orders(ANGIOSPERM)
    print(f"被子植物の目: {len(all_orders)}(うち単子葉 {len(monocot_orders)})")

    # (QID, class) の取得対象リスト
    targets = []
    for o in sorted(all_orders):
        targets.append((o, "単子葉" if o in monocot_orders else "双子葉"))
    targets.extend(CLADES.items())

    name_cat = {}   # カタカナ和名 -> 大分類(先勝ち)
    name_ext = {}   # カタカナ和名 -> 絶滅フラグ(いずれかで絶滅なら絶滅)
    for qid, cat in targets:
        taxa = fetch_taxa(qid)
        for n, e in taxa.items():
            name_cat.setdefault(n, cat)
            name_ext[n] = name_ext.get(n, False) or e
        print(f"{cat}({qid}): カタカナ和名 {len(taxa)}, "
              f"うち絶滅 {sum(taxa.values())}")
        time.sleep(1)  # WDQSへの連続アクセスを避ける(取得対象は70件超)

    if len(name_cat) < MIN_TOTAL:
        print(f"error: implausible taxa count: {len(name_cat)}", file=sys.stderr)
        return 1

    def ext_str(name: str) -> str:
        return "yes" if name_ext.get(name) else "no"

    cols = ["id", "original", "surface", "pronunciation", "class", "extinct"]
    if CSV_PATH.exists():
        old_rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    else:
        old_rows = []
    na = 0
    for r in old_rows:
        r["class"] = name_cat.get(r["original"], UNKNOWN)
        r["extinct"] = ext_str(r["original"])
        if r["class"] == UNKNOWN:
            na += 1
    existing = {r["original"] for r in old_rows}
    next_id = (max(int(r["id"]) for r in old_rows) + 1) if old_rows else 0

    added = []
    for name in sorted(name_cat.keys() - existing):
        added.append({"id": str(next_id), "original": name, "surface": name,
                      "pronunciation": name, "class": name_cat[name],
                      "extinct": ext_str(name)})
        next_id += 1

    write_csv_no_trailing_newline(CSV_PATH, cols, old_rows + added)
    print(f"plant.csv: +{len(added)}種 (計 {len(old_rows) + len(added)}行), "
          f"既存の分類不明(NA) {na}行, "
          f"絶滅 {sum(1 for n in name_cat if name_ext.get(n))}種")
    return 0


if __name__ == "__main__":
    sys.exit(main())
