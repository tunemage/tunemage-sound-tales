"""コード記号 (例: "C Am F# Bb") → 構成音(MIDIノート番号)への変換。CLIには依存しない。

対応記法: ルート(A-G, 任意で # か b を1つ) + 任意の m(マイナー)。例: C, Am, F#, Bbm
それ以外 (7th, dim, sus, onコード, 小文字, 'min' など) は推測せずエラーにする。

音の並びは、ルートが C4(60)〜B4(71) の範囲に来る基本形の3和音(ルート・3度・5度)。
"""
import re
from typing import NamedTuple

NOTE_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
ROOT_OCTAVE_BASE = 60          # C4。ルートは 60 + (0〜11)
MAJOR_THIRD, MINOR_THIRD, FIFTH = 4, 3, 7

_CHORD_RE = re.compile(r"^([A-G])([#b]?)(m?)$")
SUPPORTED = "ルート(A-G) + 任意の # または b + 任意の m(マイナー)。例: C, Am, F#, Bbm"


class ChordParseError(ValueError):
    """コード指定が不正または未対応のときに投げる。メッセージはそのままユーザーに見せられる。"""


class Chord(NamedTuple):
    symbol: str          # 入力どおりの表記 (例: "Am")
    pitches: list[int]   # 構成音 (低い順)


def parse_chord(symbol: str) -> Chord:
    match = _CHORD_RE.match(symbol)
    if not match:
        raise ChordParseError(
            f"コード '{symbol}' は解釈できません。現在対応しているのは {SUPPORTED} だけです"
            "(7th・dim・sus・onコード・小文字などは未対応)。"
        )
    letter, accidental, minor = match.groups()
    semitone = NOTE_SEMITONES[letter] + {"#": 1, "b": -1, "": 0}[accidental]
    root = ROOT_OCTAVE_BASE + semitone % 12
    third = MINOR_THIRD if minor else MAJOR_THIRD
    return Chord(symbol, [root, root + third, root + FIFTH])


def parse_progression(text: str) -> list[Chord]:
    """空白区切りのコード進行 ("C Am F G") を Chord のリストにする。"""
    symbols = text.split()
    if not symbols:
        raise ChordParseError("コード進行が空です。例: \"C Am F G\"")
    return [parse_chord(symbol) for symbol in symbols]
