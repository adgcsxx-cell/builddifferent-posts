"""Original background sound for Reels.

A soft lo-fi bed (electric-piano chords, pad, bass, light drums) plus effects that follow the edit
(impact on the first frame, whooshes into scene changes, a rising blip per line of text, a chime on
the follow ending). Everything is synthesized here from sine waves and noise, so there is nothing
to license and no copyright question.

    render(duration, events, path, breakdown_at=None)   -> writes a 48 kHz stereo 16-bit WAV

events: list of (seconds, kind, arg) with kind in impact | whoosh | blip | pop | chime.
"""
import json
import subprocess
import wave

import numpy as np
from scipy import signal

SR = 48000
BPM = 92
BEAT = 60.0 / BPM
BAR = 4 * BEAT
TARGET_LUFS = -16.0

# A minor, lo-fi voicings (MIDI). i - VI - III - VII: Am9, Fmaj7, Cmaj7, G6
CHORDS = [
    {"bass": 45, "notes": [57, 60, 64, 67, 71]},   # Am9  (A C E G B)
    {"bass": 41, "notes": [53, 57, 60, 64]},       # Fmaj7 (F A C E)
    {"bass": 48, "notes": [55, 59, 64, 67]},       # Cmaj7 (G B E G)
    {"bass": 43, "notes": [55, 59, 62, 64]},       # G6 (G B D E)
]
BLIP_NOTES = [81, 84, 86, 88, 91, 93]              # A5 C6 D6 E6 G6 A6 (A minor pentatonic)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def _t(n):
    return np.arange(n) / SR


def _lp(x, fc, order=2):
    sos = signal.butter(order, fc, "low", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def _hp(x, fc, order=2):
    sos = signal.butter(order, fc, "high", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def _bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], "band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def _biquad(x, b, a):
    return signal.lfilter(np.array(b) / a[0], np.array(a) / a[0], x, axis=-1)


def _shelf(x, f0, gain_db, kind):
    """RBJ cookbook low/high shelf (slope 1)."""
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / SR
    cw, al = np.cos(w0), np.sin(w0) / 2 * np.sqrt(2)
    sa = 2 * np.sqrt(A) * al
    if kind == "low":
        b = [A * ((A + 1) - (A - 1) * cw + sa), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - sa)]
        a = [(A + 1) + (A - 1) * cw + sa, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - sa]
    else:
        b = [A * ((A + 1) + (A - 1) * cw + sa), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - sa)]
        a = [(A + 1) - (A - 1) * cw + sa, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - sa]
    return _biquad(x, b, a)


def _peak(x, f0, gain_db, q):
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / SR
    al = np.sin(w0) / (2 * q)
    b = [1 + al * A, -2 * np.cos(w0), 1 - al * A]
    a = [1 + al / A, -2 * np.cos(w0), 1 - al / A]
    return _biquad(x, b, a)


def master_eq(x):
    """Voice the mix for phone speakers: less sub, a little more presence and air."""
    x = _hp(x, 42)
    x = _shelf(x, 120, -6.0, "low")
    x = _peak(x, 2600, 3.0, 0.8)
    return _shelf(x, 7000, 2.0, "high")


class Bus:
    """Stereo buffer with pan-law placement."""

    def __init__(self, seconds):
        self.n = int(seconds * SR)
        self.x = np.zeros((2, self.n))

    def add(self, sig, at, gain=1.0, pan=0.0):
        i = int(round(at * SR))
        if i >= self.n or i + len(sig) <= 0:
            return
        s = sig[max(0, -i):]
        i = max(0, i)
        s = s[: self.n - i]
        th = (pan + 1) * np.pi / 4
        self.x[0, i:i + len(s)] += s * gain * np.cos(th)
        self.x[1, i:i + len(s)] += s * gain * np.sin(th)


