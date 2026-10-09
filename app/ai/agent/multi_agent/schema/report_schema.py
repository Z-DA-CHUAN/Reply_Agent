from pydantic import BaseModel, Field


class ReportSchema(BaseModel):
    """最终答辩报告的结构化输出。"""

    # 对本次答辩表现的整体评价
    overall_evaluation: str = Field(
        description="对学生本次项目答辩表现的总体评价",
    )

    # 学生答辩中表现较好的方面
    advantages: list[str] = Field(
        description="学生回答中的主要优点",
    )

    # 学生答辩中存在的问题
    problems: list[str] = Field(
        description="学生回答中存在的主要问题",
    )

    # 后续改进建议
    suggestions: list[str] = Field(
        description="针对学生不足给出的改进建议",
    )
