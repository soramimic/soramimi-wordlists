"""
このスクリプトは、最新の野球選手表の更新内容と現在のデータファイルの差分を、
現在のデータファイルにコピペしやすい形式で出力します。
新しい生データファイル（csv）と現在の整形済みデータファイル（csv）を読み込み、
各レコードに新しいIDを割り当て、名前の分割やふりがなの変換を行い、最終的に整形されたデータをCSVファイルとして出力します。

主な処理の流れは以下の通りです：
1. コマンドライン引数からファイルパスを取得します。
2. 新しい生データファイルと現在の整形済みデータファイルを読み込み、以下の条件でフィルタリングを行います：
    - 新しい生データファイルの「氏名」列が、現在の整形済みデータファイルの「original」列に存在しないレコードを抽出します。
3. 現在の整形済みデータの最大IDを取得し、新しいIDの開始値を決定します。
4. 新しいデータに対して新しいIDを生成し、各レコードに割り当てます。
5. 名前の分割やふりがなの変換を行い、整形されたデータを生成します。
6. 整形されたデータをCSVファイルとして出力します。
"""

import argparse
import re
from dataclasses import dataclass

import jaconv
import neologdn
import pandas as pd
import sudachipy
from namedivider import BasicNameDivider


# 姓名分離するためのクラス
@dataclass
class DividedName:
    family: str
    given: str
    score: float
    algorithm: str


@dataclass
class TidyRow:
    id: int | str
    original: str
    team: str
    surface: str
    pronunciation: str
    type: str
    org_id: int | str
    score: float
    note: str | None


class NameDividerWrapper:
    def __init__(self, *, sep: str = "・"):
        self.name_divider = BasicNameDivider()
        self.sep = sep

    def divide_japanese_name(self, name: str) -> DividedName:
        divided_name_dict = self.name_divider.divide_name(name).to_dict()
        divided_name = DividedName(
            family=divided_name_dict["family"],
            given=divided_name_dict["given"],
            score=float(divided_name_dict["score"]),
            algorithm=divided_name_dict["algorithm"],
        )
        return divided_name

    def divide_foreign_name(self, name: str) -> DividedName:
        family = name.split(self.sep)[-1]
        given = self.sep.join(name.split(self.sep)[:-1])
        # sepが複数含まれていたらscoreを下げる
        score = 1 / (len(name.split(self.sep)) - 1)
        return DividedName(
            family=family, given=given, score=score, algorithm="foreign_rule"
        )

    def divide_name(self, name: str) -> DividedName:
        if len(name) == 1:
            return DividedName(
                family=name, given="", score=1, algorithm="one_char_rule"
            )
        elif self.sep in name:
            return self.divide_foreign_name(name)
        else:
            return self.divide_japanese_name(name)


class TokenizerWrapper:
    def __init__(self):
        self.tokenizer = sudachipy.Dictionary(dict="full").create()
        alphabet_and_numbers = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        alphabet_and_numbers_pronunciation = "エー・ビー・シー・ディー・イー・エフ・ジー・エイチ・アイ・ジェー・ケー・エル・エム・エヌ・オー・ピー・キュー・アール・エス・ティー・ユー・ブイ・ダブリュー・エックス・ワイ・ゼット・ゼロ・イチ・ニ・サン・ヨン・ゴ・ロク・ナナ・ハチ・キュー".split(
            "・"
        )

        # 変換辞書を作りたいとき
        self.alphabet_and_numbers_to_pronunciation = {
            s: p
            for s, p in zip(alphabet_and_numbers, alphabet_and_numbers_pronunciation)
        }

    def get_reading_form(self, text: str) -> str:
        mode = sudachipy.Tokenizer.SplitMode.C
        tokens = self.tokenizer.tokenize(text, mode)
        reading_form = ""
        for token in tokens:
            if token.part_of_speech()[0] == "助詞" and token.surface() == "は":
                reading_form += "ワ"
            elif token.part_of_speech()[0] == "助詞" and token.surface() == "へ":
                reading_form += "エ"
            elif token.surface() in self.alphabet_and_numbers_to_pronunciation:
                reading_form += self.alphabet_and_numbers_to_pronunciation[
                    token.surface()
                ]
            elif token.part_of_speech()[0] in ["記号", "補助記号"]:
                pass
            else:
                reading_form += token.reading_form()
        return reading_form