# ------------------------------------------------------------ instruments --
def ep_note(f, dur, vel=1.0, detune=0.0):
    """FM electric piano: carrier:modulator 1:1 with a decaying index, plus a short tine."""
    n = int((dur + 0.9) * SR)
    t = _t(n)
    f = f * (1 + detune)
    index = 2.0 * np.exp(-t * 2.4) + 0.35
    y = np.sin(2 * np.pi * f * t + index * np.sin(2 * np.pi * f * t))
    y += 0.06 * np.sin(2 * np.pi * f * 4.0 * t) * np.exp(-t * 20)
    amp = (1 - np.exp(-t * 300)) * np.exp(-t * 1.25)
    k = int(dur * SR)
    amp[k:] *= np.exp(-(t[k:] - dur) * 7.0)
    trem = 1 + 0.06 * np.sin(2 * np.pi * 4.2 * t)
    return vel * y * amp * trem


def pad_chord(freqs, dur):
    n = int((dur + 1.2) * SR)
    t = _t(n)
    y = np.zeros(n)
    for f in freqs:
        for det in (-0.0035, 0.0035):
            ff = f * (1 + det)
            y += np.sin(2 * np.pi * ff * t) + np.sin(2 * np.pi * 3 * ff * t) / 9
    env = np.minimum(1, t / 0.6)
    k = int(dur * SR)
    env[k:] *= np.exp(-(t[k:] - dur) * 3.5)
    return _lp(y * env / (2 * len(freqs)), 1600)


def bass_note(f, dur, vel=1.0):
    n = int((dur + 0.25) * SR)
    t = _t(n)
    # strong 2nd/3rd harmonics so the bass line is still heard on phone speakers
    y = np.sin(2 * np.pi * f * t) + 0.55 * np.sin(4 * np.pi * f * t) + 0.3 * np.sin(6 * np.pi * f * t)
    amp = (1 - np.exp(-t * 250)) * np.exp(-t * 1.1)
    k = int(dur * SR)
    amp[k:] *= np.exp(-(t[k:] - dur) * 25)
    return _lp(vel * y * amp, 900)


def kick(vel=1.0, rng=None):
    n = int(0.5 * SR)
    t = _t(n)
    f = 47 + 95 * np.exp(-t * 32)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8.5)
    click = _hp(rng.standard_normal(n), 2500) * np.exp(-t * 380) * 0.35
    return vel * (body + click) * (1 - np.exp(-t * 3000))


def snare(vel=1.0, rng=None):
    n = int(0.35 * SR)
    t = _t(n)
    noise = _bp(rng.standard_normal(n), 900, 6500) * np.exp(-t * 19)
    body = np.sin(2 * np.pi * 188 * t) * np.exp(-t * 30)
    return vel * (0.55 * noise + 0.45 * body) * (1 - np.exp(-t * 2500))


def hat(vel=1.0, rng=None):
    n = int(0.09 * SR)
    t = _t(n)
    return vel * _hp(rng.standard_normal(n), 7500) * np.exp(-t * 75)


# --------------------------------------------------------------- effects ---
def impact(rng):
    n = int(1.3 * SR)
    t = _t(n)
    f = 38 + 72 * np.exp(-t * 9)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.0)
    dust = _lp(rng.standard_normal(n), 1400) * np.exp(-t * 11) * 0.45
    return (boom + dust) * (1 - np.exp(-t * 2000))


def whoosh(rng, dur=0.5, f0=350.0, f1=5200.0):
    n = int(dur * SR)
    x = rng.standard_normal(n + 2048)
    f, tt, z = signal.stft(x, SR, nperseg=1024, noverlap=896)
    fpos = np.maximum(f, 1.0)
    for j, tj in enumerate(tt):
        q = min(1.0, max(0.0, tj / dur))
        fc = f0 * (f1 / f0) ** q
        z[:, j] *= np.exp(-0.5 * (np.log(fpos / fc) / 0.42) ** 2)
    _, y = signal.istft(z, SR, nperseg=1024, noverlap=896)
    y = y[:n]
    t = _t(n) / dur
    env = np.sin(np.pi * np.clip(t, 0, 1) ** 0.8) ** 2
    return y * env / (np.max(np.abs(y * env)) + 1e-9)


