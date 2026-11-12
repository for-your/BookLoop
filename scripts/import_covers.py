import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import DATA_DIR
from src.db import SessionLocal, engine, init_db
from src.services.cover_import import import_cover_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="真实封面导入教材目录，已有记录按书名匹配")
    parser.add_argument("--renumber", action="store_true", help="按现有教材 ID 顺序重编为 13 位平台编号")
    options = parser.parse_args()
    init_db()
    if engine.dialect.name == "sqlite" and engine.url.database and Path(engine.url.database).is_file():
        backup_dir = DATA_DIR / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / ("app-before-cover-import-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".db")
        with sqlite3.connect(engine.url.database) as source, sqlite3.connect(backup) as destination:
            source.backup(destination)
        print("导入前备份：", backup)
    with SessionLocal() as db:
        result = import_cover_catalog(db, renumber=options.renumber)
        db.commit()
    print("封面导入完成：", result)


if __name__ == "__main__":
    main()
