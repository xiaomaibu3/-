"""项目号自动生成器"""
import re
from datetime import datetime


def generate_project_number(config, project_type, db_conn):
    """
    根据配置规则生成项目号
    规则示例: {type_prefix}-{yy}{mm}-{flow:03d}
    """
    rule = config.get('general', 'project_number_rule', '{type_prefix}-{yy}{mm}-{flow:03d}')
    types = config.get_project_types()
    prefix = types.get(project_type, 'XX')

    now = datetime.now()
    yy = now.strftime('%y')
    mm = now.strftime('%m')

    # 提取 flow 格式占位符（保留原始字符串，如 '03'）
    flow_match = re.search(r'(\{flow:(\d+)d\})', rule)
    if flow_match:
        flow_placeholder = flow_match.group(1)  # 例如 '{flow:03d}'
        width = int(flow_match.group(2))         # 例如 3
    else:
        flow_placeholder = '{flow:03d}'
        width = 3

    # 替换已知变量，保留 flow 占位符
    pattern = rule.replace('{type_prefix}', prefix).replace('{yy}', yy).replace('{mm}', mm)

    # 查询本月已有的最大流水号
    like_pattern = pattern.replace(flow_placeholder, '%')
    row = db_conn.execute(
        "SELECT project_number FROM projects WHERE project_number LIKE ? ORDER BY project_number DESC LIMIT 1",
        (like_pattern,)
    ).fetchone()

    if row:
        num_str = row['project_number'].split('-')[-1]
        try:
            flow = int(num_str) + 1
        except ValueError:
            flow = 1
    else:
        flow = 1

    # 生成项目号
    project_number = pattern.replace(flow_placeholder, str(flow).zfill(width))

    return project_number


def generate_req_id(db_conn, project_id):
    """自动生成需求ID: REQ-{project_id}-{序号}"""
    row = db_conn.execute(
        "SELECT req_id FROM requirements WHERE project_id=? ORDER BY id DESC LIMIT 1",
        (project_id,)
    ).fetchone()
    if row:
        try:
            seq = int(row['req_id'].split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"REQ-{project_id}-{str(seq).zfill(3)}"


def generate_material_code(db_conn):
    """自动生成物料编码: MAT-{序号}"""
    row = db_conn.execute(
        "SELECT material_code FROM bom_items ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row and row['material_code']:
        try:
            seq = int(row['material_code'].split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"MAT-{str(seq).zfill(5)}"