def blip(midi):
    """Soft marimba-like note: fundamental plus a quiet partial near 4x."""
    n = int(0.45 * SR)
    t = _t(n)
    f = hz(midi)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 11) + 0.18 * np.sin(2 * np.pi * 3.98 * f * t) * np.exp(-t * 45)
    return y * (1 - np.exp(-t * 900))


def pop():
    n = int(0.16 * SR)
    t = _t(n)
    f = 420 + 820 * (1 - np.exp(-t * 55))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30) * (1 - np.exp(-t * 1500))


def bell(f, dur=2.2):
    n = int(dur * SR)
    t = _t(n)
    idx = 1.8 * np.exp(-t * 3.2)
    y = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * 3.5 * f * t))
    return y * np.exp(-t * 2.1) * (1 - np.exp(-t * 800))


def reverb_ir(seconds=1.6, rt60=1.5, seed=11):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = _t(n)
    decay = np.exp(-6.9 * t / rt60)
    pre = int(0.018 * SR)
    irs = []
    for _ in range(2):
        ir = np.zeros(n)
        ir[pre:] = (rng.standard_normal(n - pre) * decay[: n - pre])
        ir = _lp(ir, 4800)
        irs.append(ir / np.sqrt(np.sum(ir ** 2)))
    return irs


# ------------------------------------------------------------------ music ---
def music(seconds, breakdown_at=None, seed=5):
    """The bed: EP chords, pad, bass, drums. Drums drop out at `breakdown_at` (the follow ending)."""
    rng = np.random.default_rng(seed)
    keys, drums, low = Bus(seconds), Bus(seconds), Bus(seconds)
    bars = int(np.ceil(seconds / BAR)) + 1
    for b in range(bars):
        ch = CHORDS[b % len(CHORDS)]
        t0 = b * BAR
        # chord hits: beat 1 (full) and the "and" of 3 (upper notes, softer)
        for k, m in enumerate(ch["notes"]):
            jitter = rng.uniform(-0.008, 0.008) + k * 0.012            # slight strum
            keys.add(ep_note(hz(m), BEAT * 2.2, 0.9 * rng.uniform(0.85, 1.0), detune=0.0015),
                     t0 + jitter, gain=0.24, pan=-0.35 + 0.7 * k / max(1, len(ch["notes"]) - 1))
        for k, m in enumerate(ch["notes"][-3:]):
            keys.add(ep_note(hz(m), BEAT * 1.2, 0.6 * rng.uniform(0.8, 1.0), detune=-0.0015),
                     t0 + 2.5 * BEAT + k * 0.01 + rng.uniform(-0.006, 0.006), gain=0.18, pan=0.25 - 0.25 * k)
        keys.add(pad_chord([hz(m + 12) for m in ch["notes"][:3]], BAR), t0, gain=0.10)
        # bass: beats 1 and 3
        low.add(bass_note(hz(ch["bass"]), BEAT * 1.8, 1.0), t0, gain=0.2)
        low.add(bass_note(hz(ch["bass"]), BEAT * 1.4, 0.8), t0 + 2 * BEAT, gain=0.2)
        # drums
        for beat in range(4):
            tb = t0 + beat * BEAT
            if breakdown_at is not None and tb >= breakdown_at - 0.05:
                continue
            if beat in (0, 2):
                drums.add(kick(1.0 if beat == 0 else 0.85, rng), tb, gain=0.36)
            if beat in (1, 3) and b > 0:
                drums.add(snare(rng.uniform(0.85, 1.0), rng), tb + 0.012, gain=0.28, pan=0.05)
            if beat == 1 and b % 2 == 1:
                drums.add(kick(0.55, rng), tb + 0.5 * BEAT, gain=0.3)      # ghost kick on the "and" of 2
            for half in (0, 1):
                swing = 0.09 * BEAT if half else 0.0
                drums.add(hat(rng.uniform(0.55, 0.8) if half else rng.uniform(0.8, 1.0), rng),
                          tb + half * 0.5 * BEAT + swing, gain=0.1, pan=0.3)
    # gentle ducking of keys under the kick for a bit of groove
    duck = np.ones(keys.n)
    for b in range(bars):
        for beat in (0, 2):
            tb = b * BAR + beat * BEAT
            if breakdown_at is not None and tb >= breakdown_at - 0.05:
                continue
            i = int(tb * SR)
            m = min(keys.n - i, int(0.3 * SR))
            if m > 0:
                duck[i:i + m] *= 1 - 0.22 * np.exp(-_t(m) * 12)
    irl, irr = reverb_ir()
    wet = np.stack([signal.fftconvolve(keys.x[0] + 0.5 * drums.x[0], irl)[: keys.n],
                    signal.fftconvolve(keys.x[1] + 0.5 * drums.x[1], irr)[: keys.n]])
    return keys.x * duck + drums.x + low.x + 0.22 * wet


