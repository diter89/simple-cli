#!/usr/bin/env python3

import hashlib
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from typing import Callable

try:
    from chromadb import PersistentClient as _PersistentClient
except ImportError:
    _PersistentClient = None

from chromadb.api.models.Collection import Collection

if _PersistentClient is None:
    import chromadb
    from chromadb.config import Settings


@dataclass
class MemoryItem:
    content: str
    metadata: Dict[str, Any]
    document_id: Optional[str] = None


class SimpleHashEmbedding:
    def __init__(self, dimension: int = 256) -> None:
        self.dimension = dimension

    def embed(self, text: str) -> List[float]:
        tokens = text.split()
        vector = [0.0] * self.dimension

        for token in tokens:
            token_hash = hashlib.sha256(token.encode("utf-8")).digest()
            segment_size = len(token_hash) // 4

            for idx in range(4):
                start = idx * segment_size
                end = start + segment_size
                chunk = token_hash[start:end]

                chunk_value = int.from_bytes(chunk, "big")
                position = chunk_value % self.dimension
                vector[position] += 1.0

        length = sum(value * value for value in vector) ** 0.5
        if length > 0:
            vector = [value / length for value in vector]

        return vector


class ChromaMemoryStore:
    COLLECTION_NAME = "hybrid_shell_memory"

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        embedding_dimension: int = 256,
        max_items: Optional[int] = None,
    ) -> None:
        if persist_directory is None:
            home = os.path.expanduser("~")
            persist_directory = os.path.join(home, ".cache", "wrapcli", "chroma")

        os.makedirs(persist_directory, exist_ok=True)

        self._lock = threading.Lock()
        self._embedding = SimpleHashEmbedding(embedding_dimension)
        self._max_items = max_items
        self._persist_directory = persist_directory

        if _PersistentClient is not None:
            self._client = _PersistentClient(path=persist_directory)
        else:
            self._client = chromadb.Client(
                Settings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=persist_directory,
                )
            )

        self._collection: Collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def _generate_document_id(self, metadata: Dict[str, Any]) -> str:
        base = f"{metadata.get('type', 'unknown')}:{metadata.get('timestamp', time.time())}:{metadata.get('cwd', '')}"
        digest = hashlib.md5(base.encode("utf-8")).hexdigest()
        return f"mem_{digest}_{int(time.time() * 1000)}"

    def add_items(self, items: Iterable[MemoryItem]) -> None:
        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        embeddings: List[List[float]] = []

        for item in items:
            document_id = item.document_id or self._generate_document_id(item.metadata)
            embedding = self._embedding.embed(item.content)

            ids.append(document_id)
            documents.append(item.content)
            metadatas.append(item.metadata)
            embeddings.append(embedding)

        if not documents:
            return

        with self._lock:
            self._collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )
            if self._max_items is not None:
                self._trim_collection()
            if hasattr(self._client, "persist"):
                self._client.persist()
            #if self._max_items is not None:
            #    self._trim_collection()

    def add_interaction(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[str] = None,
    ) -> None:
        metadata = metadata or {}
        if "timestamp" not in metadata:
            metadata["timestamp"] = time.time()

        item = MemoryItem(content=content, metadata=metadata, document_id=document_id)
        self.add_items([item])

    def query_recent(
        self, limit: int = 5, metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[MemoryItem]:
        metadata_filter = metadata_filter or {}

        with self._lock:
            result = self._collection.get(
                where=metadata_filter,
                limit=limit,
                include=["documents", "metadatas", "ids"],
            )

        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])
        ids = result.get("ids", [])

        items = [
            MemoryItem(content=doc, metadata=meta, document_id=item_id)
            for doc, meta, item_id in zip(documents, metadatas, ids)
        ]

        items.sort(key=lambda item: item.metadata.get("timestamp", 0), reverse=True)
        return items[:limit]

    def similarity_search(
        self,
        query: str,
        top_k: int = 5,
        type_filter: Optional[str] = None,
    ) -> List[MemoryItem]:
        query_embedding = self._embedding.embed(query)

        where_clause: Optional[Dict[str, Any]] = None
        if type_filter:
            where_clause = {"type": type_filter}

        with self._lock:
            result = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause,
                include=["documents", "metadatas", "ids"],
            )

        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        ids = result.get("ids", [[]])[0]

        return [
            MemoryItem(content=doc, metadata=meta, document_id=item_id)
            for doc, meta, item_id in zip(docs, metas, ids)
        ]

    def clear(self) -> None:
        with self._lock:
            self._client.delete_collection(self.COLLECTION_NAME)
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            if hasattr(self._client, "persist"):
                self._client.persist()

    def count(self) -> int:
        with self._lock:
            result = self._collection.count()
        return int(result)

    @property
    def storage_path(self) -> str:
        return self._persist_directory

    def _trim_collection(self) -> None:
        if self._max_items is None:
            return

        current_count = self._collection.count()
        if current_count <= self._max_items:
            return

        data = self._collection.get(include=["metadatas", "ids"])
        metadatas = data.get("metadatas", [])
        ids = data.get("ids", [])

        items = sorted(
            zip(ids, metadatas),
            key=lambda pair: pair[1].get("timestamp", 0) if pair[1] else 0,
        )

        keep = int(self._max_items)
        if keep < 0:
            keep = 0
        ids_to_delete = [item_id for item_id, _ in items[:-keep]]

        if ids_to_delete:
            self._collection.delete(ids=ids_to_delete)
