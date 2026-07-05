#!/usr/bin/env python3
"""nations.csv を国連加盟国リストと突き合わせて差分更新する。

出典: https://github.com/mledoze/countries (countries.json, CC BY-SA 4.0)

nations.csv の表記は独自の通称(アメリカ、グルジア等)なので、既存行の
original/surface は一切書き換えない。tools/nations_map.csv(ISOコード
cca3 -> id)で対応を管理し:
- マップにない新規加盟国は末尾に追記(status=current)
- 加盟国でなくなった国は該当行の status を former に変更
- 別名・旧称は同じidの行を手動で追加してよい(status列で現行かどうかを示す)

usage: python3 tools/update_nations.py
"""

import csv
import json
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/mledoze/countries/master/countries.json"
)
# mledozeのデータはバチカン(オブザーバー)をunMember扱いにしているので除外
NOT_ACTUALLY_UN_MEMBERS = {"VAT"}
# 加盟国が一度に大きく増減したらソースデータの異常とみなして中断する
MAX_CHANGES = 5

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "nations.csv"
MAP_PATH = ROOT / "tools" / "nations_map.csv"


def main() -> int:
    with urllib.request.urlopen(SOURCE_URL, timeout=60) as res:
        countries = json.load(res)

    un = {
        c["cca3"]: c["translations"]["jpn"]["common"]
        for c in countries
        if c.get("unMember") and c["cca3"] not in NOT_ACTUALLY_UN_MEMBERS
    }
    if not 180 <= len(un) <= 210:
        print(f"error: implausible UN member count: {len(un)}", file=sys.stderr)
        return 1

    with MAP_PATH.open(encoding="utf-8") as f:
        mapping = {row["cca3"]: row for row in csv.DictReader(f)}
    with CSV_PATH.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row.setdefault("status", "current")

    added = sorted(code for code in un if code not in mapping)
    removed = sorted(code for code in mapping if code not in un)
    if len(added) + len(removed) > MAX_CHANGES:
        print(
            f"error: too many changes (+{len(added)}/-{len(removed)}), "
            "source data looks broken",
            file=sys.stderr,
        )
        return 1

    changed = 0
    # 脱退・消滅した国は former に、(再)加盟国は current に揃える
    member_ids = {mapping[code]["id"] for code in mapping if code in un}
    former_ids = {mapping[code]["id"] for code in removed}
    for row in rows:
        want = "current" if row["id"] in member_ids else (
            "former" if row["id"] in former_ids else row["status"]
        )
        if row["status"] != want:
            print(f"status: {row['surface']} (id={row['id']}) -> {want}")
            row["status"] = want
            changed += 1

    old_count = len(rows)
    next_id = max(int(r["id"]) for r in rows) + 1
    for code in added:
        name = un[code]
        rows.append(
            {"id": str(next_id), "original": name, "surface": name,
             "status": "current"}
        )
        mapping[code] = {"cca3": code, "id": str(next_id), "original": name}
        print(f"added: {code} {name} (id={next_id})")
        next_id += 1

    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["id", "original", "surface", "status"])
        for row in rows:
            writer.writerow([row["id"], row["original"], row["surface"],
                             row["status"]])

    if added:
        with MAP_PATH.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(["cca3", "id", "original"])
            for code in sorted(mapping):
                row = mapping[code]
                writer.writerow([row["cca3"], row["id"], row["original"]])

    print(
        f"nations.csv: {old_count} -> {len(rows)} rows "
        f"(+{len(added)} added, {changed} status changed)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
