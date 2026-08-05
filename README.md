# 📋 项目管理系统

基于 Flask + SQLite 的本地化项目管理系统，支持多用户角色、文件管理、需求管理、图纸管理、BOM管理和审批流程。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动应用

```bash
python3 app.py
```

应用将在 `http://localhost:5000` 启动。

### 3. 首次使用

1. 打开浏览器访问 `http://localhost:5000`
2. 系统会引导你设置**数据根目录**（存储数据库和附件的位置）
3. 设置完成后，使用默认管理员账号登录：
   - 用户名：`admin`
   - 密码：`admin123`
4. 登录后可在"用户管理"中创建其他用户

## 功能模块

| 模块 | 说明 |
|------|------|
| 📊 仪表盘 | 项目概览、待办任务、快捷入口 |
| 📁 项目登记 | 创建项目、自动生成项目号、项目信息管理 |
| 📎 立项文件库 | 文件上传、版本管理、分类筛选 |
| 📝 需求管理 | 需求创建、变更审批、版本追溯 |
| 📐 图纸管理 | 图纸上传、ECO变更、版本控制 |
| 🔧 BOM管理 | 物料清单编辑、Excel导入导出、一致性校验 |
| ✅ 审批中心 | 多级审批流程、待办管理 |
| 👥 用户管理 | 多角色用户、权限控制 |
| ⚙️ 系统设置 | 配置管理、备份恢复、审计日志 |

## 用户角色

| 角色 | 说明 |
|------|------|
| 系统管理员 | 全部权限 |
| 项目管理员 | 项目和用户管理 |
| 项目经理 | 项目管理、审批 |
| 设计工程师 | 图纸、BOM管理 |
| 需求工程师 | 需求管理 |
| 文控/质量 | 文件管理、质量审批 |

## 项目结构

```
project-management/
├── app.py              # Flask 主应用（路由 + API）
├── config.py           # 配置管理（config.ini 读写）
├── database.py         # 数据库初始化与 Schema
├── requirements.txt    # Python 依赖
├── templates/          # HTML 模板
│   ├── login.html      # 登录页
│   ├── setup.html      # 初始化设置页
│   └── dashboard.html  # 主界面（SPA 风格）
├── static/
│   ├── css/style.css   # 全局样式
│   └── js/app.js       # 前端核心 JS
├── utils/
│   ├── number_generator.py  # 项目号/需求ID生成器
│   └── file_utils.py        # 文件操作工具
└── models/             # 业务逻辑（扩展用）
```

## 技术栈

- **后端**: Python 3 + Flask
- **数据库**: SQLite（WAL 模式）
- **前端**: 原生 HTML/CSS/JS（SPA 风格）
- **UI风格**: 极简现代、翠绿强调色、扁平化设计

## 配置说明

`config.ini` 自动生成于项目目录，包含：

- `data_root`: 数据存储根目录
- `project_number_rule`: 项目号生成规则（支持 `{type_prefix}`, `{yy}`, `{mm}`, `{flow:03d}` 变量）
- `project_types`: 项目类型及其前缀映射
- `approval`: 各模块审批角色配置

## 备份

在系统设置中可一键备份，生成包含数据库和附件的 ZIP 文件。恢复时选择备份 ZIP 文件即可。
