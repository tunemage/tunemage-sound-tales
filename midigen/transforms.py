"""Pattern を受け取って、変更した新しい Pattern を返す変換。元の Pattern は変更しない。

shift_offbeats: 裏拍(8分の裏)のノートの開始位置を前後にずらす (スイング/レイドバックの実験用)。
"""
import math
from dataclasses import replace

from .model import Note, Pattern, Track

OVERLAP_EPSILON = 1e-9


def is_offbeat(note: Note, beats_per_bar: float) -> bool:
    """小節の頭から数えて x.5 拍の位置(8分音符の裏)にあるか。16分の裏(x.25, x.75)は対象外。"""
    position_in_bar = note.start % beats_per_bar
    return math.isclose(position_in_bar % 1, 0.5, abs_tol=OVERLAP_EPSILON)


def shift_offbeats(pattern: Pattern, amount: float, track_names=None) -> Pattern:
    """裏拍のノートを amount 拍ずらした Pattern を返す。

    amount: 拍単位。正=後ろへ(遅らせる)、負=前へ(早める)。-0.5 < amount < 0.5。
            三連のスイングなら 1/6 拍(約0.1667)。
    track_names: ずらす対象のトラック名 (大文字小文字は区別しない)。None なら全トラック。

    ノートは長さを変えずに丸ごと動かす。ずらした結果、同じ音程のノートと重なる場合は
    手前のノートを次のノートの開始位置までで切る(音が鳴りっぱなしになるのを防ぐため)。
    """
    if not -0.5 < amount < 0.5:
        raise ValueError(f"ずらす量 {amount:g} 拍は範囲外です。-0.5 より大きく 0.5 より小さい値にしてください")

    available = [track.name for track in pattern.tracks]
    targets = set(available) if track_names is None else _match_track_names(track_names, available)

    tracks = [
        _shift_track(track, amount, pattern.beats_per_bar) if track.name in targets else track
        for track in pattern.tracks
    ]
    return replace(pattern, tracks=tracks)


def _match_track_names(requested, available):
    by_lower = {name.lower(): name for name in available}
    unknown = [name for name in requested if name.lower() not in by_lower]
    if unknown:
        raise ValueError(f"トラック {unknown} はこのパターンにありません。指定できるのは {available} です")
    return {by_lower[name.lower()] for name in requested}


def _shift_track(track: Track, amount: float, beats_per_bar: float) -> Track:
    notes = [
        replace(note, start=note.start + amount) if is_offbeat(note, beats_per_bar) else note
        for note in track.notes
    ]
    if notes == track.notes:       # 裏拍のノートがなければ何も変えない
        return track
    return replace(track, notes=_trim_same_pitch_overlaps(notes))


def _trim_same_pitch_overlaps(notes: list[Note]) -> list[Note]:
    """同じ音程で重なったノートを、次のノートの開始位置で切る。同じ位置に重なる場合はエラー。"""
    result = list(notes)
    by_pitch = {}
    for index, note in enumerate(notes):
        by_pitch.setdefault(note.pitch, []).append(index)

    for indices in by_pitch.values():
        indices.sort(key=lambda i: notes[i].start)
        for current, following in zip(indices, indices[1:]):
            note, next_note = notes[current], notes[following]
            gap = next_note.start - note.start
            if gap <= OVERLAP_EPSILON:
                raise ValueError(
                    f"ずらした結果、音程 {note.pitch} のノートが同じ位置({note.start:g}拍)に重なります。"
                    "ずらす量を小さくしてください"
                )
            if note.duration > gap + OVERLAP_EPSILON:
                result[current] = replace(note, duration=gap)
    return result
