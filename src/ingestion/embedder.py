import warnings
from typing import List, Protocol
from sentence_transformers import SentenceTransformer

# Suppress HuggingFace warnings
warnings.filterwarnings("ignore", category=UserWarning)

class Embedder(Protocol):
    def embed_text(self, text: str) -> List[float]:
        """Embeds text and returns a float vector."""
        ...
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embeds a batch of texts."""
        ...

class KrutrimLocalEmbedder:
    def __init__(self):
        # The Vyakyarth model is loaded directly from the local huggingface cache
        self.model = SentenceTransformer("krutrim-ai-labs/vyakyarth")

    def embed_text(self, text: str) -> List[float]:
        # Returns a 768-dim float vector
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]

def get_embedder() -> Embedder:
    """Returns the default embedding provider adapter."""
    return KrutrimLocalEmbedder()
