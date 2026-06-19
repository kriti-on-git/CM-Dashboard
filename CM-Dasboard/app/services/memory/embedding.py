import torch
import logging
from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)

class MemoryEmbeddingService:
    """
    RAG Embedding wrapper.
    Singleton pattern for sentence-transformers to avoid memory bloat.
    """
    _instance = None
    
    def __new__(cls, model_name: str = 'all-MiniLM-L6-v2'):
        if cls._instance is None:
            logger.info(f"Loading RAG memory embedding model: {model_name}")
            cls._instance = super(MemoryEmbeddingService, cls).__new__(cls)
            cls._instance.model = SentenceTransformer(model_name)
        return cls._instance
        
    def embed(self, text: str) -> np.ndarray:
        """
        Embeds a single string into a 1D vector.
        """
        vector = self.model.encode([text])[0]
        return np.array(vector, dtype=np.float32)
