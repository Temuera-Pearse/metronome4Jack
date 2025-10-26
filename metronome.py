"""
Metronome core logic.
Supports constant BPM and linear ramping between start_bpm and end_bpm over ramp_duration seconds.

Beat timestamps are computed precisely:
- For ramping region we solve for t in (1/60)*(b0*t + 0.5*m*t^2) = k (k = beat count)
  which yields a quadratic solution:
    t_k = (-b0 + sqrt(b0^2 + 120*m*k)) / m   (if m != 0)
- After ramp ends, beats continue at constant end_bpm.
"""

import math
import asyncio
import pygame
import time
import config
import audio

class Metronome:
    def __init__(self, start_bpm=120.0, end_bpm=None, ramp_duration=0.0, click_sound=None):
        """
        start_bpm: starting BPM (float)
        end_bpm: ending BPM; if None -> constant mode (end_bpm == start_bpm)
        ramp_duration: seconds over which to linearly change BPM from start_bpm to end_bpm
        click_sound: pygame.mixer.Sound to play for each beat
        """
        if end_bpm is None:
            end_bpm = start_bpm
        # Validation
        if not (40 <= start_bpm <= 200):
            raise ValueError("start_bpm must be between 40 and 200")
        if not (40 <= end_bpm <= 200):
            raise ValueError("end_bpm must be between 40 and 200")
        if ramp_duration < 0:
            raise ValueError("ramp_duration must be >= 0")
        if ramp_duration == 0:
            end_bpm = start_bpm  # treat as constant

        self.start_bpm = float(start_bpm)
        self.end_bpm = float(end_bpm)
        self.ramp_duration = float(ramp_duration)
        self.click_sound = click_sound or audio.get_default_click()

        # slope m in BPM per second
        if self.ramp_duration > 0:
            self.m = (self.end_bpm - self.start_bpm) / self.ramp_duration
        else:
            self.m = 0.0

        # Precompute total fractional beats at the end of ramp (may be fractional)
        if self.ramp_duration > 0:
            # B(T) = (1/60)*(b0*T + 0.5*m*T^2)
            self.B_T = (1.0 / 60.0) * (self.start_bpm * self.ramp_duration + 0.5 * self.m * (self.ramp_duration ** 2))
        else:
            self.B_T = 0.0

    def beat_time_for_k(self, k):
        """
        Return the time in seconds since start (t >= 0) when beat index k occurs.
        k is a positive integer (1-based count).
        Uses quadratic solution for ramp section, and linear continuation after ramp.
        """
        if k <= 0:
            raise ValueError("k must be a positive integer")
        b0 = self.start_bpm
        m = self.m
        T = self.ramp_duration

        # Constant BPM case
        if m == 0:
            return (k * 60.0) / b0

        # Solve quadratic: (1/60)*(b0*t + 0.5*m*t^2) = k
        # => 0.5*m*t^2 + b0*t - 60*k = 0
        # t = (-b0 + sqrt(b0^2 + 120*m*k)) / m
        discriminant = b0 * b0 + 120.0 * m * k
        if discriminant < 0:
            # numeric safety (shouldn't happen for valid inputs)
            discriminant = 0.0
        t_candidate = (-b0 + math.sqrt(discriminant)) / m if m != 0 else (k * 60.0 / b0)

        # If candidate occurs before or at ramp end, use it
        if t_candidate <= T:
            return t_candidate

        # Otherwise compute time after ramp using constant end_bpm
        # Number of beats that have happened by time T (may be fractional):
        B_T = self.B_T
        # Additional beats to reach integer k:
        additional_beats = k - B_T
        # Time after ramp:
        seconds_after_ramp = additional_beats * (60.0 / self.end_bpm)
        return T + seconds_after_ramp

    def current_bpm_at(self, t):
        """
        Return instantaneous BPM at time t (seconds since start).
        After ramp end, returns end_bpm.
        """
        if t < 0:
            return self.start_bpm
        if self.ramp_duration <= 0:
            return self.start_bpm
        if t >= self.ramp_duration:
            return self.end_bpm
        return self.start_bpm + self.m * t

    async def run(self, max_beats=None):
        """
        Async run loop. Plays clicks at precise times.
        - Uses pygame.time.get_ticks() for timing.
        - max_beats: optional limit to stop after N beats (useful for testing).
        """
        # Ensure mixer is initialized
        if not pygame.mixer.get_init():
            raise RuntimeError("pygame.mixer is not initialized. Call audio.init_mixer() first.")

        start_ms = pygame.time.get_ticks()
        start_time = start_ms / 1000.0
        beat_index = 1  # 1-based beat counter
        next_beat_time = self.beat_time_for_k(beat_index)  # seconds since start

        # small epsilon to counter scheduling jitter (seconds)
        epsilon = 0.001

        print(f"Metronome start: {self.start_bpm:.2f} -> {self.end_bpm:.2f} over {self.ramp_duration:.2f}s")
        try:
            while True:
                now_ms = pygame.time.get_ticks()
                now = now_ms / 1000.0
                elapsed = now - start_time

                # Play beats that are due (while-loop handles multiple if loop delayed)
                while elapsed + epsilon >= next_beat_time:
                    # Play click
                    try:
                        self.click_sound.play()
                    except Exception as e:
                        print(f"Failed to play click: {e}")

                    current_bpm = self.current_bpm_at(next_beat_time)
                    print(f"Beat {beat_index}: elapsed={next_beat_time:.3f}s bpm={current_bpm:.2f}")

                    beat_index += 1
                    if max_beats and beat_index > max_beats:
                        print("Reached max_beats, stopping.")
                        return
                    next_beat_time = self.beat_time_for_k(beat_index)

                # Pump pygame events (keeps mixer responsive in some ports)
                try:
                    pygame.event.pump()
                except Exception:
                    pass

                # Non-blocking sleep aligned to FPS
                await asyncio.sleep(1.0 / config.FPS)
        except asyncio.CancelledError:
            print("Metronome run cancelled.")
            raise
