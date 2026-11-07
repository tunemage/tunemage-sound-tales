"""コマンドライン入口。引数を解釈して Pattern を作り、write_midi に渡すだけ。

  python generate.py                              # プリセット A〜D を output/ に出力
  python generate.py b c --bpm 90                 # B・C を90BPMで出力 (ファイル名に _90bpm が付く)
  python generate.py --chords C Am F G            # コード進行(1小節1コード)を output/ に出力
  python generate.py --chords "C Am F G" --bpm 90 --bars 8 --output out/prog.mid
  python generate.py a --offbeat-shift 0.1667     # 裏拍を1/6拍後ろへ(三連スイング風)
  python generate.py c --offbeat-shift -0.05 --offbeat-tracks drums   # ドラムの裏拍だけ少し前へ
"""
import argparse
from pathlib import Path

from midigen.chords import parse_progression
from midigen.patterns import PATTERNS, chord_progression_pattern
from midigen.transforms import shift_offbeats
from midigen.writer import write_midi


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ドラム/ベース/コードのMIDIパターンを生成する")
    parser.add_argument("patterns", nargs="*", help="生成するプリセット (a b c d)。省略時は全部。--chords とは併用不可")
    parser.add_argument("--chords", nargs="+", metavar="CHORD",
                        help='コード進行を直接指定 (例: --chords C Am F G / --chords "C Am F G")。'
                             "1小節1コード、対応はメジャー(C)とマイナー(Am)。#/b可 (F#, Bbm)")
    parser.add_argument("--bpm", type=float, help="BPM (プリセットは既定120を上書き、--chords の既定も120)")
    parser.add_argument("--bars", type=int, help="--chords の小節数 (既定: コード数。多ければ進行を繰り返す)")
    parser.add_argument("--out-dir", type=Path, default=Path("output"), help="出力先ディレクトリ (既定: output)")
    parser.add_argument("--output", type=Path, help="--chords の出力ファイル名を直接指定 (--out-dir より優先)")
    parser.add_argument("--offbeat-shift", type=float, metavar="BEATS",
                        help="裏拍(小節内の x.5 拍の位置)のノートを BEATS 拍ずらす。正=後ろ、負=前。"
                             "-0.5〜0.5の範囲。三連スイングは約0.1667。プリセット・--chords の両方で使える")
    parser.add_argument("--offbeat-tracks", nargs="+", metavar="TRACK",
                        help="--offbeat-shift の対象トラック (drums bass chords)。省略時は全トラック")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.bpm is not None and args.bpm <= 0:
        parser.error("--bpm は正の数で指定してください")

    if args.offbeat_tracks and args.offbeat_shift is None:
        parser.error("--offbeat-tracks は --offbeat-shift と一緒に使います")

    if args.chords is None:
        if args.bars is not None or args.output is not None:
            parser.error("--bars と --output は --chords と一緒に使います")
        jobs = presets_to_patterns(parser, args)
    else:
        if args.patterns:
            parser.error("プリセット名と --chords は同時に指定できません")
        jobs = [chords_to_pattern(parser, args)]

    for pattern, path in jobs:
        write_midi(pattern, path)
        print(f"wrote {path}  ({pattern.bpm:g} BPM, {pattern.time_signature[0]}/{pattern.time_signature[1]}, {pattern.bars} bars)")


def presets_to_patterns(parser, args):
    names = [p.lower() for p in args.patterns] or list(PATTERNS)
    unknown = [n for n in names if n not in PATTERNS]
    if unknown:
        parser.error(f"unknown pattern {unknown}; choose from {list(PATTERNS)}")

    jobs = []
    for name in names:
        pattern = PATTERNS[name](args.bpm) if args.bpm else PATTERNS[name]()
        pattern = apply_offbeat_shift(parser, args, pattern)
        jobs.append((pattern, args.out_dir / f"{pattern.name}{filename_suffix(args)}.mid"))
    return jobs


def chords_to_pattern(parser, args):
    try:
        progression = parse_progression(" ".join(args.chords))
        if args.bars is not None and args.bars < 1:
            raise ValueError("--bars は1以上で指定してください")
        pattern = chord_progression_pattern(progression, args.bpm or 120, args.bars)
    except ValueError as error:   # ChordParseError も ValueError の一種
        parser.error(str(error))
    pattern = apply_offbeat_shift(parser, args, pattern)
    return pattern, args.output or args.out_dir / f"{pattern.name}{filename_suffix(args)}.mid"


def apply_offbeat_shift(parser, args, pattern):
    if args.offbeat_shift is None:
        return pattern
    try:
        return shift_offbeats(pattern, args.offbeat_shift, args.offbeat_tracks)
    except ValueError as error:
        parser.error(str(error))


def filename_suffix(args):
    """出力ファイル名の末尾。オプションごとに違う名前になり、上書きを避ける。"""
    suffix = f"_{args.bpm:g}bpm" if args.bpm else ""
    if args.offbeat_shift is not None:
        suffix += f"_offbeat{args.offbeat_shift:g}"
        if args.offbeat_tracks:
            suffix += "_" + "-".join(name.lower() for name in args.offbeat_tracks)
    return suffix


if __name__ == "__main__":
    main()
