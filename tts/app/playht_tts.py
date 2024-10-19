import websockets
import json
import os
import logging
import requests
import asyncio
import hashlib
from tts_interface import TTSInterface

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PLAYHT_API_KEY = os.getenv("PLAYHT_API_KEY", '')
PLAYHT_USER_ID = os.getenv("PLAYHT_USER_ID", '')
PLAYHT_VOICE_ID = os.getenv('PLAYHT_VOICE_ID', '')
TTS_SAMPLE_RATE = os.getenv('TTS_SAMPLE_RATE', '24000')

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_key(content):
    return hashlib.md5(content.encode('utf-8')).hexdigest()

class PlayHtTTS(TTSInterface):
    def __init__(self):
        self._is_open = False
        self.playht_ws = None
        self.playht_endpoint = None

    async def initialize(self):
        self._is_open = True
        # TODO: fill this request in....
        self.playht_endpoint = requests.post("https://api.play.ht/api/v3/websocket-auth", headers={
            "Authorization": "Bearer",
            "X-User-Id": PLAYHT_USER_ID,
            "Content-Type": "application/json"
        }).json()["websocket_url"]
        logger.info("PlayHtTTS initialized.")

    async def synthesize(self, content):
        cache_key = get_cache_key(content)
        cache_path = os.path.join(CACHE_DIR, f"{cache_key}.pcm")

        if os.path.exists(cache_path):
            logger.info("Cache hit, sending cached audio")
            with open(cache_path, "rb") as f:
                while chunk := f.read(4096):
                    yield chunk
            return

        self.playht_ws = await websockets.connect(self.playht_endpoint)
        logger.info("Connected to playht websocket")

        try:
            input_message = {
                "voice": PLAYHT_VOICE_ID,
                "xi_api_key": PLAYHT_API_KEY,
                "text": content,
                "output_format": "wav",
                "speed": 0.8
                # "temperature": 0.7
            }
            await self.playht_ws.send(json.dumps(input_message))
            logger.info("Sent initial message to playht")

            eos_message = {"text": ""}
            await self.playht_ws.send(json.dumps(eos_message))
            logger.info("Sent EOS message to playht")

            with open(cache_path, "wb") as f:
                while True:
                    try:
                        response = await self.playht_ws.recv()
                        data = json.loads(response)
                        if isinstance(response, bytes):#"audio" in data and data["audio"] is not None:
                            audio_data = response
                            logger.info(f"Received audio chunk from playht of size: {len(audio_data)}")
                            f.write(audio_data)
                            # TODO: We might need to collect these all into one file before yielding; need to see if that's the way this is intended to be used or not
                            yield audio_data
                        elif ("request_id" in response) :
                            logger.info("No more audio data.")
                            break
                        else :
                            logger.error(f"error from playht ws: {response}")

                    except json.JSONDecodeError:
                        logger.warning("Failed to parse EOS response as JSON")
                        break
                    except asyncio.CancelledError:
                        logger.info("Synthesis task was cancelled")
                        break
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed")
        except Exception as e:
            logger.exception("An error occurred while receiving data from playht")
        finally:
            await self.playht_ws.close()
            self.playht_ws = None

    async def close(self):
        self._is_open = False
        if self.playht_ws:
            await self.playht_ws.close()
        logger.info("PlayHtTTS connection closed.")

    @property
    def is_open(self) -> bool:
        return self._is_open