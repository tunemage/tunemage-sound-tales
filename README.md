# tunemage-sound01 — MIDIパターン生成ツール

ドラム・ベース・コードを **別々のMIDIトラック** として書き出し、DAWで自由に編集できる
Standard MIDI File (`.mid`) を作る実験用ツールです。音声(WAV)は生成しません。

## セットアップと実行

依存ライブラリ: `pretty_midi`(MIDI書き出し。内部で `mido` と `numpy` を使用)、`pytest`(テスト用)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python generate.py                  # プリセットA〜Dを output/ に生成
.venv/bin/python generate.py b c --bpm 90     # B・Cを90BPMで生成 (output/pattern_b_16beat_90bpm.mid など)
.venv/bin/python generate.py --chords C Am F G   # コード進行を直接指定して生成 (詳細は下の「CLI仕様」)
.venv/bin/python -m pytest -q                 # 生成→再読み込み→検証
.venv/bin/python -m midigen.reader output/pattern_a_8beat.mid   # MIDIの中身を拍単位で表示
```

## ファイル構成

| ファイル | 役割 |
|---|---|
| `midigen/patterns.py` | **音楽パターンの定義。実験で編集するのはここだけ**(プリセットA〜Dと `chord_progression_pattern`) |
| `midigen/chords.py` | コード記号(`Am` など)→構成音の解析・変換。CLIに依存しない |
| `midigen/transforms.py` | `Pattern` → 変更した新しい `Pattern`。いまは `shift_offbeats`(裏拍ずらし) |
| `midigen/model.py` | `Note`(音程・開始拍・長さ拍・ベロシティ)、`Track`、`Pattern`(BPM・拍子) |
| `midigen/writer.py` | `Pattern` → `.mid` の書き出し(パターンの中身は知らない) |
| `midigen/reader.py` | `.mid` を拍単位で読み戻す(検証・確認用) |
| `generate.py` | コマンドライン入口(引数を解釈して `Pattern` を作り、`write_midi` に渡すだけ) |
| `tests/test_midi.py` | プリセットA・B・CのMIDI検証テスト |
| `tests/test_odd_meter.py` | プリセットD(7/8拍子)のテスト |
| `tests/test_offbeat.py` | 裏拍ずらし(Python・CLI・エラー)のテスト |
| `tests/test_chords.py` | コード進行(解析・CLI・エラー・Python入口との等価性)のテスト |
| `output/` | 生成済みMIDI |

時間はすべて **拍単位**(4分音符=1拍)。小節内の位置は 0=1拍目, 1=2拍目, 1.5=2拍目の裏 …。
ノート番号は C4=60(真ん中のド)。DAWによってはこれを C3 と表示します。

## プリセットA〜Dの違い

| | ドラム | ベース | コード |
|---|---|---|---|
| **A** `pattern_a_8beat` | キック1・3拍 / スネア2・4拍 / ハイハット**8分** | C2 を 0,1,3拍、G2 を 2拍(各拍の頭) | C-E-G を毎小節全音符 |
| **B** `pattern_b_16beat` | ハイハットが**16分**(キック・スネアはA同一) | A と同じ | A と同じ |
| **C** `pattern_c_syncopation` | A と同じ | 2拍目・4拍目のベースが**半拍後ろ(裏拍)**へ移動(音程・長さは同じ) | A と同じ |
| **D** `pattern_d_7_8` | **7/8拍子**(2+2+3)。キック=1つ目と3つ目のグループの頭、スネア=2つ目のグループの頭と最後の8分、ハイハット=8分(1小節に7つ) | グループの頭(0,1,2拍)にC・C・G、最後の8分(3拍)にCで次の小節へつなぐ | C-E-G を毎小節(3.5拍)いっぱいに |

共通(A〜C): 120BPM / 4/4 / 4小節。D も 120BPM・4小節ですが拍子は 7/8 です(1小節=3.5拍、4小節=14拍)。BPMは4分音符あたりの値です。
トラックは A〜D すべて トラックは `Drums`(GMドラム, ch10) / `Bass`(Electric Bass, 音色33) / `Chords`(ピアノ)。

- **A→B**: ハイハットの密度が2倍になり、細かく刻まれる感じに。ほかは同一なので「16ビートらしさ」はハイハットだけで生まれることが分かります。
- **A→C**: ベースだけが裏拍に食い込みます。キック(1・3拍目)とベースが同時に鳴る場所が減り、前のめりなノリになります。
- **A→D**: ハイハットは同じ8分ですが、1小節が8分7つ(2+2+3)になり、小節の頭に戻るのが4/4より半拍早くなります。キックとスネアも「ドン・タン・ドン・タン」の等間隔ではなく、グループの長さ(2・2・3)に沿って並びます。

## CLI仕様 (`generate.py`)

入口は2つあり、どちらも同じ `Pattern` → `write_midi` を通るので、同じ条件なら同じMIDIが出ます。

- **Pythonコード**: `midigen/patterns.py` で `Pattern` を定義する(プリセットA〜D、`chord_progression_pattern`)。例: `write_midi(pattern_d(bpm=90), "out.mid")`
- **CLI**: 引数から `Pattern` を組み立てる(下記)

```text
generate.py [プリセット名 ...] [--bpm N] [--out-dir DIR]                      # プリセット生成
generate.py --chords CHORD [CHORD ...] [--bpm N] [--bars N] [--out-dir DIR | --output FILE]   # コード進行
# どちらにも追加できる: [--offbeat-shift BEATS [--offbeat-tracks TRACK [TRACK ...]]]   # 裏拍ずらし
```

| 引数 | 内容 |
|---|---|
| `プリセット名` | `a` `b` `c` `d`(複数可)。省略すると全部。`--chords` とは併用不可 |
| `--chords` | コード進行。`--chords C Am F G` でも `--chords "C Am F G"` でも同じ。**1小節に1コード**(4拍) |
| `--bpm N` | 正の数。プリセットの既定とコード進行の既定はどちらも120 |
| `--bars N` | `--chords` のみ。既定=コード数。コード数より多いと進行を先頭から繰り返す。**コード数より少ないとエラー**(コードを黙って捨てない) |
| `--out-dir DIR` | 出力ディレクトリ。既定 `output`。ファイル名は自動(下記) |
| `--output FILE` | `--chords` のみ。出力ファイルを直接指定(`--out-dir` より優先)。親ディレクトリは自動作成 |
| `--offbeat-shift BEATS` | 裏拍のノートを BEATS 拍ずらす(下の「裏拍ずらし」)。**正=後ろ、負=前**。-0.5〜0.5(両端は不可)。プリセットと `--chords` のどちらにも使える |
| `--offbeat-tracks TRACK ...` | `--offbeat-shift` の対象トラック。`drums` `bass` `chords`(大文字小文字は区別しない)。省略時は全トラック。`--offbeat-shift` なしではエラー |

**出力ファイル名(自動)**: プリセットは `pattern_a_8beat.mid` など、コード進行は `chords_C-Am-F-G.mid`
(`#` は `s` に置換: `F#` → `Fs`)。`--bpm` を指定すると末尾に `_90bpm`、`--offbeat-shift` を指定すると `_offbeat0.1667`(対象トラック指定時はさらに `_drums-bass` など)が付きます。

