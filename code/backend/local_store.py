import json
import os
import time
import uuid


HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")
STORE_PATH = os.path.join(DATA_DIR, "store.json")


DEFAULT_STORE = {
    "uploads": [],
    "projects": [
        {"id": "project-promo", "kind": "promo", "name": "运营素材库", "created_at": "2026-07-10"},
        {"id": "project-sales", "kind": "sales", "name": "销售知识库", "created_at": "2026-07-10"},
    ],
    "kb": {
        "sales": [
            {"id": "sales-1", "category": "销售话术", "title": "Analytics AI Mode 开场介绍", "body": "适用于首次拜访企业 IP 负责人，强调专利数据库与 AI 分析工作流。", "product": "数据库", "updated_at": "2026-07-10"},
            {"id": "sales-2", "category": "FAQ", "title": "客户问：AI Mode 的结果可以追溯吗？", "body": "回答需强调来源引用、结果可复核、报告可交付。", "product": "数据库", "updated_at": "2026-07-10"},
            {"id": "sales-3", "category": "竞品攻防", "title": "Clarivate 对比口径", "body": "对方强在全球 IP 情报资产和成熟服务，我方重点强调自然语言入口和分析交付效率。", "product": "数据库", "updated_at": "2026-07-10"},
            {"id": "sales-4", "category": "客户案例", "title": "制造业客户专利布局分析", "body": "客户使用数据库检索与分析能力识别技术空白点，形成研发决策材料。", "product": "数据库", "updated_at": "2026-07-10"}
        ],
        "promo": [
            {"id": "promo-1", "category": "IP Search", "title": "Analytics AI Mode 公众号首图", "body": "用于专利检索、专利解读相关传播。", "product": "IP Search", "updated_at": "2026-07-10"},
            {"id": "promo-2", "category": "IP Drafting", "title": "专利撰写流程介绍视频", "body": "可复用为活动预热视频或销售转发素材。", "product": "IP Drafting", "updated_at": "2026-07-10"},
            {"id": "promo-3", "category": "Life Sciences", "title": "LS 行业解决方案推文", "body": "面向生物医药客户的行业场景文案。", "product": "Life Sciences", "updated_at": "2026-07-10"},
            {"id": "promo-4", "category": "Materials", "title": "材料领域活动排期", "body": "包含 webinar、社媒发文和销售跟进节奏。", "product": "Materials", "updated_at": "2026-07-10"}
        ]
    }
}


def ensure_dirs():
    for path in (DATA_DIR, UPLOAD_DIR, EXPORT_DIR):
        os.makedirs(path, exist_ok=True)


def load_store():
    ensure_dirs()
    if not os.path.exists(STORE_PATH):
        save_store(DEFAULT_STORE)
    with open(STORE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("uploads", [])
    data.setdefault("projects", [])
    if not data["projects"]:
        data["projects"] = list(DEFAULT_STORE["projects"])
    data.setdefault("kb", {}).setdefault("sales", [])
    data.setdefault("kb", {}).setdefault("promo", [])
    return data


def save_store(data):
    ensure_dirs()
    tmp = STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STORE_PATH)


def today():
    return time.strftime("%Y-%m-%d")


def safe_filename(name):
    keep = []
    for ch in name:
        if ch.isalnum() or ch in ".-_()[] ":
            keep.append(ch)
    out = "".join(keep).strip().replace("/", "_")
    return out or "upload.txt"


def guess_text(data: bytes) -> str:
    for enc in ("utf-8", "utf-16", "gb18030"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            text = ""
    if not text:
        text = f"[二进制文件，大小 {len(data)} bytes，暂未接入专用解析器]"
    return text[:20000]


def add_upload(filename, content: bytes, description="", visibility="销售和运营可见", owner="算法研发团队", kind="sales", category="研发资料"):
    if kind not in ("sales", "promo"):
        raise ValueError("未知知识库类型")
    data = load_store()
    item_id = "up-" + uuid.uuid4().hex[:10]
    clean = safe_filename(filename)
    disk_name = f"{item_id}-{clean}"
    disk_path = os.path.join(UPLOAD_DIR, disk_name)
    with open(disk_path, "wb") as f:
        f.write(content)

    text = guess_text(content)
    title = description.strip() or clean
    item = {
        "id": item_id,
        "filename": clean,
        "disk_name": disk_name,
        "description": description.strip(),
        "visibility": visibility,
        "owner": owner,
        "status": "已入库",
        "updated_at": today(),
        "size": len(content),
    }
    data["uploads"].insert(0, item)

    data["kb"][kind].insert(0, {
        "id": kind + "-" + uuid.uuid4().hex[:10],
        "category": category or ("上传素材" if kind == "promo" else "研发资料"),
        "title": title,
        "body": text[:420],
        "product": "上传素材" if kind == "promo" else "上传资料",
        "updated_at": today(),
        "source_upload": item_id,
    })
    save_store(data)
    return item


def sync_live_material(item, text):
    """Legacy helper kept for old tests/tools.

    Do not call this from normal upload flow: sample_retrieval/live/ is owned by
    the retrieval black box and may be overwritten on every user query.
    """
    live_dir = os.path.join(HERE, "..", "sample_retrieval", "live")
    ensure_dirs()
    os.makedirs(live_dir, exist_ok=True)
    path = os.path.join(live_dir, item["id"] + ".md")
    body = text.replace("\r\n", "\n").strip()
    md = (
        "---\n"
        f"source: uploads/{item['filename']}\n"
        f"updated_at: {item['updated_at']}\n"
        "authority: L2\n"
        f"topic: upload/{item['id']}\n"
        "score: 0.9\n"
        f"title: {item['filename']}\n"
        "---\n\n"
        f"# {item['filename']}\n\n"
        f"{item.get('description') or '用户上传资料'}\n\n"
        f"{body}\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)


def list_kb(kind=None):
    data = load_store()
    if kind in ("sales", "promo"):
        return data["kb"][kind]
    return data["kb"]


def list_projects():
    return load_store().get("projects", [])


def add_project(name, kind="sales"):
    if kind not in ("sales", "promo"):
        raise ValueError("未知知识项目类型")
    name = (name or "").strip()
    if not name:
        raise ValueError("项目名称不能为空")
    data = load_store()
    project = {
        "id": "project-" + uuid.uuid4().hex[:10],
        "kind": kind,
        "name": name[:40],
        "created_at": today(),
    }
    data.setdefault("projects", []).append(project)
    data["kb"][kind].insert(0, {
        "id": kind + "-" + uuid.uuid4().hex[:10],
        "category": "自定义项目",
        "title": name[:40],
        "body": "自定义知识项目，可通过上传资料、导入素材或新增知识条目继续沉淀内容。",
        "product": name[:40],
        "updated_at": today(),
        "project_id": project["id"],
    })
    save_store(data)
    return project


def add_kb(kind, item):
    if kind not in ("sales", "promo"):
        raise ValueError("未知知识库类型")
    data = load_store()
    new_item = {
        "id": kind + "-" + uuid.uuid4().hex[:10],
        "category": item.get("category") or "未分类",
        "title": item.get("title") or "未命名知识",
        "body": item.get("body") or "",
        "product": item.get("product") or "",
        "updated_at": today(),
    }
    data["kb"][kind].insert(0, new_item)
    save_store(data)
    return new_item


def export_text(title, content, suffix=".md"):
    ensure_dirs()
    name = safe_filename(title)[:80] or "export"
    if not name.endswith(suffix):
        name += suffix
    path = os.path.join(EXPORT_DIR, f"{int(time.time())}-{name}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
