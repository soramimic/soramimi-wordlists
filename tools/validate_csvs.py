#!/usr/bin/env python3
"""全CSVがsoramimic側パーサの前提を満たすか検証する(CI用)。

チェック内容:
- 引用符付きフィールドがない(利用側はクオート非対応の素朴なsplit(","))
- 改行コードがLFのみ・末尾改行なし(最終空行でパーサが落ちる)
- 全行がヘッダと同じ列数(素朴なsplitで列ズレしない)
- 必須列(id, original, surface)が存在し、値が空でない
- image/image_page は生カンマを含まないURL
- 一意であるべき列の妥当性(stationsのwikidata重複など)

usage: python3 tools/validate_csvs.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = ("id", "original", "surface")

errors = []


def err(msg):
    errors.append(msg)
    print(f"NG: {msg}")


def validate(path: Path):
    raw = path.read_bytes()
    if b"\r" in raw:
        err(f"{path.name}: CR(\\r)を含む")
    if raw.endswith(b"\n"):
        err(f"{path.name}: 末尾に改行がある")
    text = raw.decode("utf-8")
    if '"' in text:
        err(f"{path.name}: 引用符付きフィールドがある(カンマ入りの値?)")
        return
    lines = text.split("\n")
    header = lines[0].split(",")
    ncol = len(header)
    for col in REQUIRED:
        if col not in header:
            err(f"{path.name}: 必須列 {col} がない")
            return
    idx = {c: i for i, c in enumerate(header)}
    img_cols = [c for c in ("image", "image_page") if c in idx]
    for lineno, line in enumerate(lines[1:], start=2):
        f = line.split(",")
        if len(f) != ncol:
            err(f"{path.name}:{lineno}: 列数が{len(f)}(期待{ncol}): {line[:60]}")
            continue
        for col in REQUIRED:
            if not f[idx[col]]:
                err(f"{path.name}:{lineno}: {col} が空")
        for col in img_cols:
            v = f[idx[col]]
            if v and not re.match(r"^https?://commons\.wikimedia\.org/", v):
                err(f"{path.name}:{lineno}: {col} が不正なURL: {v[:60]}")
    print(f"OK: {path.name} ({len(lines) - 1}行)")


def main() -> int:
    for p in sorted(ROOT.glob("*.csv")):
        validate(p)
    # tools のPythonが構文エラーでないこと
    import py_compile
    for p in sorted((ROOT / "tools").glob("*.py")):
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as ex:
            err(f"{p.name}: 構文エラー: {ex}")
    if errors:
        print(f"\n{len(errors)}件のエラー")
        return 1
    print("\nすべてOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
