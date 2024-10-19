import logging

from tts_interface import TTSInterface

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NullTTS(TTSInterface):
    def __init__(self):
        self._is_open = False

    async def initialize(self):
        self._is_open = True
        logger.info("NullTTS initialized. This one doesn't actually do TTS!")

    async def synthesize(self, content):
        logger.info(f"NullTTS faking synthesizing content: {content}")

    async def close(self):
        self._is_open = False
        logger.info("NullTts closed.")

    @property
    def is_open(self) -> bool:
        return self._is_open