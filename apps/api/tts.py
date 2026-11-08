"""Natural offline voice for the agent's replies: Piper neural text to speech, run on this machine.

Two voices: Hindi (hi, also speaks the Devanagari form of Hinglish replies and reads English dish names
the English way) and English (en). Voice files live in data/models/piper and are downloaded by
`python tasks.py models`. Nothing leaves the machine. When a voice file is missing, the Call desk falls
back to the browser's own voice.

Replies come from fixed templates, so the same sentences repeat; synthesised audio is cached in memory.
"""
from __future__ import annotations

import io
import logging
import threading
import wave
from collections import OrderedDict
from pathlib import Path

import settings

log = logging.getLogger("tadka.tts")
CACHE_SIZE = 256
MAX_CHARS = 400


class NothingToSay(ValueError):
    """The text has nothing the voice can speak."""


class Tts:
    def __init__(self, voices: dict[str, Path]):
        self.paths = voices
        self._voices: dict[str, object] = {}
        self._lock = threading.Lock()
        self._cache: OrderedDict[tuple[str, str], bytes] = OrderedDict()

    def available(self) -> dict[str, bool]:
        return {lang: p.exists() and Path(str(p) + ".json").exists() for lang, p in self.paths.items()}

    def _voice(self, lang: str):
        if lang not in self._voices:
            from piper import PiperVoice  # imported lazily: the API runs without Piper installed

            self._voices[lang] = PiperVoice.load(self.paths[lang])
        return self._voices[lang]

    def warm(self) -> None:
        """Load the voices in the background so the first reply of the day is not slow."""
        def run():
            for lang, ok in self.available().items():
                if ok:
                    try:
                        with self._lock:
                            self._voice(lang)
                    except Exception:  # a broken voice file must not stop the API
                        log.exception("Could not load the %s voice", lang)
        threading.Thread(target=run, name="tts-warm", daemon=True).start()

    def wav(self, text: str, lang: str) -> bytes:
        text = " ".join(text.split())[:MAX_CHARS]
        key = (lang, text)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            voice = self._voice(lang)
            buf = io.BytesIO()
            try:
                with wave.open(buf, "wb") as w:
                    voice.synthesize_wav(text, w)
            except wave.Error:  # nothing speakable (only punctuation, say): Piper wrote no audio
                raise NothingToSay(text) from None
            audio = buf.getvalue()
            self._cache[key] = audio
            if len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
            return audio


_engine: Tts | None = None


def get_tts() -> Tts:
    global _engine
    if _engine is None:
        _engine = Tts({"hi": settings.PIPER_DIR / settings.PIPER_VOICE_HI, "en": settings.PIPER_DIR / settings.PIPER_VOICE_EN})
    return _engine
