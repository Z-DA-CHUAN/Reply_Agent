from typing import Any


from app.ai.rag.chroma_store import ChromaStore


class ProjectRetriever:
    """
    项目资料检索器。

    根据问题，从指定项目的 Chroma 集合中
    检索最相关的文本块，并返回文本和余弦距离。
    """

    def __init__(
        self,
        chroma_store: ChromaStore | None = None,
    ) -> None:
        """
        初始化检索器。

        如果外部传入 ChromaStore，就复用传入的对象；
        否则创建一个新的 ChromaStore。
        """
        self.chroma_store = (chroma_store or ChromaStore())

    def search(
        self,
        project_id: int,
        question: str,
        top_k: int = 20,
    ) -> list[dict[str, str | float]]:
        """
        检索项目相关资料。

        参数：
            project_id：项目编号。
            question：用于检索的自然语言问题。
            top_k：最多返回多少个文本块。

        返回：
            每个结果包含：
            - content：文本内容
            - distance：余弦距离
        """

        # 获取当前项目对应的 Chroma 集合
        collection = self.chroma_store.get_collection(project_id)
        # 获取当前项目已有的文本块数量
        document_count: int = collection.count()

        # 当前项目没有文本时，直接返回空列表
        if document_count == 0:
            return []

        # 将检索问题转换成向量
        question_embedding = self.chroma_store.embedding_model.embed_query(question)

        # 实际返回数量不能超过集合中的文本块数量
        result_count = min(top_k,document_count)
        # Chroma 按余弦距离进行排序。
        # 距离越小，表示文本越相似。
        result = collection.query(
            query_embeddings=[
                question_embedding
            ],
            n_results=result_count,
            include=[
                "documents",
                "distances",
            ],
        )

        # documents 和 distances 都是二维列表。
        # 第 0 项代表当前这一次查询。
        documents = (
            result.get("documents") or []
        )

        distances = (
            result.get("distances") or []
        )

        # 没有查询结果时返回空列表
        if not documents or not distances:
            return []

        document_list = documents[0]

        distance_list = distances[0]

        results: list[dict[str, str | float]] = []

        # 文本和距离通过相同下标一一对应
        for document, distance in zip(
            document_list,
            distance_list,
        ):
            if not document:
                continue

            results.append(
                {
                    "content": document,
                    "distance": round(float(distance),4),
                }
            )
        return results
