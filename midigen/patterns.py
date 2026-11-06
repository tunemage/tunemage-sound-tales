"""音楽パターンの定義。ここだけ編集すれば別のパターンが作れる。

時間の単位は「拍」(4分音符=1拍)。小節内の位置は 0 始まり:
  4/4なら 0=1拍目, 1=2拍目, 2=3拍目, 3=4拍目, 0.5=1拍目の裏, 1.5=2拍目の裏 ...
"""
from .chords import Chord
from .model import Note, Pattern, Track

# ---- General MIDI ドラムノート番号 ----
KICK = 36
SNARE = 38
CLOSED_HAT = 42

# ---- 音名 (C4 = 60 = 真ん中のド) ----
C2, G2 = 36, 43
C4, E4, G4 = 60, 64, 67

BARS = 4
BEATS_PER_BAR = 4          # 4/4 の小節の長さ(拍)。他の拍子のパターンはヘルパーに beats_per_bar を渡す
DRUM_LENGTH = 0.1          # ドラムは音の長さが影響しないので短くしておく

# ---- 各パートの「小節内の」リズム定義 ----
KICK_BEATS = [0, 2]        # 1拍目と3拍目
SNARE_BEATS = [1, 3]       # 2拍目と4拍目
HIHAT_8TH = 0.5            # ハイハットの間隔(拍): 0.5 = 8分音符
HIHAT_16TH = 0.25          # 0.25 = 16分音符

# ベース: (小節内の開始位置, 音程, 長さ) のリスト。1小節ぶんを書けば全小節に繰り返される
BASS_PLAIN = [
    (0, C2, 0.5),
    (1, C2, 0.5),
    (2, G2, 0.5),
    (3, C2, 0.5),
]
# BASS_PLAIN の 2拍目(1) と 4拍目(3) を半拍後ろ(裏拍)へ移動。音程と長さは同じ
BASS_SYNCOPATED = [
    (0, C2, 0.5),
    (1.5, C2, 0.5),
    (2, G2, 0.5),
    (3.5, C2, 0.5),
]

# パターンD (7/8拍子 = 8分音符7つ。2+2+3 に区切る)。小節の長さは 7/8 x 4 = 3.5拍
BEATS_PER_BAR_7_8 = 3.5
KICK_BEATS_7_8 = [0, 2]    # 2+2+3 の1つ目と3つ目のグループの頭
SNARE_BEATS_7_8 = [1, 3]   # 2つ目のグループの頭と、最後の8分
BASS_7_8 = [
    (0, C2, 0.5),          # グループの頭(0, 1, 2)にC・C・G、最後の8分(3)で次の小節へつなぐC
    (1, C2, 0.5),
    (2, G2, 0.5),
    (3, C2, 0.5),
]

CHORD_C_MAJOR = [C4, E4, G4]   # Cメジャー: ド・ミ・ソ


# ---- パーツを組み立てる関数 ----
def _repeat_every_bar(events, bars=BARS, beats_per_bar=BEATS_PER_BAR):
    """1小節ぶんの (位置, 音程, 長さ, ベロシティ) を全小節に展開して Note にする。"""
    return [
        Note(pitch, bar * beats_per_bar + beat, duration, velocity)
        for bar in range(bars)
        for beat, pitch, duration, velocity in events
    ]


def drum_track(hihat_step: float, kick_beats=KICK_BEATS, snare_beats=SNARE_BEATS,
               beats_per_bar=BEATS_PER_BAR) -> Track:
    events = [(b, KICK, DRUM_LENGTH, 110) for b in kick_beats]
    events += [(b, SNARE, DRUM_LENGTH, 105) for b in snare_beats]
    steps = int(beats_per_bar / hihat_step)
    for i in range(steps):
        beat = i * hihat_step
        # 表拍は強め、半拍(8分の裏)は中くらい、それ以外(16分の裏)は弱め
        velocity = 90 if beat % 1 == 0 else 75 if beat % 1 == 0.5 else 60
        events.append((beat, CLOSED_HAT, DRUM_LENGTH, velocity))
    return Track("Drums", _repeat_every_bar(events, BARS, beats_per_bar), is_drum=True)


def bass_track(figure, beats_per_bar=BEATS_PER_BAR) -> Track:
    events = [(beat, pitch, duration, 100) for beat, pitch, duration in figure]
    return Track("Bass", _repeat_every_bar(events, BARS, beats_per_bar), program=33)   # 33 = Electric Bass (finger)


def chord_track(chords=(CHORD_C_MAJOR,), bars=BARS, beats_per_bar=BEATS_PER_BAR) -> Track:
    """1小節に1コード。chords は構成音のリストを小節順に並べたもの(足りなければ先頭から繰り返す)。

    各小節の頭で和音を鳴らし、小節の終わりまで伸ばす。
    """
    notes = [
        Note(pitch, bar * beats_per_bar, beats_per_bar, 80)
        for bar in range(bars)
        for pitch in chords[bar % len(chords)]
    ]
    return Track("Chords", notes, program=0)  # 0 = Acoustic Grand Piano


# ---- パターン定義: A をベースに、B・C は1か所だけ変えている ----
def pattern_a(bpm: float = 120) -> Pattern:
    """基本の8ビート。ハイハット=8分音符。"""
    return Pattern(
        "pattern_a_8beat", bpm, BARS,
        [drum_track(HIHAT_8TH), bass_track(BASS_PLAIN), chord_track()],
    )


def pattern_b(bpm: float = 120) -> Pattern:
    """16ビート。A とのちがいはハイハットが16分音符になっただけ。"""
    return Pattern(
        "pattern_b_16beat", bpm, BARS,
        [drum_track(HIHAT_16TH), bass_track(BASS_PLAIN), chord_track()],
    )


def pattern_c(bpm: float = 120) -> Pattern:
    """シンコペーション。A とのちがいはベースの一部が裏拍にずれただけ。"""
    return Pattern(
        "pattern_c_syncopation", bpm, BARS,
        [drum_track(HIHAT_8TH), bass_track(BASS_SYNCOPATED), chord_track()],
    )


def pattern_d(bpm: float = 120) -> Pattern:
    """7/8拍子 (2+2+3)。ハイハットは8分音符(1小節に7つ)。BPMは4分音符あたり。"""
    beats = BEATS_PER_BAR_7_8
    return Pattern(
        "pattern_d_7_8", bpm, BARS,
        [
            drum_track(HIHAT_8TH, KICK_BEATS_7_8, SNARE_BEATS_7_8, beats),
            bass_track(BASS_7_8, beats),
            chord_track(bars=BARS, beats_per_bar=beats),
        ],
        time_signature=(7, 8),
    )


def chord_progression_pattern(progression: list[Chord], bpm: float = 120, bars: int | None = None) -> Pattern:
    """コード進行だけのパターン (1小節1コード、コードトラックのみ)。CLI の --chords はこれを呼ぶ。

    bars を省略するとコード数と同じ小節数。bars がコード数より多ければ進行を繰り返す。
    bars がコード数より少ない場合はコードが捨てられてしまうのでエラー。
    """
    if not progression:
        raise ValueError("コード進行が空です")
    bars = len(progression) if bars is None else bars
    if bars < len(progression):
        raise ValueError(f"小節数 {bars} がコード数 {len(progression)} より少ないため、コードが入りきりません")
    name = "chords_" + "-".join(c.symbol for c in progression).replace("#", "s")
    return Pattern(name, bpm, bars, [chord_track([c.pitches for c in progression], bars)])


PATTERNS = {"a": pattern_a, "b": pattern_b, "c": pattern_c, "d": pattern_d}
