'''
接收 TXT/Markdown 文件
→ 检查文件类型和大小
→ 保存到 data/uploads
→ 文本切分和向量化
→ 写入 project_id 对应的 Chroma 集合
→ 返回文本块数量
'''
from pathlib import Path
from typing import Any
from uuid import uuid4


from fastapi import APIRouter,File,Form,HTTPException,UploadFile
from starlette.concurrency import run_in_threadpool
from app.ai.rag.project_rag import ProjectRAG


# 文档上传路由
document_router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
)


# 项目上传文件保存目录
upload_dir: Path = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "uploads"
)

# 确保上传目录存在
upload_dir.mkdir(
    parents=True,
    exist_ok=True,
)


# 支持的文件类型
allowed_suffixes: set[str] = {
    ".txt",
    ".md",
    ".markdown",
}


# 最大允许上传 5 MB
max_file_size: int = 5 * 1024 * 1024


# 创建 RAG 服务
project_rag = ProjectRAG()


@document_router.post("/upload")
async def upload_document(
    # 项目编号，用于隔离 Chroma 集合
    project_id: int = Form(...),
    # 用户上传的项目文件
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    上传项目资料并写入 Chroma。

    第一版只支持：

    - TXT
    - Markdown
    """

    # 检查项目编号
    if project_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="project_id 必须大于 0",
        )

    # 获取用户上传的原始文件名
    original_filename = Path(file.filename or "").name

    if not original_filename:
        raise HTTPException(
            status_code=400,
            detail="上传文件名不能为空",
        )

    # 获取文件扩展名
    file_suffix = Path(original_filename).suffix.lower()

    # 检查文件类型
    if file_suffix not in allowed_suffixes:
        raise HTTPException(
            status_code=400,
            detail=(
                "当前只支持 TXT、MD 和 Markdown 文件"
            ),
        )

    try:
        # 读取上传文件
        file_content = await file.read()

        # 检查空文件
        if not file_content:
            raise HTTPException(
                status_code=400,
                detail="上传文件不能为空",
            )

        # 检查文件大小
        if len(file_content) > max_file_size:
            raise HTTPException(
                status_code=400,
                detail="上传文件不能超过 5 MB",
            )

        # 使用 UUID 生成服务器内部文件名，
        # 避免重名和用户文件名造成目录穿越
        saved_filename = f"{project_id}_{uuid4().hex}{file_suffix}"

        saved_path: Path = (
            upload_dir / saved_filename
        )

        # 保存原始文件
        saved_path.write_bytes(file_content)

        try:
            # 文件读取、Embedding 和 Chroma 写入都是同步操作，
            # 放到线程池执行，避免阻塞 FastAPI 事件循环
            document_ids: list[str] = (
                await run_in_threadpool(
                    project_rag.add_file,
                    project_id,
                    str(saved_path),
                )
            )

        except Exception:
            # RAG 处理失败时删除刚保存的无效文件
            if saved_path.exists():
                saved_path.unlink()

            raise

        return {
            "message": "项目文档上传成功",
            "project_id": project_id,
            "original_filename": original_filename,
            "saved_filename": saved_filename,
            "chunk_count": len(document_ids),
        }

    except HTTPException:
        raise

    except UnicodeDecodeError as error:
        raise HTTPException(
            status_code=400,
            detail="文件编码无法识别",
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="项目文档处理失败",
        ) from error

    finally:
        await file.close()
