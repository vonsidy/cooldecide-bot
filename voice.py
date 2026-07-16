"""Text-to-speech via edge-tts (free). Returns an mp3 path."""
from __future__ import annotations
import asyncio

import edge_tts

import config


async def _run(text: str, out_path: str) -> None:
    comm = edge_tts.Communicate(text, config.EDGE_VOICE, rate=config.EDGE_RATE)
    await comm.save(out_path)


def say(text: str, out_path: str) -> str:
    asyncio.run(_run(text, out_path))
    return out_path
