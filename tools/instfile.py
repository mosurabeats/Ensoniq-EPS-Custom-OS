#!/usr/bin/env python3
"""EPS instrument files: layers, wavesamples, key maps, mute groups.

The instrument file is the instrument's memory image (checked against MAME:
byte for byte), so these offsets are the ones the OS uses in RAM
(docs/ANALYSIS.md -> Edit pages, Voice engine):
* +0x64 + 4*L (L = 0-7): layer L's offset; +0x84 + 4*W (W = 1-127):
  wavesample W's offset. Packed as ROM 0xC08D1A reads them:
  ((b[3] >> 4) << 16 | b[0] << 8 | b[2]) << 4; 0 = none.
* layer record +6 + 2*key (key 21-108): the wavesample that key plays.
* wavesample record (0x120 bytes, then the sample): name at +0x0A, one
  parameter per word (value in the high byte); ours (src/pages.s,
  src/voice.s, the 6 Amp page with --pages): +0x11E mute group, +0x11F
  FULL LEVEL, +0x11D ONE-SHOT.
"""
import re

WS_GROUP = 0x11E
WS_FULL, WS_ONESHOT = 0x11F, 0x11D
KEY_LO, KEY_HI = 21, 108


def _packed(d, a):
    return ((d[a + 3] >> 4) << 16 | d[a] << 8 | d[a + 2]) << 4


def layers(d):
    """{layer 0-7: offset} of the layers present."""
    return {l: o for l in range(8) if (o := _packed(d, 0x64 + 4 * l))}


def wavesamples(d):
    """{wavesample 1-127: offset} of the wavesamples present."""
    out = {}
    for w in range(1, 128):
        a = 0x84 + 4 * w
        if a + 4 > len(d):
            break
        o = _packed(d, a)
        if o and o + 0x120 <= len(d):
            out[w] = o
    return out


def ws_name(d, o):
    return bytes(d[o + 0x0A:o + 0x22:2]).decode("latin-1").rstrip()


def key_map(d):
    """{key: [(layer, wavesample), ...]} for the keys that play something."""
    out = {}
    for l, lo in layers(d).items():
        for k in range(KEY_LO, KEY_HI + 1):
            w = d[lo + 6 + 2 * k]
            if w:
                out.setdefault(k, []).append((l, w))
    return out


def key_ranges(d):
    """{wavesample: (lowest key, highest key)} over all layers."""
    out = {}
    for k, lws in key_map(d).items():
        for _, w in lws:
            lo, hi = out.get(w, (k, k))
            out[w] = (min(lo, k), max(hi, k))
    return out


def groups(d):
    """{wavesample: mute group}."""
    return {w: d[o + WS_GROUP] for w, o in wavesamples(d).items()}


def parse_spec(spec):
    """'C2=1,G2-A#2=2' (keys, names or MIDI numbers) or 'ALL=3' / '3' (every
    wavesample) -> [(lo, hi, group)] (lo None: all)."""
    import mkcodearea                   # key names (C4 = 60)
    out = []
    for item in (x.strip() for x in spec.split(",") if x.strip()):
        if item.isdigit() or item.upper().startswith("ALL="):
            g, lo, hi = int(item.split("=")[-1]), None, None
        else:
            m = re.fullmatch(r"([^=-]+)(?:-([^=]+))?=(\d+)", item)
            if not m:
                raise ValueError(f"bad group item {item!r}")
            lo = mkcodearea.key_number(m.group(1))
            hi = mkcodearea.key_number(m.group(2)) if m.group(2) else lo
            lo, hi, g = min(lo, hi), max(lo, hi), int(m.group(3))
        if not 0 <= g <= 15:
            raise ValueError(f"{item!r}: group 0-15")
        out.append((lo, hi, g))
    return out


def set_groups(d, spec):
    """Mute groups into the wavesamples the spec's keys play (later items
    win). A wavesample asked for two different groups is an error: groups
    are per wavesample, so all its keys share one. Returns a new bytearray
    and {wavesample: group} of what was set."""
    d = bytearray(d)
    wss, kmap = wavesamples(d), key_map(d)
    want = {}
    for lo, hi, g in parse_spec(spec):
        if lo is None:
            for w in wss:
                want[w] = (g, "ALL")
            continue
        asked = {}
        for k in range(lo, hi + 1):
            for _, w in kmap.get(k, []):
                asked[w] = g
        for w in asked:
            if w in want and want[w][1] != "ALL" and want[w][0] != g and want[w][1] == "spec":
                raise ValueError(f"wavesample {w} ({ws_name(d, wss[w])!r}) asked for groups "
                                 f"{want[w][0]} and {g}: its keys share one group")
            want[w] = (g, "spec")
    for w, (g, _) in want.items():
        d[wss[w] + WS_GROUP] = g
    return d, {w: g for w, (g, _) in want.items()}
