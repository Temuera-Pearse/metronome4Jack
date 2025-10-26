"""
Application entrypoint. Initializes pygame and runs the metronome asynchronously.
Default demo uses start=120 BPM, end=140 BPM over 60 seconds.
"""

import asyncio
import platform
import pygame
import audio
from metronome import Metronome

async def app_main():
    # Initialize pygame modules (no display needed)
    pygame.init()
    # Initialize audio mixer
    audio.init_mixer()
    # Pre-generate click sound
    click = audio.get_default_click()
    # Create metronome: default ramp 120 -> 140 BPM over 60s for testing
    metro = Metronome(start_bpm=120.0, end_bpm=140.0, ramp_duration=60.0, click_sound=click)
    # Run metronome; you can pass max_beats for short demos, None for indefinite
    await metro.run(max_beats=None)

def run_app():
    """
    Run the async app. In Pyodide/Emscripten we schedule the coroutine without blocking.
    In desktop Python we use asyncio.run.
    """
    if platform.system() == "Emscripten":
        # In Pyodide, event loop is already running in the browser; schedule the task
        loop = asyncio.get_event_loop()
        loop.create_task(app_main())
        print("Metronome scheduled on Pyodide event loop.")
    else:
        asyncio.run(app_main())

if __name__ == "__main__":
    run_app()
