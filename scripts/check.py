"""项目自检：语法、静态资源、全新数据库初始化和真实 HTTP 交易流程。"""
from __future__ import annotations

import ast
from contextlib import closing
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
HTTP = build_opener(ProxyHandler({}))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check_sources():
    python_files = [ROOT / "run.py", *sorted((ROOT / "src").rglob("*.py")), *sorted((ROOT / "scripts").rglob("*.py"))]
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = shutil.which("node")
    require(node, "Node.js is required for JavaScript syntax checks (Node 22 recommended).")
    javascript_files = sorted((ROOT / "web").rglob("*.js"))
    for path in javascript_files:
        subprocess.run([node, "--check", str(path)], check=True, capture_output=True, text=True)

    for path in (ROOT / "web").glob("*.html"):
        for reference in re.findall(r'(?:src|href)="(\./[^"?#]+)', path.read_text(encoding="utf-8")):
            require((path.parent / reference).is_file(), f"Missing HTML asset: {reference}")
    manifest = json.loads((ROOT / "data/seed/cover-library.json").read_text(encoding="utf-8"))
    filenames = [entry["file"] for entry in manifest["books"]]
    require(len(filenames) == len(set(filenames)), "Duplicate cover filename")
    for filename in filenames:
        require(Path(filename).name == filename and "\\" not in filename, "Invalid cover filename")
        require((ROOT / "data/seed/covers" / filename).is_file(), f"Missing cover: {filename}")
    print(f"PASS syntax: {len(python_files)} Python, {len(javascript_files)} JavaScript; assets: {len(filenames)} covers")


def request(base, path, body=None, token="", expected_status=200, content_type="application/json"):
    headers = {"Content-Type": content_type}
    if token:
        headers["Authorization"] = "Bearer " + token
    payload = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None
    try:
        response = HTTP.open(Request(base + path, data=payload, headers=headers), timeout=10)
    except HTTPError as error:
        response = error
    with response:
        content = response.read()
        require(response.status == expected_status, f"HTTP {response.status} at {path}: {content[:300]!r}")
        if response.headers.get_content_type() != "application/json":
            return content
        result = json.loads(content)
    if expected_status == 200:
        require(result.get("code") == 0, f"Business error at {path}: {result}")
        return result["data"]
    return result


def database_counts(database):
    tables = ("users", "books", "courses", "course_books", "handoff_points", "listings", "wanted", "wechat_bindings")
    with closing(sqlite3.connect(database)) as connection:
        return {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}


def check_workflow(base):
    html = request(base, "/").decode("utf-8")
    for source in re.findall(r'(?:src|href)="(\./[^\"]+)"', html):
        request(base, "/" + source.removeprefix("./"))
    request(base, "/user-agreement.html")
    catalog = request(base, "/api/catalog/books?size=100")
    require(catalog["total"] == 51, "Unexpected fresh catalog size")
    for book in catalog["items"]:
        if book["cover"]:
            request(base, book["cover"])
    matches = request(base, "/api/catalog/books?keyword=" + quote("0000000000002"))
    require(matches["total"] == 1, "Book-number search failed")
    request(base, "/api/assistant/status")
    print("PASS homepage assets, catalog, covers, search, assistant status")

    def login(student_no, password="campus@2026"):
        return request(base, "/api/auth/login", {"student_no": student_no, "password": password})["access_token"]

    buyer = login("20230002")
    seller = login("20230001")
    admin = login("admin", "admin@2026")
    point_admin = login("T2023001")
    request(base, "/api/auth/me", token=buyer)
    request(base, "/api/admin/users", token=buyer, expected_status=403)
    request(base, "/api/admin/users", token=admin)
    request(base, "/api/handoff/points", token=point_admin)

    listings = request(base, "/api/listings/mine", token=seller)
    listing = listings[0]

    image = next((ROOT / "data/seed/covers").glob("*.jpg")).read_bytes()
    boundary = "bookloop-smoke-upload"
    multipart = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="check.jpg"\r\n'
        'Content-Type: image/jpeg\r\n\r\n'
    ).encode() + image + f"\r\n--{boundary}--\r\n".encode()
    uploaded = request(base, "/api/upload", multipart, content_type=f"multipart/form-data; boundary={boundary}")
    require(request(base, uploaded["url"]) == image, "Uploaded image did not round-trip")
    points = request(base, "/api/handoff/points", token=seller)
    published = request(base, "/api/listings", {
        "book_id": listing["book_id"], "condition_level": "九成新", "price": 1,
        "images": [uploaded["url"]], "point_id": points[0]["id"],
    }, seller)
    detail = request(base, f"/api/search/{published['id']}")
    require(detail["images"] == [uploaded["url"]], "Listing images did not use the isolated upload directory")
    print("PASS isolated image upload, publishing and listing image lookup")

    order = request(base, "/api/orders", {"listing_id": listing["id"]}, buyer)
    require(order["status"] == "pending", "Reservation did not enter pending state")
    order_path = f"/api/orders/{order['id']}"
    confirmed = request(base, order_path + "/confirm", {}, seller)
    require(confirmed["status"] == "confirmed", "Seller confirmation failed")
    completed = request(base, order_path + "/verify", {"code": confirmed["verify_code"]}, admin)
    require(completed["status"] == "completed", "Handoff verification failed")
    request(base, "/api/reviews", {"order_id": order["id"], "comment": "Isolated smoke check"}, buyer)
    reviews = request(base, f"/api/reviews/order/{order['id']}", token=buyer)
    require(len(reviews) == 1, "Review was not persisted")
    request(base, "/api/admin/donations", {"book_id": listing["book_id"], "quantity": 1}, buyer)
    donations = request(base, "/api/admin/donations", token=buyer)
    require(len(donations) == 1, "Donation was not persisted")
    print("PASS login, role checks, reservation -> confirmation -> handoff -> review, donation")


