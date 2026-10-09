import os
from typing import Any

import pymysql
from dotenv import load_dotenv

load_dotenv()


def get_mysql_conn() -> Any:
    """创建 MySQL 数据库连接。"""

    required = {
        "MYSQL_HOST": os.getenv("MYSQL_HOST"),
        "MYSQL_PORT": os.getenv("MYSQL_PORT"),
        "MYSQL_USER": os.getenv("MYSQL_USER"),
        "MYSQL_PASSWORD": os.getenv("MYSQL_PASSWORD"),
        "MYSQL_DATABASE": os.getenv("MYSQL_DATABASE"),
        "MYSQL_CHARSET": os.getenv("MYSQL_CHARSET", "utf8mb4"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing MySQL configuration: " + ", ".join(missing)
        )

    try:
        port = int(required["MYSQL_PORT"])
    except (TypeError, ValueError) as error:
        raise RuntimeError("MYSQL_PORT must be an integer") from error

    return pymysql.connect(
        host=required["MYSQL_HOST"],
        port=port,
        user=required["MYSQL_USER"],
        password=required["MYSQL_PASSWORD"],
        database=required["MYSQL_DATABASE"],
        charset=required["MYSQL_CHARSET"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def close_mysql_conn(cursor: Any, conn: Any) -> None:
    """关闭数据库游标和连接。"""

    if cursor is not None:
        cursor.close()
    if conn is not None:
        conn.close()