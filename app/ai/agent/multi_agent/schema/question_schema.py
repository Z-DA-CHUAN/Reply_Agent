from pydantic import BaseModel, Field


class QuestionSchema(BaseModel):
    """问题生成智能体的结构化输出。"""

    question_content: str = Field(
        default="",
        min_length=1,
        description="根据项目画像生成的一道答辩问题",
    )