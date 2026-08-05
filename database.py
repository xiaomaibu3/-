"""数据库初始化与通用操作 - SQLite 封装（连接池优化）"""
import sqlite3
import os
import threading
from contextlib import contextmanager

# 连接池：每个线程复用一个连接
_local = threading.local()


def close_connection(db_path=None):
    """Close the cached connection for the current thread."""
    conn = getattr(_local, 'conn', None)
    if conn is None:
        return
    if db_path is not None and getattr(_local, 'db_path', None) != db_path:
        return
    conn.close()
    _local.conn = None
    _local.db_path = None


def get_connection(db_path):
    """获取当前线程的数据库连接（复用）"""
    conn = getattr(_local, 'conn', None)
    # 如果连接不存在或路径变了，重新创建
    if conn is None or getattr(_local, 'db_path', None) != db_path:
        close_connection()
        os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-8000")  # 8MB 缓存
        _local.conn = conn
        _local.db_path = db_path
    return conn


@contextmanager
def get_db(db_path):
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


SCHEMA = """
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '设计工程师',
    real_name TEXT NOT NULL DEFAULT '',
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 项目表
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_number TEXT UNIQUE NOT NULL,
    project_name TEXT NOT NULL,
    customer TEXT DEFAULT '',
    type TEXT DEFAULT '',
    manager_id INTEGER REFERENCES users(id),
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    budget REAL DEFAULT 0,
    status TEXT DEFAULT '进行中',
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_projects_number ON projects(project_number);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

-- 项目文件表
CREATE TABLE IF NOT EXISTS project_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    category TEXT DEFAULT '立项文件',
    uploader_id INTEGER REFERENCES users(id),
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_current INTEGER DEFAULT 1,
    description TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_pfiles_project ON project_files(project_id);

-- 需求表
CREATE TABLE IF NOT EXISTS requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    req_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    priority TEXT DEFAULT '中',
    status TEXT DEFAULT '草稿',
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1,
    parent_req_id INTEGER REFERENCES requirements(id),
    requester_name TEXT DEFAULT '',
    requirement_time TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_req_project ON requirements(project_id);
CREATE INDEX IF NOT EXISTS idx_req_status ON requirements(status);

-- 需求变更表
CREATE TABLE IF NOT EXISTS req_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    req_id INTEGER NOT NULL REFERENCES requirements(id),
    change_reason TEXT DEFAULT '',
    change_content TEXT DEFAULT '',
    impact TEXT DEFAULT '',
    status TEXT DEFAULT '待审批',
    applicant_id INTEGER REFERENCES users(id),
    approval_stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 图纸表
CREATE TABLE IF NOT EXISTS drawings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    drawing_number TEXT NOT NULL,
    drawing_name TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    file_path TEXT DEFAULT '',
    status TEXT DEFAULT '草稿',
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_draw_project ON drawings(project_id);

-- 图纸ECO变更表
CREATE TABLE IF NOT EXISTS drawing_ecos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drawing_id INTEGER NOT NULL REFERENCES drawings(id),
    change_description TEXT DEFAULT '',
    reason TEXT DEFAULT '',
    interchangeability TEXT DEFAULT '',
    status TEXT DEFAULT '待审批',
    applicant_id INTEGER REFERENCES users(id),
    approval_stages TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- BOM表
CREATE TABLE IF NOT EXISTS boms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    version TEXT DEFAULT 'V1.0',
    status TEXT DEFAULT '草稿',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_bom_project ON boms(project_id);

-- BOM物料表
CREATE TABLE IF NOT EXISTS bom_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bom_id INTEGER NOT NULL REFERENCES boms(id),
    parent_item_id INTEGER REFERENCES bom_items(id),
    material_code TEXT DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    spec TEXT DEFAULT '',
    unit TEXT DEFAULT '个',
    quantity REAL DEFAULT 1,
    position TEXT DEFAULT '',
    material TEXT DEFAULT '',
    drawing_id INTEGER REFERENCES drawings(id),
    req_id INTEGER REFERENCES requirements(id),
    check_status TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_bomitem_bom ON bom_items(bom_id);
CREATE INDEX IF NOT EXISTS idx_bomitem_parent ON bom_items(parent_item_id);

-- 审批记录表
CREATE TABLE IF NOT EXISTS approval_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    approver_id INTEGER REFERENCES users(id),
    decision TEXT NOT NULL,
    comment TEXT DEFAULT '',
    decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_approval_target ON approval_records(target_type, target_id);

-- 审计日志表
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    target_type TEXT DEFAULT '',
    target_id INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_logs(timestamp);

-- 审批流配置表
CREATE TABLE IF NOT EXISTS approval_flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT NOT NULL,
    name TEXT NOT NULL,
    stages TEXT NOT NULL DEFAULT '[]',
    is_active INTEGER DEFAULT 1
);
"""


def _migrate_db(conn):
    """数据库迁移：为已有表添加新字段"""
    # 检查 requirements 表是否有 requester_name 字段
    cols = [r[1] for r in conn.execute("PRAGMA table_info(requirements)").fetchall()]
    if 'requester_name' not in cols:
        conn.execute("ALTER TABLE requirements ADD COLUMN requester_name TEXT DEFAULT ''")
    if 'requirement_time' not in cols:
        conn.execute("ALTER TABLE requirements ADD COLUMN requirement_time TEXT DEFAULT ''")


def init_db(db_path):
    """初始化数据库，创建所有表"""
    with get_db(db_path) as conn:
        conn.executescript(SCHEMA)
        _migrate_db(conn)
        # 插入默认管理员账户（如不存在）
        row = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
        if not row:
            from werkzeug.security import generate_password_hash
            conn.execute(
                "INSERT INTO users (username, password_hash, role, real_name) VALUES (?,?,?,?)",
                ('admin', generate_password_hash('admin123'), '系统管理员', '管理员')
            )
