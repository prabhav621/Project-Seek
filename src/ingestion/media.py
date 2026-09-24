from src.utils.retry import generate_content_with_retry
import os
import logging
from typing import Optional, List
from google import genai
from src.config import settings

logger = logging.getLogger(__name__)

class MediaTranscriber:
    def __init__(self):
        self.gemini_client = genai.Client(api_key=settings.gemini_api_key)
        self.whisper_model = None

    def transcribe(self, file_path: str) -> Optional[str]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Media file not found: {file_path}")
        try:
            return self._transcribe_with_gemini(file_path)
        except Exception as e:
            logger.warning(f"Gemini transcription failed: {e}. Falling back to faster-whisper.")
            return self._transcribe_with_whisper(file_path)

    def _transcribe_with_gemini(self, file_path: str) -> str:
        gemini_file = self.gemini_client.files.upload(file=file_path)
        try:
            prompt = "Please provide a highly accurate transcription of the audio in this file. Output ONLY the transcript without any extra commentary or formatting."
            from src.config import ModelTier
            raw_model = ModelTier.FLASH.value.replace("gemini/", "")
            response = generate_content_with_retry(self.gemini_client, 
                model=raw_model,
                contents=[gemini_file, prompt]
            )
            return response.text.strip()
        finally:
            try:
                self.gemini_client.files.delete(name=gemini_file.name)
            except Exception as cleanup_error:
                logger.error(f"Failed to delete file {gemini_file.name} from Gemini: {cleanup_error}")

    def _transcribe_with_whisper(self, file_path: str) -> str:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError("faster-whisper is not installed. Cannot use fallback transcription.")
        if self.whisper_model is None:
            logger.info("Loading faster-whisper model...")
            self.whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info(f"Transcribing {file_path} with faster-whisper...")
        segments, info = self.whisper_model.transcribe(file_path, beam_size=5)
        transcript = " ".join([segment.text.strip() for segment in segments])
        return transcript.strip()

    def analyze_images(self, file_paths: List[str]) -> Optional[str]:
        gemini_files = []
        try:
            for path in file_paths:
                if os.path.exists(path):
                    gemini_files.append(self.gemini_client.files.upload(file=path))
                    
            if not gemini_files:
                return None

            prompt = "Extract all visible text from these images sequentially. If an image contains no text but conveys meaning (like an infographic, chart, or scene), briefly describe what it shows. Label each slide (e.g., 'Slide 1:', 'Slide 2:'). Output ONLY the combined text and descriptions."
            
            from src.config import ModelTier
            raw_model = ModelTier.FLASH.value.replace("gemini/", "")
            
            contents = gemini_files + [prompt]
            
            response = generate_content_with_retry(self.gemini_client, 
                model=raw_model,
                contents=contents
            )
            return response.text.strip()
        finally:
            for gf in gemini_files:
                try:
                    self.gemini_client.files.delete(name=gf.name)
                except Exception as cleanup_error:
                    logger.error(f"Failed to delete image {gf.name} from Gemini: {cleanup_error}")

def transcribe_media(file_path: str) -> Optional[str]:
    transcriber = MediaTranscriber()
    return transcriber.transcribe(file_path)

def analyze_images(file_paths: List[str]) -> Optional[str]:
    transcriber = MediaTranscriber()
    return transcriber.analyze_images(file_paths)
