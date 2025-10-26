"""
Audio utilities: initialize mixer and generate a short sine click.
No file I/O. Returns pygame.mixer.Sound objects created from NumPy arrays.
"""

import numpy as np
import pygame
import config

_default_click_sound = None

def init_mixer(sample_rate=config.SAMPLE_RATE):
    """
    Initialize pygame mixer with given sample rate.
    Safe to call multiple times.
    """
    # Use common default buffer size; small buffer helps latency but may increase CPU.
    try:
        pygame.mixer.pre_init(frequency=sample_rate, size=-16, channels=1)
        pygame.mixer.init()
    except Exception as e:
        # In Pyodide/other restricted envs this might still succeed differently; re-raise for visibility.
        raise RuntimeError(f"Failed to init pygame.mixer: {e}")

def generate_click(freq=1000, duration=config.CLICK_DURATION, sample_rate=config.SAMPLE_RATE, volume=0.5):
    """
    Generate a short sine click as a pygame Sound.
    Returns a pygame.mixer.Sound instance.
    """
    n_samples = int(duration * sample_rate)
    if n_samples <= 0:
        n_samples = 1
    t = np.linspace(0, duration, n_samples, endpoint=False)
    # sine wave; apply a short linear fade-out to avoid clicks
    wave = np.sin(2 * np.pi * freq * t)
    # simple envelope: linear fade in/out 2 ms
    fade_ms = min(0.002, duration / 2)
    fade_samples = int(fade_ms * sample_rate)
    if fade_samples > 0:
        envelope = np.ones_like(wave)
        envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
        envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
        wave *= envelope
    # scale to int16
    max_int16 = np.iinfo(np.int16).max
    samples = (wave * (volume * 0.9) * max_int16).astype(np.int16)
    # pygame.sndarray.make_sound expects a 1D or 2D array
    try:
        sound = pygame.sndarray.make_sound(samples)
    except Exception:
        # If mixer expects 2D arrays for stereo, expand dims (safe fallback)
        stereo = np.column_stack([samples, samples])
        sound = pygame.sndarray.make_sound(stereo)
    return sound

def get_default_click():
    """
    Lazily create and return a default click Sound.
    """
    global _default_click_sound
    if _default_click_sound is None:
        _default_click_sound = generate_click()
    return _default_click_sound
