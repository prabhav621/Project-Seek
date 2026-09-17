from typing import List, Protocol
from google import genai
from src.config import settings

class Embedder(Protocol):
    def embed_text(self, text: str) -> List[float]:
        """Embeds text and returns a float vector."""
        ...
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embeds a batch of texts."""
        ...

class GeminiEmbedder:
    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_id = "gemini-embedding-2"

    def embed_text(self, text: str) -> List[float]:
        response = self.client.models.embed_content(
            model=self.model_id,
            contents=text,
            config={"output_dimensionality": 768}
        )
        return response.embeddings[0].values

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        response = self.client.models.embed_content(
            model=self.model_id,
            contents=texts,
            config={"output_dimensionality": 768}
        )
        return [emb.values for emb in response.embeddings]

def get_embedder() -> Embedder:
    """Returns the default embedding provider adapter."""
    return GeminiEmbedder()
