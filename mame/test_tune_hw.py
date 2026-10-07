#!/usr/bin/env python3
"""TUNE on the swing build (src/swing/tune.s), 13-bit sample RAM and boot
ROM 2.40, as on the hardware. TUNE is per wavesample, on the 4 Pitch page.

* mame/keys/tune.txt: TR 8O8, Edit, the kick (WS 1) selected, 4 Pitch, ◄ =
  TUNE, ▼ ▼ ▲: TUNE=-1, the kick one semitone lower (ROOT KEY + 1), every
  other wavesample untouched, -1 in its record's +0x11D. Then CREATE NEW
  WAVESAMPLE (x4): the new ones start at TUNE=+0 (display and record).
* mame/keys/tune_all.txt: WS=ALL, TUNE ▼: every wavesample of layer 1 a
  semitone lower and at -1, layer 2's untouched.
Needs what mame/test_mutegroups.py needs.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import test_mutegroups as T  # noqa: E402
import test_swing_hw as H  # noqa: E402
import test_chop_hw as C  # noqa: E402
import instfile as I  # noqa: E402

W_TUNE = 0x11D


def chains(d):
    """{layer: [its wavesamples, in chain order]}"""
    W, out = I.wavesamples(d), {}
    for l, lo in I.layers(d).items():
        w, seen = d[lo + 6], []
        while w and w not in seen:
            seen.append(w)
            w = d[W[w] + 6]
        out[l] = seen
    return out


def main():
    os.makedirs(T.OUT, exist_ok=True)
    disk = H.make_disk()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as ex:
        fa = ex.submit(C.run, disk, "tune_a", "tune.txt", 44.5, (33, 44))
        fb = ex.submit(C.run, disk, "tune_b", "tune_all.txt", 38, (33, 37))
    ok = []

    def check(what, cond):
        ok.append(bool(cond))
        print(f"{'PASS' if cond else 'FAIL'}  {what}")

    out, before, after = fa.result()
    screens = [l for l in out.splitlines() if "TUNE=" in l]
    check("no ERROR on the display", "ERROR" not in out)
    check("TUNE on the 4 Pitch page: +0, then -1, -2, -1 as ▼ ▼ ▲ change it",
          screens and "TUNE=<62>+0<72><63>-1<72><63>-2<72><63>-1" in screens[0])
    W0, W1 = I.wavesamples(before), I.wavesamples(after)
    roots = {w: (before[W0[w] + 0xAA], after[W1[w] + 0xAA]) for w in W0}
    check("the kick (WS 1): ROOT KEY + 1 (a semitone lower), -1 << 3 in +0x11D",
          roots[1][1] == roots[1][0] + 1 and after[W1[1] + W_TUNE] == 0xF8)
    check("every other wavesample untouched",
          all(roots[w][1] == roots[w][0] and after[W1[w] + W_TUNE] == 0 for w in W0 if w != 1))
    new = [w for w in W1 if w not in W0]
    check("CREATE NEW WAVESAMPLE: the new ones at +0 (record)",
          new and all(after[W1[w] + W_TUNE] == 0 for w in new))
    check("... and on the display (the new edit wavesample)",
          len(screens) > 1 and "TUNE=<62>+0" in screens[-1])
    print("   roots:", roots, " new:", new)

    out, before, after = fb.result()
    W0, W1 = I.wavesamples(before), I.wavesamples(after)
    L = chains(after)
    check("WS=ALL: no ERROR, TUNE shows -1", "ERROR" not in out and "-1" in
          next((l for l in out.splitlines() if "TUNE=" in l), ""))
    check("WS=ALL: every wavesample of layer 1 a semitone lower, at -1",
          L[0] and all(after[W1[w] + 0xAA] == before[W0[w] + 0xAA] + 1
                       and after[W1[w] + W_TUNE] == 0xF8 for w in L[0]))
    check("WS=ALL: layer 2 untouched",
          all(after[W1[w] + 0xAA] == before[W0[w] + 0xAA] and after[W1[w] + W_TUNE] == 0
              for w in L.get(1, [])))
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
