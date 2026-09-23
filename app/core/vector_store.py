import logging
import uuid
import httpx
from typing import List
from qdrant_client import QdrantClient
from qdrant_client.http import models

logger = logging.getLogger(__name__)

class VectorKnowledgeBase:
    def __init__(
        self, 
        qdrant_host: str = "qdrant", 
        qdrant_port: int = 6333,
        ollama_url: str = "http://ollama-server:11434",
        embed_model: str = "nomic-embed-text",
        collection_name: str = "global_knowledge"
    ):
        self.qdrant_host = qdrant_host
        self.qdrant_port = qdrant_port
        self.ollama_url = ollama_url.rstrip('/')
        self.embed_model = embed_model
        self.collection_name = collection_name
        self.client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            collections = self.client.get_collections().collections
            if not any(c.name == self.collection_name for c in collections):
                logger.info(f"Creating Qdrant collection: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=768, # nomic-embed-text size
                        distance=models.Distance.COSINE
                    )
                )
        except Exception as e:
            logger.error(f"Failed to ensure Qdrant collection: {e}")

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.ollama_url}/api/embed",
                json={"model": self.embed_model, "input": texts}
            )
            resp.raise_for_status()
            return resp.json().get("embeddings", [])

    def _chunk_text(self, text: str, chunk_size: int = 1500) -> List[str]:
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        for p in paragraphs:
            if len(current_chunk) + len(p) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = p
            else:
                current_chunk += "\n\n" + p
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks

    async def index_document(self, text: str, source_name: str, session_id: str = None):
        logger.info(f"Indexing document '{source_name}' into Qdrant (session: {session_id})...")
        chunks = self._chunk_text(text)
        if not chunks:
            return

        try:
            embeddings = await self._get_embeddings(chunks)
            points = []
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                points.append(
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=emb,
                        payload={"text": chunk, "source": source_name, "chunk_idx": i, "session_id": session_id}
                    )
                )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            logger.info(f"Successfully indexed {len(points)} chunks into Qdrant.")
        except Exception as e:
            logger.error(f"Failed to index document to Qdrant: {e}")

    async def search(self, query: str, limit: int = 5, session_id: str = None) -> str:
        logger.info(f"Searching Qdrant for: '{query}' (session: {session_id})")
        try:
            query_embedding = (await self._get_embeddings([query]))[0]
            
            filter_params = None
            if session_id:
                filter_params = models.Filter(
                    must=[models.FieldCondition(key="session_id", match=models.MatchValue(value=session_id))]
                )

            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=filter_params,
                limit=limit
            )
            
            results = []
            for hit in search_result:
                # Фильтруем результаты с низкой релевантностью
                if hit.score > 0.5:
                    source = hit.payload.get("source", "Unknown")
                    text = hit.payload.get("text", "")
                    results.append(f"--- Из исторического документа: {source} (Score: {hit.score:.2f}) ---\n{text}")
                
            return "\n\n".join(results)
        except Exception as e:
            logger.error(f"Failed to search Qdrant: {e}")
            return ""