**対応するコード記法**: ルート(`A`〜`G`) + 任意の `#` か `b`(1つ) + 任意の `m`(マイナー)。
`C` `Am` `F#` `Bb` `Bbm` `E#` など。コード同士は**空白区切り**です。
次は解釈を推測せず、エラーにします: `C7` `Cmaj7` `CM` `Cmin` `Cdim` `Csus4` `C/E`(onコード)、小文字(`am`)、`C##`、カンマ区切り(`C,Am`)。
エラー時は終了コード2で、どの指定が悪いかを表示し、MIDIファイルは出力されません。

**出力されるMIDI(コード進行)**: トラックは `Chords` の1つだけ(ピアノ, 音色0)。各コードは基本形の3和音で、
ルートが C4(60)〜B4(71) の範囲に来る音域に置かれ、各小節の頭から小節の終わりまで(4拍)鳴ります。ベロシティは80、拍子は4/4。
ボイシング(転回)の最適化はしません。1音ずつ独立したノートなので、DAWのピアノロールで個別に編集できます。

例: `C Am F G` のノート番号

| 小節 | コード | MIDIノート |
|---|---|---|
| 1 | C | 60 64 67 |
| 2 | Am | 69 72 76 |
| 3 | F | 65 69 72 |
| 4 | G | 67 71 74 |

