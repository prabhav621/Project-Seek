from src.utils.retry import generate_content_with_retry
import os
import logging
from typing import Optional
from google import genai
from google.genai import types
from src.config import settings

logger = logging.getLogger(__name__)

class MediaTranscriber:
    def __init__(self):
        self.gemini_client = genai.Client(api_key=settings.gemini_api_key)
        self.whisper_model = None

    def transcribe(self, file_path: str) -> Optional[str]:
        """
        Transcribe an audio or video file using Gemini (configured via ModelTier in config.py).
        Falls back to local faster-whisper on failure.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Media file not found: {file_path}")

        try:
            return self._transcribe_with_gemini(file_path)
        except Exception as e:
            logger.warning(f"Gemini transcription failed: {e}. Falling back to faster-whisper.")
            return self._transcribe_with_whisper(file_path)

    def _transcribe_with_gemini(self, file_path: str) -> str:
        """Uses Gemini native audio/video understanding via google-genai SDK (configured via ModelTier in config.py)."""
        # Upload the file to Gemini's File API
        gemini_file = self.gemini_client.files.upload(file=file_path)
        
        try:
            prompt = "Please provide a highly accurate transcription of the audio in this file. Output ONLY the transcript without any extra commentary or formatting."
            
            from src.config import ModelTier
            # Strip "gemini/" prefix since this uses the direct Google SDK (for File API)
            raw_model = ModelTier.FLASH.value.replace("gemini/", "")
            response = generate_content_with_retry(self.gemini_client, 
                model=raw_model,
                contents=[
                    gemini_file,
                    prompt
                ]
            )
            return response.text.strip()
        finally:
            # Clean up the file from Gemini storage
            try:
                self.gemini_client.files.delete(name=gemini_file.name)
            except Exception as cleanup_error:
                logger.error(f"Failed to delete file {gemini_file.name} from Gemini: {cleanup_error}")

    def _transcribe_with_whisper(self, file_path: str) -> str:
        """Fallback transcription using local faster-whisper."""
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError("faster-whisper is not installed. Cannot use fallback transcription.")

        # Lazy load the whisper model to save VRAM unless needed
        if self.whisper_model is None:
            logger.info("Loading faster-whisper model...")
            # Running on CPU with int8 to accommodate the limited VRAM (RTX 3050 4GB)
            self.whisper_model = WhisperModel("base", device="cpu", compute_type="int8")

        logger.info(f"Transcribing {file_path} with faster-whisper...")
        segments, info = self.whisper_model.transcribe(file_path, beam_size=5)
        
        transcript = " ".join([segment.text.strip() for segment in segments])
        return transcript.strip()

def transcribe_media(file_path: str) -> Optional[str]:
    """Convenience function for transcribing media."""
    transcriber = MediaTranscriber()
    return transcriber.transcribe(file_path)