def effects(seconds, events, seed=9):
    rng = np.random.default_rng(seed)
    fx = Bus(seconds)
    for ev in events:
        at, kind = ev[0], ev[1]
        arg = ev[2] if len(ev) > 2 else None
        if kind == "impact":
            fx.add(impact(rng), at, gain=0.45)
        elif kind == "whoosh":
            w = whoosh(rng)
            fx.add(w, at - 0.32, gain=0.11, pan=-0.3)                     # peaks on the cut
            fx.add(whoosh(rng), at - 0.30, gain=0.11, pan=0.3)
        elif kind == "blip":
            fx.add(blip(BLIP_NOTES[min(int(arg or 0), len(BLIP_NOTES) - 1)]), at, gain=0.16,
                   pan=-0.15 + 0.1 * (arg or 0))
        elif kind == "pop":
            fx.add(pop(), at, gain=0.2)
        elif kind == "chime":
            fx.add(bell(hz(88)), at, gain=0.09, pan=-0.2)
            fx.add(bell(hz(83)), at + 0.09, gain=0.08, pan=0.2)
    irl, irr = reverb_ir(seed=17)
    wet = np.stack([signal.fftconvolve(fx.x[0], irl)[: fx.n], signal.fftconvolve(fx.x[1], irr)[: fx.n]])
    return fx.x + 0.25 * wet


# ---------------------------------------------------------------- master ---
def loudness(path):
    """Integrated loudness (LUFS) and true peak (dBTP) of a WAV, measured by ffmpeg's EBU R128 filter."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
                          "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    js = json.loads(out[out.rindex("{"): out.rindex("}") + 1])
    return float(js["input_i"]), float(js["input_tp"])


def _write(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16).T.copy()
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def render(seconds, events, path, breakdown_at=None):
    """Mix bed + effects, master to about TARGET_LUFS with peaks below -1.5 dBTP, write WAV."""
    x = music(seconds, breakdown_at) + effects(seconds, events)
    x = master_eq(x)
    x -= x.mean(axis=1, keepdims=True)
    fade_in, fade_out = int(0.006 * SR), int(0.7 * SR)
    x[:, :fade_in] *= np.linspace(0, 1, fade_in)
    x[:, -fade_out:] *= np.linspace(1, 0, fade_out) ** 1.5
    x /= np.max(np.abs(x)) + 1e-9
    x *= 0.5
    _write(path, x)
    lufs, _ = loudness(path)
    x *= 10 ** ((TARGET_LUFS - lufs) / 20)
    peak = np.max(np.abs(x))
    ceiling = 10 ** (-2.0 / 20)
    if peak > ceiling:                                   # soft-limit the few peaks above the ceiling
        k = ceiling * 0.8
        over = np.abs(x) > k
        x[over] = np.sign(x[over]) * (k + (ceiling - k) * np.tanh((np.abs(x[over]) - k) / (ceiling - k)))
    _write(path, x)
    return loudness(path)