### 使用例

```bash
.venv/bin/python generate.py --chords C Am F G                          # output/chords_C-Am-F-G.mid (120BPM, 4小節)
.venv/bin/python generate.py --chords "C Am F G" --bpm 90               # output/chords_C-Am-F-G_90bpm.mid
.venv/bin/python generate.py --chords C Am F G --bars 8                 # 進行を2周する8小節
.venv/bin/python generate.py --chords Dm G C --output out/ii-V-I.mid    # 出力ファイルを指定
.venv/bin/python generate.py --chords F#m Bb Eb --out-dir /tmp/midi     # 出力先ディレクトリを指定
.venv/bin/python generate.py c --bpm 90                                 # プリセットCを90BPMで
.venv/bin/python generate.py d                                          # 7/8拍子のプリセットD (output/pattern_d_7_8.mid)
.venv/bin/python -m midigen.reader output/chords_C-Am-F-G.mid           # 出力の確認(拍単位でノートを表示)
```

Pythonコードから同じものを作る場合:

```python
from midigen.chords import parse_progression
from midigen.patterns import chord_progression_pattern
from midigen.writer import write_midi

pattern = chord_progression_pattern(parse_progression("C Am F G"), bpm=90, bars=8)
write_midi(pattern, "output/my_progression.mid")
```

## 裏拍ずらし (`--offbeat-shift`)

スイング(裏拍を遅らせて跳ねさせる)やレイドバック/突っ込みを、元のパターンと聴き比べるための機能です。
`midigen/transforms.py` の `shift_offbeats(pattern, amount, track_names=None)` が `Pattern` を受け取り、ずらした**新しい `Pattern`** を返します(元は変更しません)。CLIの `--offbeat-shift` は同じ関数を呼びます。

**何がずれるか**
- 対象は**8分音符の裏**、つまり**小節の頭から数えて x.5 拍の位置**(4/4なら 0.5, 1.5, 2.5, 3.5 拍)にあるノートです。7/8 では小節の長さ(3.5拍)で数えるので、2小節目の頭(通算3.5拍)は表拍として動きません。
- **16分の裏**(x.25, x.75)は対象外です(動かしません)。
- ノートは**長さ・音程・ベロシティを変えずに開始位置だけ**動きます。
- 表拍のノートだけのトラック(例: ふつうのコード)は変化しません。キック・スネア・Aのベースも同様です。

**量の目安(拍単位)**: `0.1667`(=1/6)で三連のスイング、`0.05〜0.1` で軽いハネ、`-0.05` でやや突っ込み。
正=後ろ(遅らせる)、負=前(早める)。範囲は -0.5 より大きく 0.5 より小さい値です。MIDIの分解能は 1拍=480tick なので、0.125 は60tickちょうど、0.1667 は80tickに丸められます。

**同じ音程のノートが重なる場合**: ずらした結果、同じ音程の次のノートに食い込むときは、**手前のノートを次の開始位置までで切ります**(音が止まらずに残るのを防ぐため)。切られたノートは長さが変わります。たとえばCのベースの最後の裏拍 3.5拍(長さ0.5)を +0.125 すると 3.625 から 4.0 までの 0.375 拍になります。**同じ音程が同じ位置に重なる場合はエラー**です(例: Bの16分ハイハットを +0.25)。

