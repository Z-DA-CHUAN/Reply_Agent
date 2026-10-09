# AI 项目答辩与能力评测系统

## 项目简介

这是一个面向学生项目答辩的 AI 能力评测系统。学生上传自己的项目资料后，系统会解析项目内容，生成项目画像，并根据项目实际技术内容生成答辩问题。

答辩过程中，学生提交回答，系统会对回答进行评分和评价，并根据回答质量决定是否继续追问。答辩完成后，系统生成总分、优点、问题和改进建议。

## 技术栈

- Python
- FastAPI
- LangChain
- LangGraph
- Chroma
- MySQL
- Pydantic

## 系统模块

### 项目资料处理

系统支持上传 Markdown 和 TXT 项目资料。文件会先被读取，再通过 RecursiveCharacterTextSplitter 切分成多个文本块。

### 向量检索

系统使用 Embedding 模型将文本块转换为向量，并按照 project_id 将文本向量保存到 Chroma 集合中。答辩过程中，系统可以根据问题检索项目资料中最相关的文本块。Chroma 使用余弦距离进行相似度检索。

### 项目画像生成

系统使用 create_agent 调用大语言模型，根据项目资料生成结构化项目画像。项目画像包括项目名称、项目介绍、项目技术、项目模块和技术难点。模型输出使用 ProjectProfileSchema 进行结构化校验。

### LangGraph 答辩流程

系统使用 StateGraph 构建答辩工作流，主要节点包括项目画像、问题生成、答案收集、答案评价、追问和报告生成。manager 节点根据 reply_step、need_followup 和追问次数决定下一步执行哪个节点。

问题生成后，系统暂停并等待用户回答。用户提交回答时，系统使用相同的 thread_id 恢复之前的 State，然后进入答案收集和评价节点。

### 问答记录保存

答辩会话和每轮问答记录保存到 MySQL。reply_session 保存一次答辩的基本信息和最终报告，reply_record 保存每道主问题或追问、用户回答、评分和评价内容。

## 主要技术难点

1. 如何使用 LangGraph 管理多节点之间的状态流转。
2. 如何根据用户回答动态决定是否继续追问。
3. 如何使用 Checkpointer 和 thread_id 恢复用户的答辩会话。
4. 如何将 Chroma 向量检索结果交给大语言模型生成针对性问题。
5. 如何使用 Pydantic Schema 约束大模型的结构化输出。
6. 如何将 LangGraph 运行状态和 MySQL 历史答辩记录配合使用。
