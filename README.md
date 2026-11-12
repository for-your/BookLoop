# 书循 BookLoop

**让好书在校园里循环。**

CUIT校园二手教材循环平台，工程实践课程项目。围绕“按课程找书 → 发布闲置 → 预约 → 线下交接 → 评价信用”构建完整流程，同时提供求购匹配、捐赠回收、后台管理与可选的小循 AI 选书助手。

项目采用 **FastAPI + SQLAlchemy + Vue 3**。默认使用 SQLite 和本地文件存储，前端零构建，Vue 运行时随仓库提供。运行网页前，使用者需要自行配置 Python 环境、虚拟环境（可选）并安装 `requirements.txt`；日常运行不需要 MySQL、Redis 或 Node.js，Node.js 仅用于可选的静态检查。

## 功能概览

| 模块 | 主要功能 |
| --- | --- |
| 教材目录 | 书籍编号、课程关联、学科筛选、封面目录、Excel 导入 |
| 校园集市 | 出售与求购、成色和价格筛选、收藏、匹配提醒 |
| 交易流程 | 预约锁定、卖方确认、改约、取消、核销、超时处理 |
| 交接与信用 | 交接点、时段容量、暂存、双向评价、信用记录、申诉 |
| 管理后台 | 内容审核、用户、系统参数、捐赠、统计导出、操作日志 |
| 小循助手 | 基于公开目录和平台规则答疑、携书提问、模型切换 |
| 网页体验 | 响应式页面、键盘操作、轻量卡片动效、减少动态效果支持 |

