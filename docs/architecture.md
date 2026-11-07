# アーキテクチャ解説

現在のソース(裏拍ずらし `--offbeat-shift` 追加後)の役割分担と処理の流れをまとめたドキュメントです。
実装の理解を目的としており、改善案は含みません。

表記:
- **【事実】** コードやテストから確認できること
- **【推測】** 設計意図など、コードからは断定できないこと

---

## 1. 各ファイル・クラスの責務

| ファイル | 主な要素 | 責務 |
|---|---|---|
| `generate.py` | `build_parser()`, `main(argv)`, `presets_to_patterns()`, `chords_to_pattern()` | CLI 引数の解釈、`Pattern` の取得、出力パスの決定、`write_midi` の呼び出しをする。音楽的な処理はしない。 |
| `midigen/model.py` | `Note`, `Track`, `Pattern` | 音楽構造のデータ定義。時間はすべて拍単位(4分音符=1拍)で、MIDI の知識はない。 |
| `midigen/patterns.py` | `drum_track`, `bass_track`, `chord_track`, `pattern_a`〜`pattern_d`, `chord_progression_pattern`, `PATTERNS` | 音楽パターンの定義と組み立て。リズムやベース音型を定数で持ち、`Pattern` を返す関数群。 |
| `midigen/chords.py` | `Chord`, `parse_chord`, `parse_progression`, `ChordParseError` | コード記号(`Am` など)から構成音(MIDI ノート番号)への変換と、文字列の検証。 |
| `midigen/transforms.py` | `shift_offbeats`, `is_offbeat` | `Pattern` を受け取り、変更した新しい `Pattern` を返す変換(元は変更しない)。現在は裏拍(8分の裏)のノートの開始位置を前後にずらす処理のみ。 |
| `midigen/writer.py` | `write_midi(pattern, path)` | `Pattern` を `.mid` に書き出す。`pretty_midi` を使うのはこのファイルだけ(`reader.py` は `mido` を直接使う)。 |
| `midigen/reader.py` | `read_midi`, `MidiInfo`, `TrackInfo` | `.mid` を `mido` で読み戻し、拍単位の `Note` に復元する。検証用で、テストと `python -m midigen.reader` が使う。 |
| `tests/` | `test_midi.py`, `test_chords.py`, `test_odd_meter.py`, `test_offbeat.py` | 生成した MIDI を再読み込みして検証する。 |

各クラスの中身:

- **`Note`**: `pitch`・`start`・`duration`・`velocity` を持つ frozen dataclass。`__post_init__` で範囲を検証する(音程 0〜127、ベロシティ 1〜127、`start`≥0、`duration`>0)。
- **`Track`**: `name`・`notes`・`program`・`is_drum` を持つ。
- **`Pattern`**: `name`・`bpm`・`bars`・`tracks`・`time_signature` を持つ。

---

## 2. クラス間の依存関係とデータの受け渡し

import の向き(`A → B` は「A が B を import する」):

```
generate.py ──→ midigen.chords   (parse_progression)
            ──→ midigen.patterns (PATTERNS, chord_progression_pattern)
            ──→ midigen.transforms (shift_offbeats)
            ──→ midigen.writer   (write_midi)

midigen.patterns ──→ midigen.chords (Chord のみ)
                 ──→ midigen.model  (Note, Pattern, Track)
midigen.transforms ──→ midigen.model (Note, Pattern, Track)
midigen.writer   ──→ midigen.model  (Pattern) + pretty_midi
midigen.reader   ──→ midigen.model  (Note)    + mido
midigen.chords   ──→ (標準ライブラリのみ)
midigen.model    ──→ (標準ライブラリのみ)
```

受け渡されるデータ:

```
CLI引数(str) ─parse_progression→ list[Chord(symbol, pitches)]
            ─chord_progression_pattern→ Pattern ─(任意)shift_offbeats→ Pattern ─write_midi→ .mid
プリセット名  ─PATTERNS[name](bpm)──────→ Pattern ─(任意)shift_offbeats→ Pattern ─write_midi→ .mid
```

