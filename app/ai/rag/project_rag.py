

from app.ai.rag.chroma_store import ChromaStore
from app.ai.rag.project_retriever import ProjectRetriever
from app.ai.rag.text_loader import load_text_file
from app.ai.rag.text_splitter import split_text


class ProjectRAG:
    """
    项目 RAG 服务。

    负责把项目文档转换成向量并保存，
    以及根据问题检索项目资料。
    """

    def __init__(
        self,
        chroma_store: ChromaStore | None = None,
    ) -> None:
        """
        初始化 RAG 服务。

        如果外部传入 ChromaStore，
        就复用同一个向量数据库对象。
        """

        # 向量库存储对象
        self.chroma_store: ChromaStore = (chroma_store or ChromaStore())

        # 项目资料检索器
        self.retriever = ProjectRetriever(self.chroma_store)

    def add_file(
        self,
        project_id: int,
        file_path: str,
    ) -> list[str]:
        """
        读取项目文件，切分后保存到 Chroma。

        参数：
            project_id：项目编号。
            file_path：项目资料文件路径。

        返回：
            保存到 Chroma 的文本块 ID 列表。
        """

        # 读取 TXT 或 Markdown 文件
        document_text: str = load_text_file(
            file_path
        )

        # 调用统一的文本保存方法
        return self.add_text(
            project_id=project_id,
            text=document_text,
        )

    def add_text(
        self,
        project_id: int,
        text: str,
    ) -> list[str]:
        """
        将文本切分后保存到 Chroma。
        这个方法适合处理已经读取好的文本。
        """

        if project_id <= 0:
            raise ValueError(
                "project_id 必须大于 0"
            )

        if not text.strip():
            raise ValueError(
                "项目文本不能为空"
            )

        # 将完整文本切分成多个文本块
        chunks: list[str] = split_text(text)

        # 将文本块向量化并保存
        return self.chroma_store.add_documents(
            project_id=project_id,
            documents=chunks,
        )

    def search(
        self,
        project_id: int,
        question: str,
        top_k: int = 20,
    ) -> list[dict[str, str | float]]:
        """
        检索项目资料。

        返回的每条结果包含：

        content：匹配到的文本内容
        distance：余弦距离
        """

        return self.retriever.search(
            project_id=project_id,
            question=question,
            top_k=top_k,
        )
