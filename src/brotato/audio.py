"""Procedural numpy SFX synthesizer with optional custom audio pack overrides."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict

import numpy as np
import pygame


class SoundBank:
    """Generates crisp procedural SFX at startup and throttles rapid overlapping triggers."""

    def __init__(self, custom_assets: dict[str, Path] | None = None, enabled: bool = True) -> None:
        self.enabled = enabled
        self.muted = False
        self.volume = 0.35
        self._sounds: Dict[str, pygame.mixer.Sound] = {}
        self._last_played: Dict[str, float] = {}
        self._min_intervals: Dict[str, float] = {
            "shoot": 0.045,
            "melee": 0.055,
            "hit": 0.04,
            "crit": 0.05,
            "pickup": 0.04,
            "hurt": 0.15,
            "levelup": 0.15,
            "buy": 0.05,
            "reroll": 0.05,
            "explosion": 0.06,
            "crate": 0.12,
            "boss": 0.3,
        }

        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        except Exception:
            self.enabled = False
            return

        self._build_all(custom_assets or {})

    def _to_sound(self, mono: np.ndarray) -> pygame.mixer.Sound:
        clipped = np.clip(mono, -1.0, 1.0)
        pcm = (clipped * 26000.0).astype(np.int16)
        stereo = np.column_stack((pcm, pcm))
        snd = pygame.sndarray.make_sound(stereo)
        snd.set_volume(self.volume)
        return snd

    def _synth_sweep(self, f0: float, f1: float, dur: float, wave: str = "square", amp: float = 0.5) -> np.ndarray:
        sr = 44100
        n = int(sr * dur)
        t = np.linspace(0.0, dur, n, endpoint=False)
        freqs = np.linspace(f0, f1, n)
        phase = 2.0 * np.pi * np.cumsum(freqs) / sr
        if wave == "sine":
            sig = np.sin(phase)
        elif wave == "saw":
            sig = 2.0 * ((phase / (2.0 * np.pi)) % 1.0) - 1.0
        else:
            sig = np.sign(np.sin(phase))
        env = np.exp(-4.5 * t / dur)
        return sig * env * amp

    def _synth_noise(self, dur: float, amp: float = 0.5, decay: float = 6.0) -> np.ndarray:
        sr = 44100
        n = int(sr * dur)
        t = np.linspace(0.0, dur, n, endpoint=False)
        rng = np.random.default_rng(42)
        noise = rng.uniform(-1.0, 1.0, n)
        # Mild lowpass smoothing
        kernel = np.ones(4) / 4.0
        noise = np.convolve(noise, kernel, mode="same")
        env = np.exp(-decay * t / dur)
        return noise * env * amp

    def _build_all(self, custom_assets: dict[str, Path]) -> None:
        presets = {
            "shoot": self._synth_sweep(560, 160, 0.085, "square", 0.30) + self._synth_noise(0.05, 0.18),
            "melee": self._synth_sweep(340, 110, 0.095, "saw", 0.25) + self._synth_noise(0.08, 0.20),
            "hit": self._synth_sweep(210, 85, 0.055, "sine", 0.28) + self._synth_noise(0.04, 0.14),
            "crit": self._synth_sweep(680, 980, 0.09, "square", 0.34),
            "hurt": self._synth_sweep(220, 65, 0.22, "saw", 0.45) + self._synth_noise(0.18, 0.25),
            "pickup": self._synth_sweep(620, 1080, 0.07, "sine", 0.26),
            "levelup": np.concatenate([
                self._synth_sweep(440, 440, 0.08, "square", 0.30),
                self._synth_sweep(554, 554, 0.08, "square", 0.30),
                self._synth_sweep(659, 880, 0.18, "square", 0.34),
            ]),
            "buy": self._synth_sweep(520, 780, 0.10, "sine", 0.32),
            "reroll": self._synth_sweep(300, 460, 0.09, "saw", 0.24),
            "explosion": self._synth_sweep(130, 38, 0.28, "saw", 0.42) + self._synth_noise(0.28, 0.45, decay=4.0),
            "crate": np.concatenate([
                self._synth_sweep(523, 659, 0.09, "sine", 0.32),
                self._synth_sweep(784, 1046, 0.15, "sine", 0.34),
            ]),
            "boss": self._synth_sweep(150, 55, 0.45, "saw", 0.45),
        }

        for name, wave in presets.items():
            custom_key = f"sounds/{name}"
            if custom_key in custom_assets:
                try:
                    snd = pygame.mixer.Sound(str(custom_assets[custom_key]))
                    snd.set_volume(self.volume)
                    self._sounds[name] = snd
                    continue
                except Exception:
                    pass
            try:
                self._sounds[name] = self._to_sound(wave)
            except Exception:
                pass

    def play(self, name: str) -> None:
        if not self.enabled or self.muted:
            return
        snd = self._sounds.get(name)
        if snd is None:
            return
        now = time.monotonic()
        min_gap = self._min_intervals.get(name, 0.05)
        if now - self._last_played.get(name, 0.0) < min_gap:
            return
        self._last_played[name] = now
        snd.play()

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))
        for snd in self._sounds.values():
            snd.set_volume(self.volume)
