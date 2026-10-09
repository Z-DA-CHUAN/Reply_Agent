import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import chromadb
from dotenv import load_dotenv

from app.ai.models.LoadEmbeddingModel import load_embedding_model

load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[3]
_configured_chroma_path = Path(os.getenv("CHROMA_PATH", "data/chroma"))
CHROMA_PATH = (
    _configured_chroma_path
    if _configured_chroma_path.is_absolute()
    else PROJECT_ROOT / _configured_chroma_path
)


class ChromaStore:
    """Chroma 向量库存储类。"""

    def __init__(self) -> None:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self.embedding_model = load_embedding_model()

    def get_collection(self, project_id: int) -> Any:
        """获取指定项目的向量集合。"""

        return self.client.get_or_create_collection(
            name=f"project_{project_id}",
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        project_id: int,
        documents: list[str],
    ) -> list[str]:
        """将文本块保存到指定项目的 Chroma 集合。"""

        clean_documents = [document.strip() for document in documents if document.strip()]
        if not clean_documents:
            raise ValueError("没有可保存的项目文本")

        collection = self.get_collection(project_id)
        embeddings = self.embedding_model.embed_documents(clean_documents)
        document_ids = [
            f"project_{project_id}_chunk_{uuid4().hex}"
            for _ in clean_documents
        ]
        metadatas = [
            {"project_id": project_id, "chunk_index": index}
            for index in range(len(clean_documents))
        ]

        collection.add(
            ids=document_ids,
            documents=clean_documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return document_ids