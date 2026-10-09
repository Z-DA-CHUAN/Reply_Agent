import json
from typing import Any


from app.common.mysql import close_mysql_conn,get_mysql_conn



class ReplyRepository:
    """
    答辩历史数据访问类。

    直接使用 SQL 操作：

    reply_session：
        保存一次答辩会话和最终总结。

    reply_record：
        保存这次答辩中的每一轮问题、回答和评价。
    """

    def create_session(
        self,
        session_id: str,
        user_id: str,
        project_name: str,
        total_questions: int = 3,
        max_followups: int = 3,
    ) -> None:
        """
        创建一条答辩会话记录。
        """

        conn = None
        cursor = None

        try:
            conn = get_mysql_conn()
            cursor = conn.cursor()

            sql = """INSERT INTO reply_session (session_id,user_id,project_name,status,total_questions,max_followups)VALUES (%s,%s,%s,'running',%s,%s)"""

            cursor.execute(
                sql,
                (
                session_id,
                user_id,
                project_name,
                total_questions,
                max_followups,
                ),
            )

            conn.commit()

        except Exception:
            if conn is not None:
                conn.rollback()
            raise

        finally:
            close_mysql_conn(cursor, conn)

    def save_record(
        self,
        session_id: str,
        sequence_no: int,
        question_id: str | int,
        question_type: str,
        question_content: str,
        answer_content: str | None,
        score: int | None,
        evaluation_content: str | None,
        need_followup: bool,
        followup_direction: str | None,
    ) -> None:
        """
        保存一轮答辩记录。

        一轮记录包含：

        - AI 问题；
        - 用户回答；
        - 回答分数；
        - AI 评价；
        - 是否需要追问。
        """

        conn = None
        cursor = None

        try:
            conn = get_mysql_conn()
            cursor = conn.cursor()

            sql = """INSERT INTO reply_record (session_id,sequence_no,question_id,question_type,question_content,answer_content,score,evaluation_content,need_followup,followup_direction)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""

            cursor.execute(
                sql,
                (
                    session_id,
                    sequence_no,
                    str(question_id),
                    question_type,
                    question_content,
                    answer_content,
                    score,
                    evaluation_content,
                    int(need_followup),
                    followup_direction,
                ),
            )

            conn.commit()

        except Exception:
            if conn is not None:
                conn.rollback()
            raise

        finally:
            close_mysql_conn(cursor, conn)

    def complete_session(
        self,
        session_id: str,
        total_score: int,
        overall_evaluation: str,
        advantages: list[str],
        problems: list[str],
        suggestions: list[str],
    ) -> None:
        """
        完成答辩并保存最终总结。
        """

        conn = None
        cursor = None

        try:
            conn = get_mysql_conn()
            cursor = conn.cursor()

            sql = """UPDATE reply_session SET
                    status = 'completed',
                    total_score = %s,
                    overall_evaluation = %s,
                    advantages = %s,
                    problems = %s,
                    suggestions = %s,
                    finished_at = NOW()
                WHERE session_id = %s
            """

            cursor.execute(
                sql,
                (
                    total_score,
                    overall_evaluation,
                    json.dumps(
                        advantages,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        problems,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        suggestions,
                        ensure_ascii=False,
                    ),
                    session_id,
                ),
            )

            conn.commit()

        except Exception:
            if conn is not None:
                conn.rollback()
            raise

        finally:
            close_mysql_conn(cursor, conn)

    def delete_session(
        self,
        session_id: str,
        user_id: str,
    ) -> bool:
        """
        删除当前用户的一场答辩历史。

        先删除答辩明细，再删除答辩会话，
        避免 reply_record 外键约束导致主记录无法删除。
        两步操作在同一个事务中完成。
        """

        conn = None
        cursor = None

        try:
            conn = get_mysql_conn()
            cursor = conn.cursor()

            # 先确认这场答辩属于当前用户，防止误删其他用户的数据。
            select_sql = """
                SELECT session_id
                FROM reply_session
                WHERE session_id = %s
                  AND user_id = %s
                FOR UPDATE
            """
            cursor.execute(
                select_sql,
                (session_id, user_id),
            )

            if cursor.fetchone() is None:
                conn.rollback()
                return False

            # 先删除这场答辩的所有问题、回答和评价记录。
            delete_records_sql = """
                DELETE FROM reply_record
                WHERE session_id = %s
            """
            cursor.execute(
                delete_records_sql,
                (session_id,),
            )

            # 再删除当前用户的答辩会话主记录。
            delete_session_sql = """
                DELETE FROM reply_session
                WHERE session_id = %s
                  AND user_id = %s
            """
            cursor.execute(
                delete_session_sql,
                (session_id, user_id),
            )

            if cursor.rowcount != 1:
                conn.rollback()
                return False

            conn.commit()
            return True

        except Exception:
            if conn is not None:
                conn.rollback()
            raise

        finally:
            close_mysql_conn(cursor, conn)

    def get_user_sessions(
        self,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """
        查询某个用户的历史答辩列表。
        """

        conn = None
        cursor = None

        try:
            conn = get_mysql_conn()
            cursor = conn.cursor()

            sql = """
                SELECT
                    session_id,
                    user_id,
                    project_name,
                    status,
                    total_questions,
                    max_followups,
                    total_score,
                    created_at,
                    finished_at
                FROM reply_session
                WHERE user_id = %s
                ORDER BY created_at DESC
            """

            cursor.execute(
                sql,
                (user_id,),
            )

            return cursor.fetchall()

        finally:
            close_mysql_conn(cursor, conn)

    def get_session(
        self,
        session_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        """
        查询一场答辩的基本信息和最终总结。

        user_id 用于确认这场答辩属于当前用户。
        """

        conn = None
        cursor = None

        try:
            conn = get_mysql_conn()
            cursor = conn.cursor()

            sql = """
                SELECT
                    session_id,
                    user_id,
                    project_name,
                    status,
                    total_questions,
                    max_followups,
                    total_score,
                    overall_evaluation,
                    advantages,
                    problems,
                    suggestions,
                    created_at,
                    finished_at
                FROM reply_session
                WHERE session_id = %s
                  AND user_id = %s
            """

            cursor.execute(
                sql,
                (
                    session_id,
                    user_id,
                ),
            )

            result: dict[str, Any] | None = (
                cursor.fetchone()
            )

            if result is None:
                return None

            # MySQL JSON 字段可能以字符串形式返回，
            # 这里转换成 Python 列表
            for field in (
                "advantages",
                "problems",
                "suggestions",
            ):
                value = result.get(field)

                if isinstance(value, str):
                    result[field] = json.loads(value)

            return result

        finally:
            close_mysql_conn(cursor, conn)

    def get_session_records(
        self,
        session_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """
        查询某场答辩的完整聊天记录。

        通过关联 reply_session 验证用户归属。
        """

        conn = None
        cursor = None

        try:
            conn = get_mysql_conn()
            cursor = conn.cursor()

            sql = """
                SELECT
                    r.record_id,
                    r.session_id,
                    r.sequence_no,
                    r.question_id,
                    r.question_type,
                    r.question_content,
                    r.answer_content,
                    r.score,
                    r.evaluation_content,
                    r.need_followup,
                    r.followup_direction,
                    r.created_at
                FROM reply_record AS r
                INNER JOIN reply_session AS s
                    ON r.session_id = s.session_id
                WHERE r.session_id = %s
                  AND s.user_id = %s
                ORDER BY r.sequence_no ASC
            """

            cursor.execute(
                sql,
                (
                    session_id,
                    user_id,
                ),
            )

            return cursor.fetchall()

        finally:
            close_mysql_conn(cursor, conn)