```bash
.venv/bin/python generate.py a --offbeat-shift 0.1667                       # Aの裏拍(ハイハット)を三連スイング風に
.venv/bin/python generate.py c --offbeat-shift 0.1 --offbeat-tracks drums   # ドラムだけ。ベースは元の位置のまま
.venv/bin/python generate.py c --offbeat-shift -0.05 --offbeat-tracks drums bass
.venv/bin/python generate.py d --bpm 90 --offbeat-shift 0.1                 # 7/8 + 90BPM との組み合わせ
```

Pythonコードから同じものを作る場合:

```python
from midigen.patterns import pattern_c
from midigen.transforms import shift_offbeats
from midigen.writer import write_midi

write_midi(shift_offbeats(pattern_c(), 0.1, ["drums"]), "output/c_swing_drums.mid")
```

注意: `--offbeat-tracks` は複数の値を取るので、プリセット名は**その前**に書いてください(`generate.py c --offbeat-shift 0.1 --offbeat-tracks drums`)。

## パターンの変え方 (`midigen/patterns.py`)

- ハイハットの間隔: `drum_track(HIHAT_8TH)` の引数を `HIHAT_16TH` などに
- ベースの音型: `(小節内の開始位置, 音程, 長さ)` のリスト(`BASS_PLAIN`, `BASS_SYNCOPATED`)を編集
- コード: `chord_track([[C4, E4, G4], [A4, C5, E5]])` のように、小節ごとの構成音のリストを渡す(足りなければ繰り返す)
- BPM: `pattern_a(bpm=90)` または `generate.py --bpm 90`
- 4/4以外の拍子: `Pattern(..., time_signature=(7, 8))` と、`drum_track` / `bass_track` / `chord_track` の `beats_per_bar`(1小節の拍数。7/8なら3.5)をそろえる。`pattern_d` が実例
- 新パターンは `pattern_a` を真似た関数を足して `PATTERNS` に登録すれば `generate.py` から出せます(`PATTERNS` のキーがそのままプリセット名になる)

## DAWで読み込んだら、ピアノロールで確認すること

1. **トラック**: Drums / Bass / Chords の3トラックに分かれ、個別にミュート・編集できるか。テンポ 120、拍子 4/4 になっているか。
2. **ドラム(A)**: キック(C1/36)が1・3拍目、スネア(D1/38)が2・4拍目、ハイハット(F#1/42)が8分で等間隔に並んでいるか。ドラム音源が GM 配置でない場合は音色がずれます(ノート番号は正しい)。
3. **A と B の比較**: ハイハットの行だけが2倍の密度になっているか。キック・スネアの位置が重なって見えるか。
4. **A と C の比較**: ベースの音符のうち2拍目・4拍目だけが、グリッド(8分)の「裏」へずれているか。**キックの縦位置と揃っているか/ずれているか**をキック列と見比べる。
5. **ベロシティ**: ハイハットは表拍が強く裏拍が弱い。ベロシティ表示で強弱の山ができているか。
6. **コード**: C(ド)E(ミ)G(ソ) の3音が、4小節それぞれの頭から小節の終わりまで伸びているか。
7. **D(7/8)**: DAWのテンポ・拍子表示が 7/8 になっているか。小節線の間隔が4/4の曲より短い(8分7つ)か。キックの位置が小節内で 1つ目・3つ目のグループの頭(8分の1個目と5個目)に来ているか。8分のグリッド表示にして数えると 2+2+3 が確認できる。
8. **裏拍ずらし**: 元のファイルと `--offbeat-shift` 付きのファイルを別トラックに並べ、ハイハット(裏拍)のノートだけがグリッドの右(正)または左(負)へずれているか確認する。表拍(キック・スネア・拍の頭のハイハット)は元の位置のままか、ベースの切れたノート(同音の重なり回避)がないかを見る。
9. **実験**: ベースの音符を1つ手でグリッドからずらしたり、ベロシティを均一にしたりして、ノリがどう変わるか聴いてみる。
