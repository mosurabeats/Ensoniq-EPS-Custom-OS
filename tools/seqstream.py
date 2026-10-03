#!/usr/bin/env python3
"""EPS sequencer event streams: decode, encode, and swing-quantize a take.

Reference for the 68000 code (src/swing.s is tested against it). Format,
from recordings made in MAME (docs/ANALYSIS.md -> Sequencer):

* An event is one or more 16-bit words; the first has bit 15 set, the
  others don't. Bits 11-4 of the first word are the event code, bits 3-0
  the instrument (track) it plays.
* code < 0xB0: a note, 3 words. key = code + 21; w1 bits 15-3 = duration in
  ticks; w2 bits 10-4 = velocity.
* code 0xB9: a time event, 2 words, carrying a 14-bit gap: high 3 bits in
  w0 bits 14-12, low 11 bits in w1 bits 14-4.
* other codes 0xB0+: control events. 2 words (a 7-bit value in w1 bits 10-4,
  e.g. 0xB1 pitch bend, 0xB8 mod wheel, 0xBD ...) or 1 word (0xBB: start of
  a take, 0xBC: end).
* Every event of 2+ words (except time events) carries the 7-bit gap to the
  next event: high 3 bits in w0 bits 14-12, low 4 bits in its last word's
  bits 14-11 (OS 0xFF73F0). Longer gaps, and gaps after 1-word events, use
  time events.

Times are ticks, 48 per quarter note.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import swing  # noqa: E402

TIME, START, END = 0xB9, 0xBB, 0xBC
MAX_TIME = 0x3FFF


def code(w0):
    return (w0 >> 4) & 0xFF


def is_note(ev):
    return code(ev[0]) < 0xB0


def split(words):
    """Words -> list of events (lists of words)."""
    evs = []
    for w in words:
        if w & 0x8000:
            evs.append([w])
        elif evs:
            evs[-1].append(w)
        else:
            raise ValueError("stream starts inside an event")
    return evs


def gap_of(ev):
    if code(ev[0]) == TIME:
        return ((ev[0] >> 12) & 7) << 11 | (ev[1] >> 4) & 0x7FF
    if len(ev) == 1:
        return 0                      # bits 14-12 unused (0 in recordings)
    return ((ev[0] >> 12) & 7) << 4 | (ev[-1] >> 11) & 0xF


def with_gap(ev, gap):
    ev = list(ev)
    if code(ev[0]) == TIME:
        ev[0] = ev[0] & 0x8FFF | ((gap >> 11) & 7) << 12
        ev[1] = ev[1] & 0x800F | (gap & 0x7FF) << 4
    elif len(ev) == 1:
        if gap:
            raise ValueError("1-word event can't carry a gap")
    else:
        ev[0] = ev[0] & 0x8FFF | ((gap >> 4) & 7) << 12
        ev[-1] = ev[-1] & 0x87FF | (gap & 0xF) << 11
    return ev


def decode(words):
    """Words -> [(time, event)] without the time events, plus the end time
    (the time of the END event, or of the end of the stream)."""
    t, out = 0, []
    for ev in split(words):
        if len(ev) == 1:              # bits 14-12 unused (0 in recordings)
            ev = [ev[0] & 0x8FFF]
        if code(ev[0]) != TIME:
            out.append((t, with_gap(ev, 0) if len(ev) > 1 else ev))
        t += gap_of(ev)
    return out, t


def time_event(gap):
    return with_gap([0x8B90, 0x0000], gap)


def encode(timed):
    """[(time, event)] in time order -> words, with gaps and time events."""
    words = []
    for i, (t, ev) in enumerate(timed):
        gap = timed[i + 1][0] - t if i + 1 < len(timed) else 0
        if gap < 0:
            raise ValueError("events out of order")
        if len(ev) > 1 and gap <= 127:
            words += with_gap(ev, gap)
            continue
        words += with_gap(ev, 0) if len(ev) > 1 else ev
        while gap:
            g = min(gap, MAX_TIME)
            words += time_event(g)
            gap -= g
    return words


def tag(ev):
    """A note's pass tag: bits 3-0 of its last word (src/looprec.s writes
    them during LOOPED recording; playback ignores them)."""
    return ev[2] & 0xF if is_note(ev) else 0


def clear_tags(words):
    return [w for ev in split(words) for w in (ev[:2] + [ev[2] & 0xFFF0] if is_note(ev) else ev)]


def quantize_take(words, settings, kill=0):
    """Quantize the notes of a take. settings: {instrument 0-7: (grid,
    style, amount)} (instruments not listed stay as played). Notes keep
    their order relative to events at the same new time; notes that land
    on or after the end wrap to the start of the take; nothing moves before
    the take's opening events (start marker and controller states, at tick
    1 in recordings), and notes already at that time stay (a downbeat).
    kill: notes whose tag n has bit n set in it are left out (undo)."""
    timed, _ = decode(words)
    timed = [(t, ev) for t, ev in timed if not kill >> tag(ev) & 1 or not tag(ev)]
    end = next((t for t, ev in timed if code(ev[0]) == END), None)
    first_note = next((i for i, (t, ev) in enumerate(timed) if is_note(ev)), len(timed))
    floor = timed[first_note - 1][0] if first_note else 0
    moved = []
    for i, (t, ev) in enumerate(timed):
        inst = ev[0] & 0xF
        if is_note(ev) and inst in settings and t != floor:
            grid, style, amount = settings[inst]
            q = swing.quantize(t, grid, style, amount)
            if end is not None and q >= end:
                q = floor
            t = max(q, floor)
        moved.append((t, i, ev))
    ends = [m for m in moved if code(m[2][0]) == END]
    rest = sorted((m for m in moved if code(m[2][0]) != END), key=lambda m: (m[0], m[1]))
    return encode([(t, ev) for t, _, ev in rest + ends])


def notes(words):
    """[(time, key, instrument, velocity, duration)] of a stream."""
    timed, _ = decode(words)
    return [(t, code(ev[0]) + 21, ev[0] & 0xF, (ev[2] >> 4) & 0x7F, ev[1] >> 3)
            for t, ev in timed if is_note(ev)]


def parse(hexwords):
    return [int(w, 16) for w in hexwords.split()]


# ---------------------------------------------------------------- fast path
# What src/swing.s does at a loop wrap: walk the take once and move each
# off-grid note locally (notes from earlier passes are on the grid already)
# instead of re-encoding the whole take. A move shifts the events between
# the old and new place by the note's size and fixes three gaps. When it
# can't (a gap over 127 or a 1-word / time event where a gap must go, or a
# note moving back over more than HISTORY events), the rest is left to
# quantize_take, which starts from the take as edited so far. A note that
# quantizes onto the end wraps to the start (after the opening events).
HISTORY = 16


class _Fallback(Exception):
    pass


def _gap_ok(ev, gap):
    if not 0 <= gap <= 127 or len(ev) < 2 or code(ev[0]) == TIME:
        raise _Fallback


def swing_take(words, settings):
    """The take as src/swing.s leaves it: the fast path, and quantize_take
    on its result if the fast path had to stop."""
    evs = split(list(words))
    try:
        _fast(evs, settings)
        return [w for ev in evs for w in ev]
    except _Fallback:
        return quantize_take([w for ev in evs for w in ev], settings)


def quantize_take_fast(words, settings):
    """The fast path alone: words, or None if it had to stop."""
    evs = split(list(words))
    try:
        _fast(evs, settings)
    except _Fallback:
        return None
    return [w for ev in evs for w in ev]


def _fast(evs, settings):
    """Edits evs (a list of events) in place, like the 68000 code."""
    def time_at(k):
        return sum(gap_of(e) for e in evs[:k])

    floor, seen_note = 0, False
    i, t = 0, 0
    while i < len(evs):
        ev = evs[i]
        gap_n = gap_of(ev)
        if not is_note(ev):
            if not seen_note and code(ev[0]) != TIME:
                floor = t
            i, t = i + 1, t + gap_n
            continue
        seen_note = True
        inst = ev[0] & 0xF
        if inst not in settings or t == floor:
            i, t = i + 1, t + gap_n
            continue
        grid, style, amount = settings[inst]
        q = max(swing.quantize(t, grid, style, amount), floor)
        if q == t:
            i, t = i + 1, t + gap_n
            continue
        b = i - 1                              # the event before the note
        if b < 0:
            raise _Fallback
        wrap = False
        if q > t:
            # forward over the events before q; they go before the note
            m, tm = i + 1, t + gap_n
            while tm < q:
                if m >= len(evs) or code(evs[m][0]) == END:
                    wrap = True                # q is past the end
                    break
                tm += gap_of(evs[m])
                m += 1
            if not wrap and m < len(evs) and code(evs[m][0]) == END and tm <= q:
                wrap = True
        if wrap:
            # to the start: after the events at or before the floor
            q = floor
            r, tr = 0, 0
            while tr <= q:
                tr += gap_of(evs[r])
                r += 1
            tp = tr - gap_of(evs[r - 1])
        if q < t:
            if not wrap:
                # back over the events after q (their times: t minus gaps)
                r, tr = i, t
                while True:
                    tp = tr - gap_of(evs[r - 1])   # time of event r-1
                    if tp <= q:
                        break
                    r, tr = r - 1, tp
                    if i - r > HISTORY or r - 1 < 0:
                        raise _Fallback
            if r == i:                         # nothing in between
                _gap_ok(evs[b], gap_of(evs[b]) - (t - q))
                _gap_ok(ev, gap_n + (t - q))
                evs[b] = with_gap(evs[b], gap_of(evs[b]) - (t - q))
                evs[i] = with_gap(ev, gap_n + (t - q))
            else:
                p = r - 1                      # the event before the new place
                _gap_ok(evs[p], q - tp)
                _gap_ok(ev, tr - q)
                _gap_ok(evs[b], gap_of(evs[b]) + gap_n)
                evs[b] = with_gap(evs[b], gap_of(evs[b]) + gap_n)
                evs[p] = with_gap(evs[p], q - tp)
                note = with_gap(ev, tr - q)
                del evs[i]
                evs.insert(r, note)
            i, t = i + 1, t + gap_n            # on with the event after it
        else:
            if m == i + 1:                     # nothing in between
                _gap_ok(evs[b], gap_of(evs[b]) + (q - t))
                _gap_ok(ev, gap_n - (q - t))
                evs[b] = with_gap(evs[b], gap_of(evs[b]) + (q - t))
                evs[i] = with_gap(ev, gap_n - (q - t))
                i, t = i + 1, t + gap_n
            else:
                last = m - 1                   # the last event that moves before
                tl = tm - gap_of(evs[last])
                _gap_ok(evs[b], gap_of(evs[b]) + gap_n)
                _gap_ok(evs[last], q - tl)
                _gap_ok(ev, tm - q)
                evs[b] = with_gap(evs[b], gap_of(evs[b]) + gap_n)
                evs[last] = with_gap(evs[last], q - tl)
                note = with_gap(ev, tm - q)
                del evs[i]
                evs.insert(last, note)
                t = t + gap_n                  # on with the first event moved


# ------------------------------------------------------------ logged notes
# At record time src/looprec.s logs each new note (its word offset in the
# take and its time); at the wrap only those are moved, with the same local
# edits as _fast - no scan of the whole take. log: [(word index of the
# note's first word, time)] in recording order (= stream order).

def swing_logged(words, settings, log):
    """The take as src/swing.s leaves it in log mode (fast moves of the
    logged notes; the full path if one can't be done)."""
    evs = split(list(words))
    try:
        _logged(evs, settings, log)
        return [w for ev in evs for w in ev]
    except _Fallback:
        return quantize_take([w for ev in evs for w in ev], settings)


def _logged(evs, settings, log):
    starts = []                                  # word index of each event
    def index_of(word_index):
        pos = 0
        for k, ev in enumerate(evs):
            if pos == word_index:
                return k
            pos += len(ev)
        raise _Fallback
    def word_index(k):
        return sum(len(e) for e in evs[:k])
    # floor: the time of the last opening event before the first note
    floor, t = 0, 0
    for ev in evs:
        if is_note(ev):
            break
        if code(ev[0]) != TIME:
            floor = t
        t += gap_of(ev)
    pending = [list(e) for e in log]
    for n in range(len(pending)):
        wi, t = pending[n]
        i = index_of(wi)
        ev = evs[i]
        if not is_note(ev):
            raise _Fallback
        moved = _move_note(evs, i, t, floor, settings)
        if moved is not None:                    # later move: shift the log
            lo, hi = moved                       # (word indexes) moved by -3
            for e in pending[n + 1:]:
                if lo <= e[0] < hi:
                    e[0] -= 3


def _move_note(evs, i, t, floor, settings):
    """One note (index i, time t): the edits of _fast. Returns the word
    range (old indexes) that moved down by 3 words for a later move, else
    None."""
    ev = evs[i]
    gap_n = gap_of(ev)
    inst = ev[0] & 0xF
    if inst not in settings or t == floor:
        return None
    grid, style, amount = settings[inst]
    q = max(swing.quantize(t, grid, style, amount), floor)
    if q == t:
        return None
    b = i - 1
    if b < 0:
        raise _Fallback
    wrap = False
    if q > t:
        m, tm = i + 1, t + gap_n
        while tm < q:
            if m >= len(evs) or code(evs[m][0]) == END:
                wrap = True
                break
            tm += gap_of(evs[m])
            m += 1
        if not wrap and m < len(evs) and code(evs[m][0]) == END and tm <= q:
            wrap = True
    if wrap:
        q = floor
        r, tr = 0, 0
        while tr <= q:
            tr += gap_of(evs[r])
            r += 1
        tp = tr - gap_of(evs[r - 1])
    if q < t:
        if not wrap:
            r, tr = i, t
            while True:
                tp = tr - gap_of(evs[r - 1])
                if tp <= q:
                    break
                r, tr = r - 1, tp
                if i - r > HISTORY or r - 1 < 0:
                    raise _Fallback
        if r == i:
            _gap_ok(evs[b], gap_of(evs[b]) - (t - q))
            _gap_ok(ev, gap_n + (t - q))
            evs[b] = with_gap(evs[b], gap_of(evs[b]) - (t - q))
            evs[i] = with_gap(ev, gap_n + (t - q))
        else:
            p = r - 1
            _gap_ok(evs[p], q - tp)
            _gap_ok(ev, tr - q)
            _gap_ok(evs[b], gap_of(evs[b]) + gap_n)
            evs[b] = with_gap(evs[b], gap_of(evs[b]) + gap_n)
            evs[p] = with_gap(evs[p], q - tp)
            del evs[i]
            evs.insert(r, with_gap(ev, tr - q))
        return None
    if m == i + 1:
        _gap_ok(evs[b], gap_of(evs[b]) + (q - t))
        _gap_ok(ev, gap_n - (q - t))
        evs[b] = with_gap(evs[b], gap_of(evs[b]) + (q - t))
        evs[i] = with_gap(ev, gap_n - (q - t))
        return None
    last = m - 1
    tl = tm - gap_of(evs[last])
    _gap_ok(evs[b], gap_of(evs[b]) + gap_n)
    _gap_ok(evs[last], q - tl)
    _gap_ok(ev, tm - q)
    lo = sum(len(e) for e in evs[:i + 1])        # old word range that moves
    hi = sum(len(e) for e in evs[:m])
    evs[b] = with_gap(evs[b], gap_of(evs[b]) + gap_n)
    evs[last] = with_gap(evs[last], q - tl)
    del evs[i]
    evs.insert(last, with_gap(ev, tm - q))
    return lo, hi
