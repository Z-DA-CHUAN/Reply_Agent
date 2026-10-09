-- MySQL schema for Reply Agent history.
-- Run this script in the database configured by MYSQL_DATABASE.

CREATE TABLE IF NOT EXISTS reply_session (
    session_id VARCHAR(128) NOT NULL PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    project_name VARCHAR(255) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    total_questions INT NOT NULL DEFAULT 3,
    max_followups INT NOT NULL DEFAULT 3,
    total_score INT NULL,
    overall_evaluation TEXT NULL,
    advantages JSON NULL,
    problems JSON NULL,
    suggestions JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL,
    INDEX idx_reply_session_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS reply_record (
    record_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(128) NOT NULL,
    sequence_no INT NOT NULL,
    question_id VARCHAR(64) NOT NULL,
    question_type VARCHAR(32) NOT NULL,
    question_content TEXT NOT NULL,
    answer_content TEXT NULL,
    score INT NULL,
    evaluation_content TEXT NULL,
    need_followup TINYINT(1) NOT NULL DEFAULT 0,
    followup_direction TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_reply_record_question (session_id, question_id),
    INDEX idx_reply_record_session_sequence (session_id, sequence_no),
    CONSTRAINT fk_reply_record_session
        FOREIGN KEY (session_id) REFERENCES reply_session(session_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;