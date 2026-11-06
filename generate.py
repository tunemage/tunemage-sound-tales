"""コマンドライン入口。引数を解釈して Pattern を作り、write_midi に渡すだけ。

  python generate.py                              # プリセット A〜D を output/ に出力
  python generate.py b c --bpm 90                 # B・C を90BPMで出力 (ファイル名に _90bpm が付く)
  python generate.py --chords C Am F G            # コード進行(1小節1コード)を output/ に出力
  python generate.py --chords "C Am F G" --bpm 90 --bars 8 --output out/prog.mid
"""
import argparse
from pathlib import Path

from midigen.chords import parse_progression
from midigen.patterns import PATTERNS, chord_progression_pattern
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
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.bpm is not None and args.bpm <= 0:
        parser.error("--bpm は正の数で指定してください")

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
        suffix = f"_{args.bpm:g}bpm" if args.bpm else ""
        jobs.append((pattern, args.out_dir / f"{pattern.name}{suffix}.mid"))
    return jobs


def chords_to_pattern(parser, args):
    try:
        progression = parse_progression(" ".join(args.chords))
        if args.bars is not None and args.bars < 1:
            raise ValueError("--bars は1以上で指定してください")
        pattern = chord_progression_pattern(progression, args.bpm or 120, args.bars)
    except ValueError as error:   # ChordParseError も ValueError の一種
        parser.error(str(error))
    suffix = f"_{args.bpm:g}bpm" if args.bpm else ""
    return pattern, args.output or args.out_dir / f"{pattern.name}{suffix}.mid"


if __name__ == "__main__":
    main()
