"""裏拍ずらし (midigen/transforms.py の shift_offbeats / generate.py --offbeat-shift) のテスト。

0.125拍 = 480ticks/拍 のうち60tick で、MIDIに書いても丸め誤差が出ない。
"""
import pytest

from generate import main
from midigen.patterns import pattern_a, pattern_b, pattern_c, pattern_d
from midigen.reader import read_midi
from midigen.transforms import shift_offbeats
from midigen.writer import write_midi


def notes_of(pattern, name):
    return next(t for t in pattern.tracks if t.name == name).notes


def starts(notes, pitch):
    return sorted(n.start for n in notes if n.pitch == pitch)


def no_same_pitch_overlap(notes):
    by_pitch = {}
    for n in sorted(notes, key=lambda n: n.start):
        by_pitch.setdefault(n.pitch, []).append(n)
    return all(a.start + a.duration <= b.start + 1e-9
               for ns in by_pitch.values() for a, b in zip(ns, ns[1:]))


# ---------- Python入口: shift_offbeats ----------
def test_a_only_hihat_offbeats_move():
    shifted = shift_offbeats(pattern_a(), 0.125)
    drums = notes_of(shifted, "Drums")
    # ハイハット: 表拍(0,1,2,...)はそのまま、裏拍(0.5,1.5,...)だけ +0.125
    assert starts(drums, 42) == [i + off for i in range(16) for off in (0, 0.625)]
    # キック・スネア・ベース・コードは全部表拍なので変わらない
    assert starts(drums, 36) == [b * 4 + x for b in range(4) for x in (0, 2)]
    assert starts(drums, 38) == [b * 4 + x for b in range(4) for x in (1, 3)]
    for name in ("Bass", "Chords"):
        assert notes_of(shifted, name) == notes_of(pattern_a(), name)


def test_original_pattern_is_not_modified():
    original = pattern_a()
    shift_offbeats(original, 0.125)
    assert original == pattern_a()


def test_only_duration_and_start_of_offbeat_notes_change():
    before, after = notes_of(pattern_a(), "Drums"), notes_of(shift_offbeats(pattern_a(), 0.125), "Drums")
    assert len(before) == len(after)
    for b, a in zip(before, after):
        assert (a.pitch, a.velocity) == (b.pitch, b.velocity)
        assert a.start == (b.start + 0.125 if b.start % 1 == 0.5 else b.start)
        assert a.duration == b.duration


def test_negative_shift_moves_earlier():
    hats = starts(notes_of(shift_offbeats(pattern_a(), -0.125), "Drums"), 42)
    assert hats[:4] == [0, 0.375, 1, 1.375]


def test_pattern_c_bass_offbeats():
    shifted = notes_of(shift_offbeats(pattern_c(), 0.125, ["bass"]), "Bass")   # 名前は大文字小文字を区別しない
    assert [n.start for n in shifted][:4] == [0, 1.625, 2, 3.625]
    # 対象外のドラムは変わらない
    assert notes_of(shift_offbeats(pattern_c(), 0.125, ["bass"]), "Drums") == notes_of(pattern_c(), "Drums")


def test_track_filter_limits_what_moves():
    shifted = shift_offbeats(pattern_c(), 0.125, ["Drums"])
    assert notes_of(shifted, "Bass") == notes_of(pattern_c(), "Bass")
    assert notes_of(shifted, "Drums") != notes_of(pattern_c(), "Drums")


def test_only_eighth_offbeats_move_not_sixteenth_offbeats():
    hats = starts(notes_of(shift_offbeats(pattern_b(), 0.125), "Drums"), 42)
    # B(16分): 0, 0.25, 0.5, 0.75 のうち 0.5 だけが +0.125 される
    assert hats[:4] == [0, 0.25, 0.625, 0.75]          # starts() は開始位置順に返す


def test_offbeat_is_measured_from_bar_start_in_7_8():
    # 7/8 は1小節=3.5拍。2小節目の頭(3.5)は「裏拍」ではなく表拍なので動かない
    hats = starts(notes_of(shift_offbeats(pattern_d(), 0.125), "Drums"), 42)
    assert 3.5 in hats and 3.625 not in hats          # 小節頭の 3.5 はそのまま
    assert 4.125 in hats and 4.0 not in hats          # 2小節目の裏拍 4.0 → 4.125
    assert 0.625 in hats and 0.5 not in hats          # 1小節目の裏拍 0.5 → 0.625
    assert 3.0 in hats                                 # 1小節目の最後の8分(3.0)は拍の頭なので動かない