`shift_offbeats` は `--offbeat-shift` 指定時だけ通る。`Pattern` から `Pattern` への変換なので、プリセットでも `--chords` でも同じように挟める。

- **【事実】** `writer.py` は `patterns.py` や `chords.py` を import しない。`Pattern` だけを受け取るので、パターンの出どころ(プリセットかコード進行か)を知らない。
- **【事実】** `chords.py` は `patterns.py` や CLI を import しない。逆に `patterns.py` が `chords.Chord` を型として import している。
- **【事実】** `reader.py` は `writer.py` に依存しない。`Pattern` を復元するのではなく、`MidiInfo` / `TrackInfo` に復元する。

---

## 3. CLI から MIDI が生成されるまで

`main()` は `generate.py:37-58` にある。

### 共通部分
1. `build_parser()` で引数を定義し、`parse_args(argv)` を呼ぶ。`argv` を渡せるので、テストは `main([...])` を直接呼んでいる。
2. `--bpm` が 0 以下ならエラー(`generate.py:41`)。`--offbeat-tracks` だけ指定されていてもエラー。
3. `args.chords` の有無で分岐する。
   - なし(プリセット): `--bars` / `--output` が指定されていればエラー。
   - あり: プリセット名が併記されていればエラー。
4. 結果は `jobs = [(Pattern, 出力パス), ...]`。最後に `write_midi(pattern, path)` と成功メッセージの `print` を行う。

### 経路A: プリセット(`generate.py b --bpm 90`)
1. `presets_to_patterns()` が名前を小文字化する。未指定なら `list(PATTERNS)` で全部。
2. 未知の名前は `parser.error`。
3. `PATTERNS[name](args.bpm)` を呼ぶ。`--bpm` 未指定なら引数なしで呼ぶため、各 `pattern_x` 関数の既定値 120 になる。
4. `--offbeat-shift` が指定されていれば `apply_offbeat_shift()` が `shift_offbeats()` を呼び、新しい `Pattern` に差し替える。
5. パスは `out_dir / f"{pattern.name}{filename_suffix(args)}.mid"`。suffix は `--bpm` で `_90bpm`、`--offbeat-shift` で `_offbeat0.1667`(`--offbeat-tracks` 指定時はさらに `_drums-bass` など)。

### 経路B: コード進行(`generate.py --chords C Am F G`)
1. `chords_to_pattern()` が `" ".join(args.chords)` で1つの文字列にする。クォート有無のどちらでも同じ文字列になる。
2. `parse_progression()` が空白で分割し、各トークンを `parse_chord()` に渡す。正規表現 `^([A-G])([#b]?)(m?)$` に一致しなければ `ChordParseError`。
3. `--bars` が 1 未満なら `ValueError`。
4. `chord_progression_pattern(progression, args.bpm or 120, args.bars)` が `Pattern` を返す。
5. `ValueError`(`ChordParseError` を含む)は `parser.error(str(error))` に変換され、終了コード 2 で終了する。この時点でファイルは書かれない。
6. 経路A と同様に `apply_offbeat_shift()` を適用する。
7. パスは `args.output` があればそれ、なければ `out_dir / f"{pattern.name}{filename_suffix(args)}.mid"`。

### 書き出し(`midigen/writer.py:11`)
1. 親ディレクトリを `mkdir(parents=True, exist_ok=True)` で作る。
2. `PrettyMIDI(initial_tempo=bpm, resolution=480)` を作り、`TimeSignature` を1つ登録する。
3. 拍を秒に変換して(`start * 60 / bpm`)、`Track` ごとに `Instrument` を作る。`pretty_midi` が秒単位の API なので、この変換が入っている。
4. `midi.write()` で出力する。

---

## 4. `Pattern` の役割と CLI 動的生成との関係

### 役割【事実】
- `Pattern` は `write_midi` が受け取る唯一の入力型。
- 経路A・B のどちらも、最終的に `Pattern` を作って `write_midi` に渡す。
- `write_midi` を呼ぶ箇所は `generate.py:57` の1か所。

