"""コード進行 (chords.py / generate.py --chords) のテスト。期待値のMIDIノート番号は直接書いている。"""
import pytest

from generate import main
from midigen.chords import ChordParseError, parse_chord, parse_progression
from midigen.model import Note, Pattern, Track
from midigen.patterns import PATTERNS, chord_progression_pattern
from midigen.reader import read_midi
from midigen.writer import write_midi

C, AM, F, G = [60, 64, 67], [69, 72, 76], [65, 69, 72], [67, 71, 74]


def chord_notes(info):
    """MIDIから読み戻した Chords トラックを {開始拍: [音程...]} にまとめる。"""
    (track,) = info.tracks
    by_start = {}
    for n in track.notes:
        by_start.setdefault(n.start, []).append(n.pitch)
    return {start: sorted(pitches) for start, pitches in by_start.items()}


# ---------- 解析・変換 (CLI を使わない) ----------
def test_parse_c_am_f_g():
    chords = parse_progression("C Am F G")
    assert [c.symbol for c in chords] == ["C", "Am", "F", "G"]
    assert [c.pitches for c in chords] == [C, AM, F, G]


@pytest.mark.parametrize("symbol, pitches", [
    ("Cm", [60, 63, 67]),
    ("F#", [66, 70, 73]),
    ("Bb", [70, 74, 77]),
    ("Bbm", [70, 73, 77]),
    ("Dm", [62, 65, 69]),
    ("E", [64, 68, 71]),
    ("B", [71, 75, 78]),
])
def test_parse_chord_variants(symbol, pitches):
    assert parse_chord(symbol).pitches == pitches


@pytest.mark.parametrize("bad", [
    "C7", "Cmaj7", "CM", "Cmin", "Cdim", "Csus4", "C/E", "Am7", "c", "am", "H", "C##", "Cbb", "C,", "X", "5", "C-Am",
])
def test_unsupported_or_invalid_chords_are_rejected(bad):
    with pytest.raises(ChordParseError) as error:
        parse_chord(bad)
    assert f"'{bad}'" in str(error.value)          # どの指定が悪いかメッセージに出る


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_progression_is_rejected(text):
    with pytest.raises(ChordParseError, match="空"):
        parse_progression(text)


def test_progression_bars():
    progression = parse_progression("C Am")
    assert chord_progression_pattern(progression).bars == 2
    assert chord_progression_pattern(progression, bars=4).bars == 4
    with pytest.raises(ValueError, match="少ない"):
        chord_progression_pattern(parse_progression("C Am F G"), bars=2)


# ---------- CLI ----------
def run_cli(tmp_path, *args):
    main([*args, "--out-dir", str(tmp_path)])
    return sorted(tmp_path.glob("*.mid"))


def test_cli_c_am_f_g_notes(tmp_path):
    (path,) = run_cli(tmp_path, "--chords", "C", "Am", "F", "G")
    info = read_midi(path)
    assert info.bpm == pytest.approx(120, abs=1e-3)       # 既定
    assert info.time_signature == (4, 4)
    assert [t.name for t in info.tracks] == ["Chords"]
    assert chord_notes(info) == {0: C, 4: AM, 8: F, 12: G}  # 1小節1コード
    notes = info.tracks[0].notes
    assert len(notes) == 12 and all(n.duration == 4 for n in notes)   # 各コードは小節いっぱい


def test_cli_quoted_and_unquoted_forms_are_equal(tmp_path):
    a = run_cli(tmp_path / "a", "--chords", "C Am F G")[0].read_bytes()
    b = run_cli(tmp_path / "b", "--chords", "C", "Am", "F", "G")[0].read_bytes()
    assert a == b


def test_cli_bpm_and_bars_are_applied(tmp_path):
    (path,) = run_cli(tmp_path, "--chords", "C", "Am", "--bpm", "90", "--bars", "6")
    info = read_midi(path)
    assert info.bpm == pytest.approx(90, abs=1e-3)
    assert chord_notes(info) == {0: C, 4: AM, 8: C, 12: AM, 16: C, 20: AM}   # 6小節ぶん(進行を繰り返す)
    assert max(n.start + n.duration for n in info.tracks[0].notes) == 24      # 6小節 = 24拍
    assert "90bpm" in path.name


def test_cli_output_file(tmp_path):
    target = tmp_path / "sub" / "my_prog.mid"
    main(["--chords", "Dm", "G", "C", "--output", str(target)])
    assert chord_notes(read_midi(target)) == {0: [62, 65, 69], 4: G, 8: C}


@pytest.mark.parametrize("args, message", [
    (["--chords", "C7"], "C7"),
    (["--chords", "C", "Am", "x"], "'x'"),
    (["--chords", "C,Am"], "C,Am"),
    (["--chords", "C", "Am", "F", "G", "--bars", "2"], "少ない"),
    (["--chords", "C", "--bars", "0"], "1以上"),
    (["--chords", "C", "--bpm", "0"], "正の数"),
    (["a", "--chords", "C"], "同時"),
    (["--bars", "4"], "--chords"),
])
def test_cli_errors_exit_with_message_and_write_nothing(tmp_path, capsys, args, message):
    with pytest.raises(SystemExit) as exit_info:
        main([*args, "--out-dir", str(tmp_path)])
    assert exit_info.value.code == 2
    assert message in capsys.readouterr().err
    assert list(tmp_path.glob("*.mid")) == []


# ---------- 既存プリセットの維持 ----------
def test_cli_presets_still_generate(tmp_path):
    paths = run_cli(tmp_path)
    assert [p.name for p in paths] == [
        "pattern_a_8beat.mid", "pattern_b_16beat.mid", "pattern_c_syncopation.mid", "pattern_d_7_8.mid",
    ]
    assert all(len(read_midi(p).tracks) == 3 for p in paths)

    (b90,) = run_cli(tmp_path / "x", "b", "--bpm", "90")
    assert b90.name == "pattern_b_16beat_90bpm.mid"
    assert read_midi(b90).bpm == pytest.approx(90, abs=1e-3)


# ---------- Python入口とCLI入口の等価性 ----------
def test_python_pattern_and_cli_produce_identical_midi(tmp_path):
    # CLI の関数を一切使わず、Pattern を手で組み立てる
    notes = [
        Note(pitch, bar * 4, 4, 80)
        for bar, chord in enumerate([C, AM, F, G])
        for pitch in chord
    ]
    by_hand = Pattern("by_hand", 90, 4, [Track("Chords", notes, program=0)])
    python_path = write_midi(by_hand, tmp_path / "python.mid")

    (cli_path,) = run_cli(tmp_path / "cli", "--chords", "C", "Am", "F", "G", "--bpm", "90")

    assert read_midi(python_path) == read_midi(cli_path)
    assert python_path.read_bytes() == cli_path.read_bytes()


def test_preset_via_python_and_cli_are_identical(tmp_path):
    for key, make in PATTERNS.items():
        python_path = write_midi(make(), tmp_path / "py" / f"{key}.mid")
        (cli_path,) = run_cli(tmp_path / f"cli_{key}", key)
        assert python_path.read_bytes() == cli_path.read_bytes()
