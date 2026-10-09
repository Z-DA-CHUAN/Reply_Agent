from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[str]:
    """
    将项目文档切分成多个文本块。
    """

    if not text.strip():
        raise ValueError("待切分文本不能为空")

    # 递归文本切分器会优先按照段落、换行、
    # 句子和字符顺序进行切分
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,

        # 优先保留完整段落和句子
        separators=[
            "\n\n",
            "\n",
            "。",
            "！",
            "？",
            "；",
            "，",
            " ",
            "",
        ],
    )

    return splitter.split_text(text)
