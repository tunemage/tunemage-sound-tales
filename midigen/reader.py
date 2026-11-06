"""書き出した .mid を読み戻して拍単位の音符リストにする(検証・確認用)。

  python -m midigen.reader output/pattern_a_8beat.mid
"""
import sys
from dataclasses import dataclass, field

import mido

from .model import Note


@dataclass
class TrackInfo:
    name: str
    channels: set[int]
    programs: list[int]
    notes: list[Note]


@dataclass
class MidiInfo:
    bpm: float
    tempo_count: int
    time_signature: tuple[int, int]
    ticks_per_beat: int
    tracks: list[TrackInfo] = field(default_factory=list)   # テンポ用トラックは含まない


def read_midi(path) -> MidiInfo:
    midi = mido.MidiFile(str(path))
    tpb = midi.ticks_per_beat
    tempos, signatures, tracks = [], [], []

    for track in midi.tracks:
        tick = 0
        name, channels, programs, notes = "", set(), [], []
        open_notes = {}   # (channel, pitch) -> (開始tick, velocity)
        for msg in track:
            tick += msg.time
            if msg.type == "track_name":
                name = msg.name
            elif msg.type == "set_tempo":
                tempos.append(mido.tempo2bpm(msg.tempo))
            elif msg.type == "time_signature":
                signatures.append((msg.numerator, msg.denominator))
            elif msg.type == "program_change":
                programs.append(msg.program)
            elif msg.type == "note_on" and msg.velocity > 0:
                channels.add(msg.channel)
                open_notes[(msg.channel, msg.note)] = (tick, msg.velocity)
            elif msg.type in ("note_off", "note_on"):   # note_on velocity 0 もnote_off扱い
                start, velocity = open_notes.pop((msg.channel, msg.note))
                notes.append(Note(msg.note, start / tpb, (tick - start) / tpb, velocity))
        if notes:
            notes.sort(key=lambda n: (n.start, n.pitch))
            tracks.append(TrackInfo(name, channels, programs, notes))

    return MidiInfo(tempos[0], len(tempos), signatures[0], tpb, tracks)


def _main(path):
    info = read_midi(path)
    print(f"{path}: {info.bpm:.3f} BPM, {info.time_signature[0]}/{info.time_signature[1]}, "
          f"{info.ticks_per_beat} ticks/beat, {len(info.tracks)} tracks")
    for track in info.tracks:
        print(f"[{track.name}] channels={sorted(track.channels)} programs={track.programs} notes={len(track.notes)}")
        for n in track.notes[:12]:
            print(f"  beat {n.start:6.2f}  len {n.duration:4.2f}  pitch {n.pitch:3d}  vel {n.velocity}")
        if len(track.notes) > 12:
            print(f"  ... ({len(track.notes) - 12} more)")


if __name__ == "__main__":
    _main(sys.argv[1])
