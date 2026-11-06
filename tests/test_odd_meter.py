"""パターンD (7/8拍子, 2+2+3) のテスト。期待値は patterns.py の定数を使わず直接書いている。

7/8 の1小節 = 8分音符7つ = 3.5拍(4分音符基準)。4小節 = 14拍。
"""
import mido
import pytest

from generate import main
from midigen.patterns import pattern_d
from midigen.reader import read_midi
from midigen.writer import write_midi

BAR = 3.5
BARS = range(4)


@pytest.fixture(scope="module")
def info(tmp_path_factory):
    return read_midi(write_midi(pattern_d(), tmp_path_factory.mktemp("d") / "d.mid"))


def track(info, name):
    return next(t for t in info.tracks if t.name == name)


def test_tempo_and_time_signature(tmp_path):
    path = write_midi(pattern_d(), tmp_path / "d.mid")
    raw = mido.MidiFile(str(path))
    signature = next(m for m in raw.tracks[0] if m.type == "time_signature")
    assert (signature.numerator, signature.denominator) == (7, 8)
    assert next(m.tempo for m in raw.tracks[0] if m.type == "set_tempo") == 500000

    info = read_midi(path)
    assert info.time_signature == (7, 8)
    assert info.bpm == pytest.approx(120, abs=1e-3)


def test_three_independent_tracks(info):
    assert [t.name for t in info.tracks] == ["Drums", "Bass", "Chords"]
    assert track(info, "Drums").channels == {9}
    assert len(set().union(*(t.channels for t in info.tracks))) == 3


def test_drums_follow_2_2_3_grouping(info):
    drums = track(info, "Drums").notes
    starts = lambda pitch: sorted(n.start for n in drums if n.pitch == pitch)
    assert starts(36) == [b * BAR + x for b in BARS for x in (0, 2)]            # キック: 3グループ(2+2+3)のうち1つ目と3つ目の頭
    assert starts(38) == [b * BAR + x for b in BARS for x in (1, 3)]            # スネア: 2つ目のグループの頭と最後の8分
    assert starts(42) == [i * 0.5 for i in range(7 * 4)]                          # ハイハット: 1小節に8分7つ


def test_bass_and_chords_fit_the_bar(info):
    bass = [(n.pitch, n.start, n.duration) for n in track(info, "Bass").notes]
    assert bass == [(p, b * BAR + s, 0.5) for b in BARS for s, p in ((0, 36), (1, 36), (2, 43), (3, 36))]

    chords = track(info, "Chords").notes
    assert len(chords) == 12
    for bar in BARS:
        in_bar = [n for n in chords if n.start == bar * BAR]
        assert sorted(n.pitch for n in in_bar) == [60, 64, 67]
        assert all(n.duration == BAR for n in in_bar)

    # 曲全体が14拍(4小節)に収まる
    assert max(n.start + n.duration for t in info.tracks for n in t.notes) == 4 * BAR


def test_cli_and_python_produce_identical_midi(tmp_path):
    python_path = write_midi(pattern_d(90), tmp_path / "python.mid")
    main(["d", "--bpm", "90", "--out-dir", str(tmp_path / "cli")])
    cli_path = tmp_path / "cli" / "pattern_d_7_8_90bpm.mid"
    assert python_path.read_bytes() == cli_path.read_bytes()
    assert read_midi(cli_path).bpm == pytest.approx(90, abs=1e-3)
    assert read_midi(cli_path).time_signature == (7, 8)
