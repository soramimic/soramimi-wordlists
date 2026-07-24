#!/usr/bin/env python3
"""vtuber.csv を生成・追記する(詳細は docs/adr/00011)。

対象: Wikidataの職業(P106)が バーチャルYouTuber(Q55155641)で、ja.wikipediaに
記事がある人物(キャラクター)。国内・海外(ホロライブEN/ID等)は区別しない。
所属(org)・活動開始年(debut_year)・status(current/former)を付与する。

環境変数 VTUBER_CACHE を指定すると取得結果をpickleキャッシュする(開発用)。

usage: python3 tools/update_vtuber.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yt_common import build_list

if __name__ == "__main__":
    sys.exit(build_list(
        csv_name="vtuber.csv",
        occ="Q55155641",                      # バーチャルYouTuber
        must=("virtual", "バーチャル"),       # QID取り違えのフェイルセーフ
        must_not=(),
        exclude=None,
        guard=(100, 10000),
        cache_env="VTUBER_CACHE",
    ))