线上完成匹配和预约，验书及付款在线下进行。当前面向课程演示；短信、微信模拟模式及外部服务边界见 [工程说明](docs/architecture.md#当前实现边界)。

## 快速开始

### 1. 获取代码并自行配置环境

克隆或下载本仓库，进入包含 `run.py` 的项目根目录。

运行环境和依赖由使用者根据本机系统自行准备；创建并激活虚拟环境（已有可用环境时可跳过）：
```
conda create -n <环境名> python=<版本号>
conda activate <环境名>
python -m pip install -r requirements.txt
```

Windows PowerShell：

```powershell
python scripts/init_data.py
python run.py
```

Linux / macOS：

```bash
python scripts/init_data.py
python run.py
```

如果不使用虚拟环境，请将示例中的 `python` 替换为已配置好的系统解释器（Windows 可使用 `py`，Linux / macOS 可使用 `python3`）。后续文档中的 `python` 均指当前已配置并安装项目依赖的解释器。

### 2. 打开应用

- 网页：<http://127.0.0.1:8000>
- 交互 API 文档：<http://127.0.0.1:8000/api/docs>
- 健康检查：<http://127.0.0.1:8000/api/health>

完成上述环境准备后，项目默认使用 SQLite 和本地文件存储即可运行。需要 AI 或其他参数时，由使用者自行将 `configs/.env.example` 复制为 `configs/.env` 并编辑；也可以直接设置系统环境变量。`configs/.env` 中的密钥不会提交到 Git。

### 3. 使用演示账号

| 角色 | 账号 | 初始演示密码 |
| --- | --- | --- |
| 学生 / 演示卖方 | `20230001` | `campus@2026` |
| 学生 / 演示买方 | `20230002` | `campus@2026` |
| 信用受限学生（可购买） | `20230004` | `campus@2026` |
| 图书馆交接点管理员 | `T2023001` | `campus@2026` |
| 平台管理员 | `admin` | `admin@2026` |

空数据库初始化后有 9 个用户、51 个教材条目、10 门课程、10 条挂牌、4 个交接点和 3 条求购。订单、评价和捐赠由演示操作产生。日常启动只需 `python run.py`。

初始化是增量操作；`DEMO_PWD` / `ADMIN_PWD` 只影响新创建的账号。`--reset` 会清空当前数据库全部表，仅用于可丢弃的演示库。

## 项目结构

```text
BookLoop/
├── configs/                 环境变量示例；本地 .env 不提交
├── data/
│   └── seed/                可提交的 JSON 演示数据与封面
├── docs/
│   ├── architecture.md      架构、数据关系与代码讲解
│   ├── defense.md            答辩演示路线与常见问题
│   ├── course/               课程需求、计划与设计说明书
│   └── design/               设计素材原图（校园图片、关系图）
├── scripts/
│   ├── init_data.py         初始化演示数据
│   ├── import_books.py      导入 Excel 教材目录
│   ├── import_covers.py     同步封面目录并备份 SQLite
│   └── check.py             隔离环境自检
├── src/                     FastAPI 后端
│   ├── core/                配置、鉴权、安全、统一响应
│   ├── routers/             HTTP 业务接口
│   ├── services/            业务服务与定时维护
│   ├── db.py                数据库引擎、会话及建表
│   ├── models.py            ORM 数据表
│   ├── schemas.py           请求校验模型
│   └── main.py              应用组装与静态托管
├── web/                     Vue 3 前端
│   ├── assets/              品牌图标与校园 WebP 图片
│   ├── css/                 页面与助手样式
│   ├── js/pages/            页面组件
│   ├── js/                  API、共享状态、组件与动效
│   ├── vendor/              Vue 运行时及第三方许可证
│   ├── index.html           网页入口
│   └── user-agreement.html  用户协议页面
├── run.py                   本地启动入口
└── requirements.txt         本地运行直接依赖（固定版本）
```

运行后在 `data/` 自动生成 `app.db`、`.aes_key` 和 `uploads/`；这些内容及日志、备份、虚拟环境和工具索引均被 Git 忽略。仓库通过种子数据重建演示环境，不分发真实运行数据库。

## 开发与可选检查

如需运行隔离环境自检，使用者需自行安装 **Node.js 22**，并先完成 Python 依赖配置：

```bash
python scripts/check.py
```

该命令检查 Python / JavaScript 语法和本地静态资源，再在临时目录创建数据库、启动独立本地服务，验证：

- 从空库初始化，以及重复初始化不产生重复记录。
- 首页资源、教材目录、全部已配置封面与平台编号搜索。
- 图片上传、发布挂牌及实物照片读取。
- 学生、交接点管理员、平台管理员登录和后台权限。
- 买方预约 → 卖方确认 → 管理员核销 → 买方评价。
- 学生捐赠与助手可用状态。
- 封面同步前的 SQLite 备份，以及空库 Excel 导入和重复导入。

检查进程不会读取个人 `configs/.env`，不会使用现有数据库或调用外部 AI。完成后停止临时服务并清理数据。自动检查不代替浏览器视觉验收和外部服务集成测试。

## 常用维护命令

```bash
python scripts/import_books.py "教材目录.xlsx"
python scripts/import_covers.py
```

`isbn` 接口字段兼容保留，实际含义是 **13 位平台书籍编号**。编号与图片文件名独立，卖家实物照片和目录参考封面分开保存。`data/seed/` 只放可提交的演示数据与目录封面，真实数据库、上传和备份由 `.gitignore` 排除。

可选 MySQL、Redis 或 S3/MinIO 服务需在 `requirements.txt` 中取消注释对应依赖，并按 `configs/.env.example` 配置参数；默认课程演示不需要。小循需要后端 `AI_API_KEY`，未配置时显示不可用状态。

## 答辩与文档

- [工程结构与代码讲解](docs/architecture.md)
- [答辩演示路线与常见问题](docs/defense.md)

## 发布到 GitHub

本地运行数据通过 `.gitignore` 排除。首次提交前执行自检，再检查文件清单：

```bash
git status --short
git add .
git diff --cached --stat
git diff --cached --name-only
```

待提交列表应包含源代码、文档、`data/seed/` 和配置示例，不应包含 `configs/.env`、数据库、`.aes_key`、上传、备份或 `.venv/`。确认后创建提交，按 GitHub 空仓库页面提示配置远程并推送。已有仓库先检查 `git remote -v`，避免覆盖已有远程。

