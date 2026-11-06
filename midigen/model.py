"""音符・トラック・パターンのデータ定義。時間の単位はすべて「拍」(4分音符 = 1拍)。"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Note:
    pitch: int          # MIDIノート番号 (0-127)
    start: float        # 開始位置(拍)。曲の先頭が0
    duration: float     # 長さ(拍)
    velocity: int = 100  # 強さ (1-127)

    def __post_init__(self):
        if not 0 <= self.pitch <= 127:
            raise ValueError(f"pitch out of range: {self.pitch}")
        if not 1 <= self.velocity <= 127:
            raise ValueError(f"velocity out of range: {self.velocity}")
        if self.start < 0 or self.duration <= 0:
            raise ValueError(f"bad timing: start={self.start}, duration={self.duration}")


@dataclass
class Track:
    name: str
    notes: list[Note]
    program: int = 0        # General MIDI音色番号(0始まり)。ドラムでは無視される
    is_drum: bool = False   # Trueならチャンネル10(GMドラム)で出力


@dataclass
class Pattern:
    name: str
    bpm: float
    bars: int
    tracks: list[Track] = field(default_factory=list)
    time_signature: tuple[int, int] = (4, 4)

    @property
    def beats_per_bar(self) -> float:
        numerator, denominator = self.time_signature
        return numerator * 4 / denominator   # 4/4 -> 4拍, 6/8 -> 3拍

    @property
    def total_beats(self) -> float:
        return self.bars * self.beats_per_bar
