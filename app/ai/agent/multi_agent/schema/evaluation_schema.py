from pydantic import BaseModel, Field


class EvaluationSchema(BaseModel):
    """回答评价智能体的结构化输出。"""

    score: int = Field(
        default=0,
        ge=0,
        le=100,
        description="当前回答的评分，范围为0到100",
    )
    evaluation_content: str = Field(
        default="",
        description="说明回答是否正确，以及存在的问题",
    )
    need_followup: bool = Field(
        default=False,
        description="当前回答是否需要继续追问",
    )
    followup_direction: str = Field(
        default="",
        description="需要继续追问的技术方向",
    )