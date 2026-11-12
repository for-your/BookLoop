from functools import lru_cache
import json

from sqlalchemy import case, func, or_

from ..core.config import SEED_DIR, UPLOAD_DIR
from ..models import Book


COVER_DIR = SEED_DIR / "covers"
CATEGORIES = (
    ("math", "数学与理学", ("数学", "代数", "概率", "统计", "量子", "运筹")),
    ("computing", "计算机与软件", ("计算机", "软件", "数据结构", "数据库", "编译", "程序", "算法", "java", "android", "vue", "机器学习", "设计模式", "操作系统")),
    ("electronics", "电子与通信", ("信号", "电路", "电子", "通信")),
    ("engineering", "机械与工程", ("机械", "力学", "材料", "工程")),
    ("business", "经管与会计", ("管理", "会计", "经济", "营销")),
    ("languages", "语言与外语", ("英语", "英文", "翻译", "外语", "英国文学")),
    ("humanities", "人文与阅读", ("文学", "汉语", "新闻", "历史", "哲学")),
    ("other", "其他好书", ()),
)
CATEGORY_NAMES = {category: name for category, name, keywords in CATEGORIES}


def category_for(title: str) -> str:
    normalized = title.casefold()
    for category, name, keywords in CATEGORIES:
        if any(keyword in normalized for keyword in keywords):
            return category
    return "other"


def category_expression():
    return case(
        *((or_(*(func.lower(Book.title).contains(keyword) for keyword in keywords)), category)
          for category, name, keywords in CATEGORIES if keywords),
        else_="other",
    )


def book_visuals(book: Book | None) -> dict:
    if book is None:
        return {"cover": "", "cover_source": "missing", "category": "other", "category_name": CATEGORY_NAMES["other"]}
    cover = book.cover or ""
    category = category_for(book.title)
    return {"cover": cover, "cover_source": "catalog" if cover else "missing", "category": category, "category_name": CATEGORY_NAMES[category]}


def listing_images(value: str) -> list[str]:
    try:
        images = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(images, list):
        return []
    result = []
    for image in images:
        if not isinstance(image, str) or not image:
            continue
        if image.startswith("/static/uploads/"):
            relative = image.removeprefix("/static/uploads/")
            if not relative or "/" in relative or "\\" in relative or not (UPLOAD_DIR / relative).is_file():
                continue
        result.append(image)
    return result


@lru_cache(maxsize=1)
def _cover_entries() -> tuple[dict, ...]:
    with (SEED_DIR / "cover-library.json").open(encoding="utf-8") as source:
        return tuple(json.load(source)["books"])


def cover_assets() -> list[dict]:
    result = []
    filenames = set()
    for entry in _cover_entries():
        filename = entry["file"]
        if filename in filenames or "/" in filename or "\\" in filename or not (COVER_DIR / filename).is_file():
            raise ValueError("封面文件重复或不存在：" + filename)
        filenames.add(filename)
        result.append({**entry, "cover": "/static/covers/" + filename, "category_name": CATEGORY_NAMES[entry["category"]]})
    return result
