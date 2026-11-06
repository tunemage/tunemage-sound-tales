"""生成した .mid を読み戻して検証する。期待値は patterns.py の定数を使わず直接書いている。"""
import mido
import pretty_midi
import pytest

from midigen.patterns import PATTERNS
from midigen.reader import read_midi
from midigen.writer import write_midi

BARS = range(4)


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    out = tmp_path_factory.mktemp("midi")
    return {key: write_midi(make(), out / f"{key}.mid") for key, make in PATTERNS.items()}


def track(info, name):
    return next(t for t in info.tracks if t.name == name)


def as_tuples(t):
    return [(n.pitch, n.start, n.duration, n.velocity) for n in t.notes]


# ---------- ファイル全体 ----------
@pytest.mark.parametrize("key", ["a", "b", "c"])
def test_file_is_valid_smf_with_tempo_and_meter(files, key):
    assert files[key].stat().st_size > 0
    raw = mido.MidiFile(str(files[key]))          # 読めない/壊れていれば例外
    assert raw.type == 1                          # 複数トラック形式
    assert len(raw.tracks) == 4                   # テンポ用 + Drums/Bass/Chords

    info = read_midi(files[key])
    assert info.bpm == pytest.approx(120, abs=1e-3)
    assert info.tempo_count == 1
    assert info.time_signature == (4, 4)

    tempo = next(m.tempo for m in raw.tracks[0] if m.type == "set_tempo")
    assert tempo == 500000                        # 120BPM = 1拍500000マイクロ秒


def test_bpm_can_be_overridden(tmp_path):
    path = write_midi(PATTERNS["a"](90), tmp_path / "a90.mid")
    info = read_midi(path)
    assert info.bpm == pytest.approx(90, abs=1e-3)
    # BPMを変えても拍位置は変わらない
    assert as_tuples(track(info, "Bass")) == as_tuples(track(read_midi(write_midi(PATTERNS["a"](), tmp_path / "a120.mid")), "Bass"))


# ---------- トラック構成 ----------
@pytest.mark.parametrize("key", ["a", "b", "c"])
def test_three_independent_tracks(files, key):
    info = read_midi(files[key])
    assert [t.name for t in info.tracks] == ["Drums", "Bass", "Chords"]
    channels = [t.channels for t in info.tracks]
    assert channels[0] == {9}                     # GMドラムはチャンネル10(0始まりで9)
    assert all(len(c) == 1 for c in channels)
    assert len(set().union(*channels)) == 3       # 3トラックでチャンネルも別
    assert track(info, "Bass").programs == [33]
    assert track(info, "Chords").programs == [0]

    # 各トラックに他パートの音が混ざっていない
    assert {n.pitch for n in track(info, "Drums").notes} <= {36, 38, 42}
    assert {n.pitch for n in track(info, "Bass").notes} <= {36, 43}
    assert {n.pitch for n in track(info, "Chords").notes} == {60, 64, 67}


# ---------- 音符の内容 (パターンA) ----------
def test_pattern_a_drums(files):
    drums = track(read_midi(files["a"]), "Drums")
    by_pitch = lambda p: sorted(n.start for n in drums.notes if n.pitch == p)

    assert by_pitch(36) == [b * 4 + x for b in BARS for x in (0, 2)]          # キック: 1・3拍目
    assert by_pitch(38) == [b * 4 + x for b in BARS for x in (1, 3)]          # スネア: 2・4拍目
    assert by_pitch(42) == [i * 0.5 for i in range(32)]                        # ハイハット: 8分 x 8 x 4小節


def test_pattern_a_bass_and_chords(files):
    info = read_midi(files["a"])
    bass = [(n.pitch, n.start, n.duration) for n in track(info, "Bass").notes]
    assert bass == [(p, b * 4 + s, 0.5) for b in BARS for s, p in ((0, 36), (1, 36), (2, 43), (3, 36))]

    chords = track(info, "Chords").notes
    assert len(chords) == 12
    for bar in BARS:
        in_bar = [n for n in chords if n.start == bar * 4]
        assert sorted(n.pitch for n in in_bar) == [60, 64, 67]                 # C-E-G
        assert all(n.duration == 4 for n in in_bar)


# ---------- パターン間の差 ----------
def test_b_differs_from_a_only_in_hihat(files):
    a, b = read_midi(files["a"]), read_midi(files["b"])
    assert as_tuples(track(a, "Bass")) == as_tuples(track(b, "Bass"))
    assert as_tuples(track(a, "Chords")) == as_tuples(track(b, "Chords"))

    hats_a = [n.start for n in track(a, "Drums").notes if n.pitch == 42]
    hats_b = [n.start for n in track(b, "Drums").notes if n.pitch == 42]
    assert len(hats_a) == 32 and len(hats_b) == 64
    assert hats_b == [i * 0.25 for i in range(64)]                             # 16分音符
    for pitch in (36, 38):                                                     # キック・スネアは同じ
        same = lambda info: [n.start for n in track(info, "Drums").notes if n.pitch == pitch]
        assert same(a) == same(b)


def test_c_differs_from_a_only_in_bass_offbeats(files):
    a, c = read_midi(files["a"]), read_midi(files["c"])
    assert as_tuples(track(a, "Drums")) == as_tuples(track(c, "Drums"))
    assert as_tuples(track(a, "Chords")) == as_tuples(track(c, "Chords"))

    bass_a, bass_c = track(a, "Bass").notes, track(c, "Bass").notes
    assert len(bass_a) == len(bass_c) == 16
    moved = [(x.start, y.start) for x, y in zip(bass_a, bass_c) if x.start != y.start]
    assert moved == [(b * 4 + s, b * 4 + s + 0.5) for b in BARS for s in (1, 3)]  # 2・4拍目 → その裏
    assert all(y.start % 1 == 0.5 for x, y in zip(bass_a, bass_c) if x.start != y.start)
    # 音程・長さ・ベロシティは変わらない
    assert [(n.pitch, n.duration, n.velocity) for n in bass_a] == [(n.pitch, n.duration, n.velocity) for n in bass_c]
    # 曲の長さ(4小節=16拍)を超えて音が残っていない
    assert max(n.start + n.duration for n in bass_c) <= 16


# ---------- pretty_midi での再読み込み(秒単位)の確認 ----------
def test_pretty_midi_can_load_and_timing_matches(files):
    pm = pretty_midi.PrettyMIDI(str(files["a"]))
    assert pm.estimate_tempo() > 0
    assert [i.name for i in pm.instruments] == ["Drums", "Bass", "Chords"]
    assert [i.is_drum for i in pm.instruments] == [True, False, False]
    assert pm.time_signature_changes[0].numerator == 4 and pm.time_signature_changes[0].denominator == 4

    bass = pm.instruments[1].notes
    assert bass[0].start == pytest.approx(0.0)
    assert bass[1].start == pytest.approx(0.5, abs=1e-3)    # 1拍目の次=1拍後=0.5秒(120BPM)
    assert bass[0].end - bass[0].start == pytest.approx(0.25, abs=1e-3)
    assert pm.get_end_time() == pytest.approx(8.0, abs=1e-2)  # 4小節 = 16拍 = 8秒


# ---------- 入力チェック ----------
def test_note_validation():
    from midigen.model import Note
    for bad in (dict(pitch=128), dict(velocity=0), dict(start=-1), dict(duration=0)):
        with pytest.raises(ValueError):
            Note(**{"pitch": 60, "start": 0, "duration": 1, "velocity": 100, **bad})
