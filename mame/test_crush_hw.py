#!/usr/bin/env python3
"""CRUSH on the swing build (src/swing/crush.s), 13-bit sample RAM and boot
ROM 2.40, as on the hardware.

* mame/keys/crush.txt: the TR 8O8 kick (WS 1, 6112 samples, LOOP FORWARD)
  crushed with PITCH -5, BITS 12: a new wavesample with its own data,
  every sample the SP-style pick of the source (the input sample the
  2^(-5/12) step lands in) masked to 12 bits, the parameters copied, loop
  points moved with the pitch, on the kick's keys (the key map), the new
  edit wavesample; C2 then plays it. The source is unchanged.
* mame/keys/crush_up.txt: PITCH +7, BITS 8: shorter, 8 bits.
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


def sp(src, step, n_in, mask):
    """The SP-style resample: (output samples, first output at or after
    each input position)."""
    out, pos, frac = [], 0, 0
    whole, f = step >> 16, step & 0xFFFF
    while pos < n_in:
        out.append(pos)
        frac += f
        if frac >= 0x10000:
            frac -= 0x10000
            pos += 1
        pos += whole
    return out


def word(d, a):
    return d[a] << 8 | d[a + 1]


def check_run(check, tag, out, before, after, pitch, mask):
    W0, W = I.wavesamples(before), I.wavesamples(after)
    new = sorted(set(W) - set(W0))
    check(f"{tag}: no ERROR, CRUSHED", "ERROR" not in out and "CRUSHED: WS" in out)
    check(f"{tag}: one new wavesample", len(new) == 1)
    if len(new) != 1:
        return
    n = new[0]
    src, rec = after[W[1]:W[1] + 0x120], after[W[n]:W[n] + 0x120]
    s, e = C.mp(src, 0xF0), C.mp(src, 0xF8)
    step = round(2 ** (pitch / 12) * 65536)
    picks = sp(None, step, e - s + 1, mask)
    got = [word(after, W[n] + 0x120 + 2 * i) for i in range(len(picks))]
    want = [word(after, W[1] + 0x120 + 2 * (s + p)) & mask for p in picks]
    check(f"{tag}: {len(picks)} samples, SP-style picks of the kick, {12 if mask == 0xFFF0 else 8}-bit",
          C.mp(rec, 0xF0) == 0 and C.mp(rec, 0xF8) == len(picks) - 1 and got == want)
    ls, le = C.mp(src, 0x100) - s, C.mp(src, 0x108) - s
    nls = next(i for i, p in enumerate(picks) if p >= ls)
    nle = max(i for i, p in enumerate(picks) if p <= le)
    check(f"{tag}: loop points moved with the pitch",
          (C.mp(rec, 0x100), C.mp(rec, 0x108)) == (nls, nle))
    same = all(rec[i] == src[i] for i in range(10, 0x120)
               if not (0x22 <= i < 0x26 or 0xF0 <= i < 0x110))
    check(f"{tag}: the rest copied, its own data", same and rec[0x22] == 0)
    check(f"{tag}: the source unchanged", before[W0[1]:W0[1] + 0x120] == after[W[1]:W[1] + 0x120])
    km = I.key_map(after)
    check(f"{tag}: on the kick's keys (21-36)",
          all(dict(km.get(k, []))[0] == n for k in range(21, 37)))
    return n


def main():
    os.makedirs(T.OUT, exist_ok=True)
    disk = H.make_disk()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as ex:
        fa = ex.submit(C.run, disk, "crush_a", "crush.txt")
        fb = ex.submit(C.run, disk, "crush_b", "crush_up.txt")
        (a_out, a_before, a_after), (b_out, b_before, b_after) = fa.result(), fb.result()
    ok = []

    def check(what, cond):
        ok.append(bool(cond))
        print(f"{'PASS' if cond else 'FAIL'}  {what}")

    check("the prompts", "CRUSH PITCH=+0?" in a_out and "CRUSH PITCH=-5?" in a_out
          and "CRUSH BITS=12?" in a_out and "CRUSH BITS=8?" in b_out and "CRUSH PITCH=+7?" in b_out)
    n = check_run(check, "-5, 12 bits", a_out, a_before, a_after, -5, 0xFFF0)
    check_run(check, "+7, 8 bits", b_out, b_before, b_after, 7, 0xFF00)
    voices = dict((int(l.split()[1]), int(l.split()[2], 16)) for l in a_out.splitlines()
                  if l.startswith("VOICE "))
    base = int(next(l for l in a_out.splitlines() if l.startswith("BASE ")).split()[1], 16)
    if n:
        check("C2 plays the crushed kick", voices.get(36) == base + I.wavesamples(a_after)[n])
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
