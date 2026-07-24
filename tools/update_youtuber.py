#!/usr/bin/env python3
"""youtuber.csv を生成・追記する(詳細は docs/adr/00011)。

対象: Wikidataの職業(P106)が YouTuber(Q17125263)で、ja.wikipediaに記事が
ある人物。バーチャルYouTuber(Q58471517)を併せ持つ者は vtuber.csv 側に
収録するため除外する。収録は記事名(=活動名)のみで、本名は取得しない。

環境変数 YOUTUBER_CACHE を指定すると取得結果をpickleキャッシュする(開発用)。

usage: python3 tools/update_youtuber.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yt_common import build_list

if __name__ == "__main__":
    sys.exit(build_list(
        csv_name="youtuber.csv",
        occ="Q17125263",                      # YouTuber
        must=("youtuber", "ユーチューバー"),
        must_not=("virtual", "バーチャル"),   # VTuberのQIDと取り違えたら中断
        exclude="Q58471517",                  # バーチャルYouTuberは除外
        guard=(200, 20000),
        cache_env="YOUTUBER_CACHE",
    ))
