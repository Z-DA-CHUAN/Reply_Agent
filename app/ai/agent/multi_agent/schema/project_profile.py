from pydantic import BaseModel, Field


class ProjectProfileSchema(BaseModel):
    """
    项目画像的结构化数据模型。
    """
    # 项目名称
    project_name: str = Field(
        default="",
        description="项目名称",
    )

    # 项目整体介绍
    project_introduce: str = Field(
        default="",
        description="项目解决的问题、主要功能和应用场景",
    )

    # 项目使用的技术
    project_technology: list[str] = Field(
        default_factory=list,
        description="项目使用的编程语言、框架、数据库和中间件",
    )

    # 项目核心模块
    project_module: list[str] = Field(
        default_factory=list,
        description="项目中的主要业务模块",
    )

    # 项目技术难点
    technology_challenges: list[str] = Field(
        default_factory=list,
        description="项目中适合用于答辩提问的技术难点",
    )
