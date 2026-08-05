"""文件操作工具函数"""
import os
import shutil
from datetime import datetime


def ensure_dir(path):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)
    return path


def get_project_file_dir(upload_root, project_number, category='立项文件'):
    """获取项目文件存储目录"""
    path = os.path.join(upload_root, category, project_number)
    return ensure_dir(path)


def save_uploaded_file(file_obj, dest_dir, original_name, version=1):
    """
    保存上传文件，添加版本后缀
    返回: (saved_filename, full_path)
    """
    ensure_dir(dest_dir)
    name, ext = os.path.splitext(original_name)
    saved_name = f"{name}_v{version}{ext}"
    full_path = os.path.join(dest_dir, saved_name)

    # 避免覆盖
    counter = 1
    while os.path.exists(full_path):
        saved_name = f"{name}_v{version}_{counter}{ext}"
        full_path = os.path.join(dest_dir, saved_name)
        counter += 1

    file_obj.save(full_path)
    return saved_name, full_path


def save_drawing_file(file_obj, upload_root, drawing_number, version=1):
    """保存图纸文件"""
    dest_dir = ensure_dir(os.path.join(upload_root, '图纸库'))
    name, ext = os.path.splitext(file_obj.filename)
    saved_name = f"{drawing_number}_v{version}{ext}"
    full_path = os.path.join(dest_dir, saved_name)

    counter = 1
    while os.path.exists(full_path):
        saved_name = f"{drawing_number}_v{version}_{counter}{ext}"
        full_path = os.path.join(dest_dir, saved_name)
        counter += 1

    file_obj.save(full_path)
    return saved_name, full_path


def move_to_history(file_path, upload_root):
    """将旧版本文件移动到 _history 子目录"""
    if not os.path.exists(file_path):
        return
    history_dir = ensure_dir(os.path.join(os.path.dirname(file_path), '_history'))
    filename = os.path.basename(file_path)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    name, ext = os.path.splitext(filename)
    dest = os.path.join(history_dir, f"{name}_{timestamp}{ext}")
    shutil.move(file_path, dest)


def get_file_size_str(size_bytes):
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