def test_notes_are_trimmed_so_same_pitch_never_overlaps():
    # C のベース 3.5拍(長さ0.5) を +0.125 すると 4.125 まで伸びて次小節頭の同音(4.0)に重なる
    shifted = notes_of(shift_offbeats(pattern_c(), 0.125), "Bass")
    last_in_bar = next(n for n in shifted if n.start == 3.625)
    assert 3.625 + 0.5 > 4.0                                   # 切らなければ次小節頭の C(4.0) に食い込む長さ
    assert last_in_bar.duration == 0.375                       # 次の C(4.0) の手前までで切れる
    assert no_same_pitch_overlap(shifted)
    assert next(n for n in shifted if n.start == 1.625).duration == 0.5   # 重ならないものは長さ維持


@pytest.mark.parametrize("amount", [0.5, -0.5, 0.75, -1])
def test_out_of_range_amount_is_rejected(amount):
    with pytest.raises(ValueError, match="範囲外"):
        shift_offbeats(pattern_a(), amount)


def test_unknown_track_is_rejected():
    with pytest.raises(ValueError, match="Guitar"):
        shift_offbeats(pattern_a(), 0.1, ["Guitar"])


def test_collision_of_same_pitch_is_rejected():
    # B(16分): 0.5 を +0.25 すると 0.75 のハイハットと同じ位置になる
    with pytest.raises(ValueError, match="重なります"):
        shift_offbeats(pattern_b(), 0.25)


def test_zero_shift_changes_nothing():
    assert shift_offbeats(pattern_c(), 0) == pattern_c()


# ---------- MIDIに反映されること ----------
def test_shift_is_written_to_midi(tmp_path):
    info = read_midi(write_midi(shift_offbeats(pattern_a(), 0.125), tmp_path / "a.mid"))
    drums = next(t for t in info.tracks if t.name == "Drums").notes
    assert starts(drums, 42)[:4] == [0, 0.625, 1, 1.625]
    assert info.bpm == pytest.approx(120, abs=1e-3)


# ---------- CLI ----------
def run_cli(tmp_path, *args):
    main([*args, "--out-dir", str(tmp_path)])
    return sorted(tmp_path.glob("*.mid"))


def test_cli_and_python_produce_identical_midi(tmp_path):
    python_path = write_midi(shift_offbeats(pattern_c(90), 0.125), tmp_path / "py.mid")
    (cli_path,) = run_cli(tmp_path / "cli", "c", "--bpm", "90", "--offbeat-shift", "0.125")
    assert cli_path.name == "pattern_c_syncopation_90bpm_offbeat0.125.mid"
    assert python_path.read_bytes() == cli_path.read_bytes()


def test_cli_track_filter_and_negative_value(tmp_path):
    python_path = write_midi(shift_offbeats(pattern_c(), -0.125, ["Drums", "Bass"]), tmp_path / "py.mid")
    (cli_path,) = run_cli(tmp_path / "cli", "c", "--offbeat-shift", "-0.125", "--offbeat-tracks", "drums", "bass")
    assert cli_path.name == "pattern_c_syncopation_offbeat-0.125_drums-bass.mid"
    assert python_path.read_bytes() == cli_path.read_bytes()


def test_cli_applies_to_every_preset_when_none_given(tmp_path):
    paths = run_cli(tmp_path, "--offbeat-shift", "0.1")
    assert len(paths) == 4 and all("_offbeat0.1" in p.name for p in paths)


def test_cli_without_option_is_unchanged(tmp_path):
    (path,) = run_cli(tmp_path, "a")
    assert path.name == "pattern_a_8beat.mid"
    assert path.read_bytes() == write_midi(pattern_a(), tmp_path / "py.mid").read_bytes()


def test_cli_shift_with_chords_changes_nothing_because_chords_are_on_the_beat(tmp_path):
    (plain,) = run_cli(tmp_path / "p", "--chords", "C", "Am")
    (shifted,) = run_cli(tmp_path / "s", "--chords", "C", "Am", "--offbeat-shift", "0.1")
    assert shifted.name == "chords_C-Am_offbeat0.1.mid"
    assert shifted.read_bytes() == plain.read_bytes()


@pytest.mark.parametrize("args, message", [
    (["a", "--offbeat-shift", "0.5"], "範囲外"),
    (["a", "--offbeat-shift", "0.1", "--offbeat-tracks", "guitar"], "guitar"),
    (["a", "--offbeat-tracks", "drums"], "--offbeat-shift"),
    (["--chords", "C", "--offbeat-shift", "0.1", "--offbeat-tracks", "drums"], "drums"),
    (["b", "--offbeat-shift", "0.25"], "重なります"),
])
def test_cli_errors_exit_with_message_and_write_nothing(tmp_path, capsys, args, message):
    with pytest.raises(SystemExit) as exit_info:
        main([*args, "--out-dir", str(tmp_path)])
    assert exit_info.value.code == 2
    assert message in capsys.readouterr().err
    assert list(tmp_path.glob("*.mid")) == []