def check_import_commands(temporary, environment):
    from openpyxl import Workbook

    subprocess.run(
        [sys.executable, str(ROOT / "scripts/import_covers.py")],
        cwd=ROOT, env=environment, check=True, capture_output=True, text=True, encoding="utf-8",
    )
    require(list((temporary / "backups").glob("*.db")), "Cover import did not create its SQLite backup")
    workbook = Workbook()
    workbook.active.append(["书名", "定价", "课程代码", "课程名"])
    workbook.active.append(["Import check", 20, "CHECK101", "Import course"])
    source = temporary / "catalog.xlsx"
    workbook.save(source)
    workbook.close()
    import_environment = {**environment, "BOOKLOOP_DATA_DIR": str(temporary / "import-data")}
    command = [sys.executable, str(ROOT / "scripts/import_books.py"), str(source)]
    for attempt in range(2):
        subprocess.run(command, cwd=ROOT, env=import_environment, check=True, capture_output=True, text=True, encoding="utf-8")
    with closing(sqlite3.connect(temporary / "import-data/app.db")) as connection:
        require(connection.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 1, "Excel import duplicated books")
        require(connection.execute("SELECT COUNT(*) FROM course_books").fetchone()[0] == 1, "Excel import duplicated course links")
    print("PASS cover sync with backup and repeat Excel import into a fresh database")


def check_runtime():
    # 不导入本地配置：子进程只读取临时环境文件，数据库和密钥也在临时目录。
    with tempfile.TemporaryDirectory(prefix="bookloop-check-") as directory:
        temporary = Path(directory)
        environment = os.environ.copy()
        environment.update({
            "BOOKLOOP_ENV_FILE": str(temporary / "empty.env"),
            "BOOKLOOP_DATA_DIR": str(temporary),
            "DB_DIALECT": "sqlite", "USE_REDIS": "false", "STORAGE_TYPE": "local",
            "DEBUG": "false", "WECHAT_MOCK": "true", "AI_ENABLED": "false", "AI_API_KEY": "",
            "AES_KEY": "", "SECRET_KEY": "isolated-check-secret-key-at-least-32-characters",
            "DEMO_PWD": "campus@2026", "ADMIN_PWD": "admin@2026", "PYTHONUTF8": "1",
        })
        seed_command = [sys.executable, str(ROOT / "scripts/init_data.py")]
        subprocess.run(seed_command, cwd=ROOT, env=environment, check=True, capture_output=True, text=True, encoding="utf-8")
        counts = database_counts(temporary / "app.db")
        subprocess.run(seed_command, cwd=ROOT, env=environment, check=True, capture_output=True, text=True, encoding="utf-8")
        require(counts == database_counts(temporary / "app.db"), "Seeding twice duplicated data")
        require(counts["users"] == 9 and counts["listings"] == 10, "Demo accounts or listings are missing")
        with closing(sqlite3.connect(temporary / "app.db")) as connection:
            assigned = connection.execute("SELECT point_id FROM users WHERE role = 'point_admin' ORDER BY id").fetchall()
            require(assigned == [(1,), (3,)], "Demo point-admin assignments are incorrect")
        print("PASS fresh initialization and repeat initialization")

        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        command = [sys.executable, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", str(port)]
        log_path = temporary / "server.log"
        with log_path.open("w", encoding="utf-8") as log:
            server = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 30
                while True:
                    require(server.poll() is None, "Check server exited during startup")
                    try:
                        request(base, "/api/health")
                        break
                    except (URLError, TimeoutError):
                        require(time.monotonic() < deadline, "Check server startup timed out")
                        time.sleep(0.2)
                check_workflow(base)
            except Exception:
                print(log_path.read_text(encoding="utf-8", errors="replace")[-4000:])
                raise
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
        check_import_commands(temporary, environment)


if __name__ == "__main__":
    try:
        check_sources()
        check_runtime()
    except subprocess.CalledProcessError as error:
        print(error.stdout or "", error.stderr or "", file=sys.stderr)
        raise SystemExit(error.returncode)
    print("All checks passed; temporary data removed.")
