"""人名リスト自動更新の共通処理(Wikipedia/Wikidata)。

- 記事冒頭文「姓 名(せい めい、…」から姓名分割済みの読みを取る
- 「本名:姓 名〈せい めい〉」パターン(登録名が記事名の場合)に対応
- 台湾選手等の「姓 名(カタカナ・カタカナ、」にも対応
- 異体字(髙/高等)は照合時のみ正規化する
"""

import json
import re
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "soramimi-wordlists-updater/1.0 (https://github.com/soramimic/soramimi-wordlists)"}
WP_API = "https://ja.wikipedia.org/w/api.php"
WDQS = "https://query.wikidata.org/sparql"

DISAMBIG = re.compile(r"\s+\([^)]*\)$")
KATAKANA = re.compile(r"^[ァ-ヶー・=＝\s]+$")
KANJI = r"一-龠々〆豈-﫿ぁ-ゖァ-ヶーA-Za-z"
KANA = r"ぁ-ゖァ-ヶー"
HIRA2KATA = str.maketrans({chr(k): chr(k + 0x60) for k in range(ord("ぁ"), ord("ゖ") + 1)})
KATA2HIRA = str.maketrans({chr(k): chr(k - 0x60) for k in range(ord("ァ"), ord("ヶ") + 1)})
VARIANT = str.maketrans("髙﨑濵濱邉邊瀨栁眞", "高崎浜浜辺辺瀬柳真")
LINK = re.compile(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]")


def vnorm(s: str) -> str:
    return s.translate(VARIANT)


def api(params: dict) -> dict:
    url = WP_API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as res:
                return json.load(res)
        except Exception as ex:
            print(f"retry {attempt}: {ex}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("wikipedia api failed")


def sparql(query: str) -> dict:
    url = WDQS + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url, headers={**UA, "Accept": "application/sparql-results+json"})
            with urllib.request.urlopen(req, timeout=120) as res:
                return json.load(res)
        except Exception as ex:
            print(f"WDQS retry {attempt}: {ex}")
            time.sleep(70)
    raise RuntimeError("wdqs failed")


def template_wikitext(title: str):
    data = api({"action": "query", "prop": "revisions", "rvprop": "content",
                "rvslots": "main", "titles": title})
    page = next(iter(data["query"]["pages"].values()))
    if "revisions" not in page:
        return None
    return page["revisions"][0]["slots"]["main"]["*"]


def fetch_extracts(titles: list, limit: int = 200) -> dict:
    """記事タイトル -> 冒頭文(先頭limit文字)"""
    extracts = {}
    for i in range(0, len(titles), 20):
        data = api({"action": "query", "prop": "extracts", "exintro": 1,
                    "explaintext": 1, "exlimit": "max", "redirects": 1,
                    "titles": "|".join(titles[i:i + 20])})
        redir = {r["to"]: r["from"] for r in data["query"].get("redirects", [])}
        for p in data["query"]["pages"].values():
            orig = redir.get(p["title"], p["title"])
            extracts[orig] = p.get("extract", "")[:limit]
        time.sleep(0.5)
    return extracts


def parse_person(name: str, text: str):
    """記事名と冒頭文から (family_s, family_y, given_s, given_y, full_s, full_y,
    registered) を返す。読みはカタカナ。registered は記事名が登録名だった場合の
    登録名(通常None)。解析できなければ None。"""
    text = text.replace("　", " ")
    plain = name.replace(" ", "")
    if KATAKANA.match(plain):
        parts = [x for x in re.split(r"[・=＝\s]", name) if x]
        fam = parts[-1] if len(parts) >= 2 else None
        giv = parts[0] if len(parts) >= 2 else None
        full_y = name.replace("＝", "・").replace(" ", "・")
        return (fam, fam, giv, giv, name, full_y, None)
    # 記事名=登録名で本名が別記載(大勢、愛斗など)。コロンは全半角
    m = re.search(r"本名[:：]\s*([" + KANJI + r"]+)[  ]+([" + KANJI + r"]+)"
                  r"\s*[〈（(]\s*([" + KANA + r"]+)[  ]+([" + KANA + r"]+)", text)
    if m:
        f_s, g_s, f_y, g_y = m.groups()
        return (f_s, f_y.translate(HIRA2KATA), g_s, g_y.translate(HIRA2KATA),
                f_s + g_s, (f_y + g_y).translate(HIRA2KATA), name)
    # 通常: 姓 名(せい めい、または 姓 名(カタカナ・カタカナ(台湾人名等)
    m = re.match(r"^([" + KANJI + r"]+)[  ]+([" + KANJI + r"]+)\s*[（(]\s*"
                 r"([" + KANA + r"]+)[  ・]+([" + KANA + r"]+)", text)
    if m and vnorm(plain) == vnorm(m.group(1) + m.group(2)):
        f_s, g_s, f_y, g_y = m.groups()
        return (f_s, f_y.translate(HIRA2KATA), g_s, g_y.translate(HIRA2KATA),
                f_s + g_s, (f_y + g_y).translate(HIRA2KATA), None)
    # ウェード式などが先に来る場合: 括弧内のカタカナ・カタカナを読みとする
    m = re.match(r"^([" + KANJI + r"]+)[  ]+([" + KANJI + r"]+)\s*[（(]", text)
    if m and vnorm(plain) == vnorm(m.group(1) + m.group(2)):
        m2 = re.search(r"([ァ-ヶー]+)・([ァ-ヶー]+)", text[:150])
        if m2:
            return (m.group(1), m2.group(1), m.group(2), m2.group(2),
                    m.group(1) + m.group(2), m2.group(1) + m2.group(2), None)
    return None


def write_csv_no_trailing_newline(path, cols, rows):
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    w = _csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    # 末尾改行なしで書く(soramimic側のパーサが最終空行で落ちるため)
    path.write_text(buf.getvalue().rstrip("\n"), encoding="utf-8")
