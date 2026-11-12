"""
教材目录 Excel 批量导入脚本（命令行版）。

与后台 /api/catalog/books/import 接口同一套导入逻辑：
按平台书籍编号去重，留空自动分配 13 位顺序编号，并自动建立课程与课程—教材关联。

用法：
    python scripts/import_books.py "教材目录.xlsx"

Excel 表头须包含：课程代码、课程名、书籍编号、书名、作者、出版社、版次、定价、
任课教师、学院、学期、用途（后四列可选）。
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

# 让脚本在任意目录下都能 import src.*
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.db import SessionLocal, init_db  # noqa: E402
from src.services.catalog_import import import_catalog


def import_file(path: str | BytesIO) -> dict:
    init_db()
    with SessionLocal() as db:
        result = import_catalog(db, path)
        db.commit()
    return result


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print("用法：python scripts/import_books.py <Excel 文件路径>")
        sys.exit(1)
    result = import_file(sys.argv[1])
    print(f"导入完成：新增教材 {result['created_book']} 条，更新 {result['updated']} 条，"
          f"新增课程 {result['created_course']} 门，建立关联 {result['linked']} 条，跳过 {result['skipped']} 行")
    if result["errors"]:
        print("跳过明细：")
        for e in result["errors"]:
            print("  -", e)
