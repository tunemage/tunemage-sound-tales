"""Pattern を Standard MIDI File (.mid) に書き出す。パターンの中身には関与しない。"""
from pathlib import Path

import pretty_midi

from .model import Pattern

RESOLUTION = 480  # 1拍あたりのtick数。16分音符=120tick、3連符も割り切れる


def write_midi(pattern: Pattern, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    midi = pretty_midi.PrettyMIDI(initial_tempo=pattern.bpm, resolution=RESOLUTION)
    numerator, denominator = pattern.time_signature
    midi.time_signature_changes.append(pretty_midi.TimeSignature(numerator, denominator, 0))

    seconds_per_beat = 60.0 / pattern.bpm   # pretty_midiは秒単位なので拍から変換する
    for track in pattern.tracks:
        instrument = pretty_midi.Instrument(
            program=track.program, is_drum=track.is_drum, name=track.name
        )
        for note in track.notes:
            instrument.notes.append(
                pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=note.pitch,
                    start=note.start * seconds_per_beat,
                    end=(note.start + note.duration) * seconds_per_beat,
                )
            )
        midi.instruments.append(instrument)

    midi.write(str(path))
    return path
