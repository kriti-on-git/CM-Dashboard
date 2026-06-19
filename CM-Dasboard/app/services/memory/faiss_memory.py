import numpy as np
import faiss
from typing import List, Dict, Any
from app.services.memory.embedding import MemoryEmbeddingService

class FaissMemory:
    """
    FAISS-based memory system for high-performance vector similarity search.
    Maps text embeddings to structured metadata.
    """
    
    # Singleton pattern to prevent re-initializing FAISS over and over
    _instance = None
    
    def __new__(cls, embedding_dim: int = 384):
        if cls._instance is None:
            cls._instance = super(FaissMemory, cls).__new__(cls)
            cls._instance.embedding = MemoryEmbeddingService()
            cls._instance.embedding_dim = embedding_dim
            
            # Initialize FAISS IndexFlatL2 (L2 distance)
            cls._instance.index = faiss.IndexFlatL2(embedding_dim)
            
            # Map FAISS internal IDs (0, 1, 2...) to incident metadata
            cls._instance.metadata_store = {}
            cls._instance._current_id = 0
        return cls._instance

    def add_memory(self, text: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Generates embeddings for the text and stores it in the FAISS index.
        """
        # 1. Convert text to embeddings
        vec = self.embedding.embed(text).reshape(1, -1)
        
        # 2. Add to FAISS index
        self.index.add(vec)
        
        # 3. Map embedding to metadata
        self.metadata_store[self._current_id] = {
            "text": text,
            **(metadata or {})
        }
        self._current_id += 1
        
        return True

    def search_similar(self, text: str, top_k: int = 5, distance_threshold: float = 1.5) -> List[Dict[str, Any]]:
        """
        Searches the FAISS index for the most similar past incidents.
        Filters out matches beyond a certain distance threshold.
        """
        if self.index.ntotal == 0:
            return []
            
        k = min(top_k, self.index.ntotal)
        
        query_vec = self.embedding.embed(text).reshape(1, -1)
        
        # Search FAISS index: distances and indices
        distances, indices = self.index.search(query_vec, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1 and dist <= distance_threshold:
                meta = self.metadata_store.get(int(idx), {})
                results.append({
                    "faiss_id": int(idx),
                    "distance": float(dist),
                    "metadata": meta
                })
                
        return results
