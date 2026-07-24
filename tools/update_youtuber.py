#!/usr/bin/env python3
"""youtuber.csv を生成・追記する(詳細は docs/adr/00011, 00012)。

対象: Wikidataの職業(P106)が YouTuber(Q17125263)または
バーチャルYouTuber(Q55155641)で、ja.wikipediaに記事がある人物。
category列(youtuber/vtuber)で区別し、両方の職業を持つ者は vtuber とする。
収録は記事名(=活動名)のみで、本名は取得しない。

環境変数 YOUTUBER_CACHE を指定すると取得結果をpickleキャッシュする(開発用)。

usage: python3 tools/update_youtuber.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yt_common import build_list

SPECS = [
    dict(category="youtuber",
         occ="Q17125263",                     # YouTuber
         must=("youtuber", "ユーチューバー"),
         must_not=("virtual", "バーチャル"),  # VTuberのQIDと取り違えたら中断
         exclude="Q55155641",                 # バーチャルYouTuberはvtuber側
         guard=(200, 20000)),
    dict(category="vtuber",
         occ="Q55155641",                     # バーチャルYouTuber
         must=("virtual", "バーチャル"),      # QID取り違えのフェイルセーフ
         must_not=(),
         exclude=None,
         guard=(100, 10000)),
]

if __name__ == "__main__":
    sys.exit(build_list("youtuber.csv", SPECS, "YOUTUBER_CACHE"))