def load_and_filter_data(
    new_raw_file: str, current_tidy_file: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    新しい生データファイルと現在の整頓されたデータファイルを読み込み、現在のデータに存在しない新しいレコードをフィルタリングして返す関数。

    Parameters:
    new_raw_file (str): 新しい生データファイルのパス
    current_tidy_file (str): 現在の整頓されたデータファイルのパス

    Returns:
    pd.DataFrame: フィルタリングされた新しいレコードを含むデータフレーム
    """
    df_new_raw = pd.read_csv(new_raw_file)
    df_new_raw["氏名"] = df_new_raw["氏名"].map(neologdn.normalize)
    df_current_tidy = pd.read_csv(current_tidy_file)
    df_current_tidy["original"] = df_current_tidy["original"].map(neologdn.normalize)

    original_set = set(df_current_tidy["original"])
    df_new_filtered = df_new_raw[
        ~df_new_raw["氏名"].map(neologdn.normalize).isin(original_set)
    ]
    return df_new_raw, df_current_tidy, df_new_filtered


# nameをカッコでバラす関数を定義
def split_name_by_parentheses(name: str) -> list[str]:
    """
    名前をカッコで分割する関数

    例:
    入力: "ワォーターズ璃海ジュミル(ワォーターズ)"
    出力: ["ワォーターズ璃海ジュミル", "ワォーターズ"]

    入力: "クリスチャン・ロドリゲス"
    出力: ["クリスチャン・ロドリゲス"]

    Args:
        name (str): 分割する名前

    Returns:
        list[str]: 分割された名前のリスト
    """
    # 全角カッコを半角にする
    name = name.translate(str.maketrans("（）", "()"))
    # スペース削除
    name = "".join(name.split())
    # カッコでスプリット
    name_list = re.split("[()]", name)
    # 空の要素を削除
    name_list = [x for x in name_list if x]
    return name_list


def generate_new_ids(df_new_filtered: pd.DataFrame, start_id: int) -> list[int]:
    """
    新しいIDを生成する関数

    この関数は、フィルタリングされた新しいデータフレームを受け取り、
    各レコードに対して新しいIDを生成します。IDは指定された開始IDから
    順に割り当てられます。同じ名前のレコードには同じIDが割り当てられます。

    Args:
        df_new_filtered (pd.DataFrame): フィルタリングされた新しいデータフレーム
        start_id (int): 新しいIDの開始値

    Returns:
        list[int]: 各レコードに対応する新しいIDのリスト
    """
    new_ids = []
    current_id = start_id
    done = {}
    for idx, row in df_new_filtered.iterrows():
        name = row["氏名"]
        # カッコで分割した名前をソートした結果が同一のものは同じIDを割り当てる
        formatted_name = split_name_by_parentheses(name)
        name_tuple = tuple(sorted(formatted_name))
        if name_tuple not in done:
            done[name_tuple] = current_id
        new_ids.append(done[name_tuple])
        current_id += 1
    return new_ids


def main():
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(description="Process baseball data files.")
    parser.add_argument(
        "--new_raw_file", "-n", type=str, help="Path to the new raw file"
    )
    parser.add_argument(
        "--current_tidy_file", "-c", type=str, help="Path to the current tidy file"
    )
    parser.add_argument(
        "--output_file",
        "-o",
        type=str,
        help="Path to the output file",
        default="data/output.csv",
    )
    args = parser.parse_args()

    NEW_RAW_FILE = args.new_raw_file
    CURRENT_TIDY_FILE = args.current_tidy_file
    OUTPUT_FILE = args.output_file

    _, df_current_tidy, df_new_filtered = load_and_filter_data(
        NEW_RAW_FILE, CURRENT_TIDY_FILE
    )

    current_max_id = max(int(id) for id in df_current_tidy["id"] if id.isdigit())
    start_id = current_max_id + 1

    new_ids = generate_new_ids(df_new_filtered, start_id)

    df_new_filtered["id"] = new_ids

    name_divider = NameDividerWrapper()
    tokenizer = TokenizerWrapper()

    new_tidy_rows = []

    for idx, row in df_new_filtered.iterrows():
        name = row["氏名"]
        # フルネーム　ふりがな,フルネーム　フリガナ,姓　フリガナ,名　フリガナ,姓
        full_kana = (
            ""
            if pd.isna(row["フルネーム　ふりがな"])
            else jaconv.hira2kata(row["フルネーム　ふりがな"])
        )
        full_kana = "".join(full_kana.split())
        family_kana = (
            ""
            if pd.isna(row["姓　フリガナ"])
            else jaconv.hira2kata(row["姓　フリガナ"])
        )
        given_kana = (
            ""
            if pd.isna(row["名　フリガナ"])
            else jaconv.hira2kata(row["名　フリガナ"])
        )

        first_name = split_name_by_parentheses(name)[0]
        divided_name = name_divider.divide_name(first_name)
        if family_kana:
            if full_kana:
                reading_form = tokenizer.get_reading_form(divided_name.family)
                note = None
                if family_kana != reading_form:
                    note = "please check"  # , {family_kana} != {reading_form}"
                if not divided_name.family:
                    note = "please check"
                new_tidy_rows.append(
                    TidyRow(
                        id=row["id"],
                        original=name,
                        team=row["球団"],
                        surface=divided_name.family,
                        pronunciation=family_kana,
                        # 野球選手表のフォーマット上、登録名の行はフルネームのふりがなが空欄のため。
                        type="family",
                        org_id=row["id"],
                        score=divided_name.score,
                        note=note,
                    )
                )
            # full_kanaが空欄の場合は登録名の行として扱う
            else:
                new_tidy_rows.append(
                    TidyRow(
                        id=row["id"],
                        original=name,
                        team=row["球団"],
                        surface=first_name,
                        pronunciation=family_kana,
                        type="registered",
                        org_id=row["id"],
                        score=1,
                        note=None,
                    )
                )

        if given_kana:
            reading_form = tokenizer.get_reading_form(divided_name.given)
            note = None
            if given_kana != reading_form:
                note = "please check"  # , {given_kana} != {reading_form}"
            if not divided_name.given:
                note = "please check"
            new_tidy_rows.append(
                TidyRow(
                    id=row["id"],
                    original=name,
                    team=row["球団"],
                    surface=divided_name.given,
                    pronunciation=given_kana,
                    type="given",
                    org_id=row["id"],
                    score=divided_name.score,
                    note=note,
                )
            )
        if full_kana:
            reading_form = tokenizer.get_reading_form(first_name)
            note = None
            if full_kana != reading_form:
                note = "please check"  # , {full_kana} != {reading_form}"
            new_tidy_rows.append(
                TidyRow(
                    id=row["id"],
                    original=name,
                    team=row["球団"],
                    surface=first_name,
                    pronunciation=full_kana,
                    type="full",
                    org_id=row["id"],
                    score=1,
                    note=note,
                )
            )
    pd.DataFrame(new_tidy_rows).to_csv(OUTPUT_FILE, index=False)


if __name__ == "__main__":
    main()
