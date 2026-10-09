from pathlib import Path


def load_text_file(file_path: str) -> str:
    """
    读取 TXT 或 Markdown 项目文档。
    参数：
        file_path：项目文档路径。
    返回：
        文档中的文本内容。
    """

    path = Path(file_path)

    # 检查文件是否存在
    if not path.is_file():
        raise FileNotFoundError(
            f"项目文档不存在：{file_path}"
        )

    # 第一版只支持纯文本和 Markdown
    allowed_suffixes: set[str] = {
        ".txt",
        ".md",
        ".markdown",
    }

    if path.suffix.lower() not in allowed_suffixes:
        raise ValueError(
            "当前只支持 TXT 和 Markdown 文件"
        )
    try:
        # 优先使用 UTF-8 编码
        content: str = path.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        # 兼容部分 Windows 文本文件
        content = path.read_text(
            encoding="gbk"
        )
    if not content.strip():
        raise ValueError(
            "项目文档内容为空"
        )
    return content.strip()