### CLI との関係【事実】
- CLI は「Pattern を組み立てる関数を選んで呼ぶ」だけで、`Note` を直接作らない。
- プリセットは事前定義の関数(`PATTERNS` の辞書引き)、コード進行は引数から組み立てる関数(`chord_progression_pattern`)。
- Python 側も同じ関数を呼べる。例: `chord_progression_pattern(parse_progression("C Am F G"), bpm=90)`。
- `tests/test_chords.py` が、手で組み立てた `Pattern` と CLI 出力のバイト列が一致することを確認している。
- `tests/test_chords.py` と `tests/test_odd_meter.py` は、プリセット(A〜D)の Python 版と CLI 版のバイト列一致も確認している。

### Pattern のうち出力に使われない部分【事実】
`grep` で確認した結果:
- `Pattern.beats_per_bar` は `midigen/transforms.py` の `shift_offbeats` が参照している(小節の頭から数えた裏拍の判定)。`Pattern.total_beats` は `model.py` 内以外から参照されていない。`patterns.py` は `Pattern.beats_per_bar` を使わず、自前の定数(`BEATS_PER_BAR`、`BEATS_PER_BAR_7_8`)を使っている。
- `Pattern.bars` は `write_midi` では使われない。CLI の `print` と `chord_progression_pattern` の内部でのみ参照される。
- `Pattern.name` はファイル名には使われるが、MIDI の中身には書かれない。

### CLI の表現力の限界【事実】
- CLI から指定できるのは、プリセット名と BPM、またはコード進行(`--chords`)、`--bars`、出力先、および裏拍ずらし(`--offbeat-shift` / `--offbeat-tracks`)だけ。
- ドラムやベースの音型、拍子を CLI から指定する手段は現在の実装にはない。
- 「Python と CLI が対等」は、「同じ `Pattern` / `write_midi` を通る」という意味では成り立っている。ただし、コマンドラインで指定できる範囲は Python 側より狭い。

### 【推測】
`Pattern.total_beats` は、将来の検証などを見越したものかもしれない。現状では使われていない。

---

## 5. 新しい音楽パターンを追加する場合に変更する箇所

### CLI のプリセットとして出す場合(最小構成)
変更するのは `midigen/patterns.py` のみ。

1. 必要ならリズムやベース音型の定数を追加する(例: `BASS_xxx = [(位置, 音程, 長さ), ...]`)。
2. `pattern_e(bpm: float = 120) -> Pattern` のような関数を追加し、`drum_track` / `bass_track` / `chord_track` を組み合わせて返す。
3. ファイル末尾の `PATTERNS` に `"e": pattern_e` を足す。

これで次の動作が決まる:
- `generate.py` は `PATTERNS` を辞書引きするので、コード変更なしで `generate.py e` が使える。
- 引数なしの全生成にも自動で含まれる。
- `--bpm` も効く。

### 既存ヘルパーで足りない場合
- 4/4 以外の拍子では、`Pattern(..., time_signature=(7, 8))` と、各 `*_track` の `beats_per_bar` 引数をそろえる。`pattern_d` が実例。
- `drum_track` はキック・スネア・ハイハットの3種に固定。他の楽器を足すには、`patterns.py` の定数かヘルパーの拡張が必要。
- `Track` を直接 `Note` のリストから作って `Pattern` に渡すこともできる。

### 同時に確認が必要になる箇所【事実】
- 全プリセット生成の件数やファイル名を固定しているテストは、プリセットを増やすと更新が必要。D 追加時に `test_cli_presets_still_generate`(`tests/test_chords.py`)の期待値を更新した。
- `generate.py` の `--help` 文言と README に、プリセット名一覧が手書きで書かれている(`a b c d`)。コードは `PATTERNS` から自動で取るが、これらの表記は手動更新。

### パターン固有の CLI 引数が欲しい場合
- `chord_progression_pattern` と `--chords` の組が実例。`patterns.py` に Pattern 生成関数を足し、`generate.py` に引数と変換関数(`chords_to_pattern` 相当)を足す形になる。
- **【推測】** 現状の構成は、この形が前提だと思われる。ただし、そのための汎用的な登録の仕組みはなく、`generate.py` 側の分岐を直接編集する形になる。
