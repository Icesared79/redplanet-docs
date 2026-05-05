"""Fetch Notion pages by ID, convert block tree to clean markdown.

Outputs each page as raw/<slug>.md so a combiner step can stitch them.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / ".scripts" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Load NOTION_TOKEN from atlas/.env
ENV_PATH = Path("C:/Users/pauld/atlas/.env")
TOKEN = None
for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
    if line.startswith("NOTION_TOKEN="):
        TOKEN = line.split("=", 1)[1].strip()
        break
if not TOKEN:
    sys.exit("NOTION_TOKEN not found in atlas/.env")

NOTION_VERSION = "2022-06-28"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

PAGES = [
    ("01_the_problem",                "3563b02528a4812e8cc8fe8100fa5cac"),
    ("02_what_atlas_is",              "3563b02528a481d18708d4a0872ccc92"),
    ("02_intelligence_layer",         "3563b02528a4810dbffbe480ba6f2bc4"),
    ("03_data_asset",                 "3563b02528a4815bba00d32552e02df4"),
    ("04_platform_model",             "3563b02528a481fdadcec8a4fb78de9d"),
    ("04_product_velocity",           "3563b02528a481179f0ec5eddb6d5c26"),
    ("05_pipeline",                   "3573b02528a48182a20ac87e4cd4b574"),
    ("05_self_correction",            "3573b02528a481b28364ef351e3a18d5"),
    ("06_development_model",          "3573b02528a481958f4ad02432e22334"),
    ("07_data_quality",               "3573b02528a48143a7a9e24d4d5b3690"),
]
# "Where We're Going" — page ID not provided; we'll resolve it via search


def http(method: str, url: str, body: dict | None = None, retries: int = 3) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(retries):
        req = request.Request(url, data=data, headers=HEADERS, method=method)
        try:
            with request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            print(f"HTTPError {e.code} on {url}: {e.read().decode()[:300]}", file=sys.stderr)
            raise
    raise RuntimeError("unreachable")


def get_page(page_id: str) -> dict:
    return http("GET", f"https://api.notion.com/v1/pages/{page_id}")


def get_block_children(block_id: str) -> list[dict]:
    out: list[dict] = []
    cursor: str | None = None
    while True:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        resp = http("GET", url)
        out.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return out


def search_for_where_were_going() -> str | None:
    body = {"query": "Where We're Going", "filter": {"property": "object", "value": "page"}}
    resp = http("POST", "https://api.notion.com/v1/search", body=body)
    for r in resp.get("results", []):
        title = ""
        props = r.get("properties", {})
        for v in props.values():
            if v.get("type") == "title":
                title = "".join(t["plain_text"] for t in v["title"])
                break
        if "where we" in title.lower():
            return r["id"]
    # fallback: try variant
    body["query"] = "Where We Are Going"
    resp = http("POST", "https://api.notion.com/v1/search", body=body)
    for r in resp.get("results", []):
        title = ""
        props = r.get("properties", {})
        for v in props.values():
            if v.get("type") == "title":
                title = "".join(t["plain_text"] for t in v["title"])
                break
        if "where" in title.lower() and "going" in title.lower():
            return r["id"]
    return None


# ---- block → markdown ------------------------------------------------------

def rich_to_md(rich: list[dict]) -> str:
    out = []
    for r in rich:
        t = r.get("plain_text", "")
        ann = r.get("annotations", {})
        href = r.get("href")
        if ann.get("code"):
            t = f"`{t}`"
        if ann.get("bold"):
            t = f"**{t}**"
        if ann.get("italic"):
            t = f"*{t}*"
        if ann.get("strikethrough"):
            t = f"~~{t}~~"
        if href:
            t = f"[{t}]({href})"
        out.append(t)
    return "".join(out)


def block_to_md(block: dict, depth: int = 0) -> str:
    btype = block["type"]
    data = block.get(btype, {})
    pad = "  " * depth
    md = ""

    if btype == "paragraph":
        md = pad + rich_to_md(data.get("rich_text", []))
    elif btype == "heading_1":
        md = "# " + rich_to_md(data.get("rich_text", []))
    elif btype == "heading_2":
        md = "## " + rich_to_md(data.get("rich_text", []))
    elif btype == "heading_3":
        md = "### " + rich_to_md(data.get("rich_text", []))
    elif btype == "bulleted_list_item":
        md = pad + "- " + rich_to_md(data.get("rich_text", []))
    elif btype == "numbered_list_item":
        md = pad + "1. " + rich_to_md(data.get("rich_text", []))
    elif btype == "to_do":
        check = "x" if data.get("checked") else " "
        md = pad + f"- [{check}] " + rich_to_md(data.get("rich_text", []))
    elif btype == "toggle":
        md = pad + "**" + rich_to_md(data.get("rich_text", [])) + "**"
    elif btype == "quote":
        md = "> " + rich_to_md(data.get("rich_text", []))
    elif btype == "callout":
        md = "> " + rich_to_md(data.get("rich_text", []))
    elif btype == "code":
        lang = data.get("language", "")
        body = rich_to_md(data.get("rich_text", []))
        md = f"```{lang}\n{body}\n```"
    elif btype == "divider":
        md = "---"
    elif btype == "image":
        img = data.get("file") or data.get("external") or {}
        url = img.get("url", "")
        cap = rich_to_md(data.get("caption", []))
        md = f"![{cap}]({url})"
    elif btype == "bookmark":
        url = data.get("url", "")
        md = f"<{url}>"
    elif btype == "table_of_contents":
        md = ""  # gitbook generates its own TOC
    elif btype == "child_page":
        md = f"**{data.get('title','')}**"
    elif btype == "equation":
        md = f"$$ {data.get('expression','')} $$"
    else:
        # Fallback: try to extract any rich_text we can find
        rt = data.get("rich_text", [])
        if rt:
            md = pad + rich_to_md(rt)
        else:
            md = ""

    # Recurse into children
    if block.get("has_children"):
        children = get_block_children(block["id"])
        child_md = "\n\n".join(filter(None, (block_to_md(c, depth + 1) for c in children)))
        if child_md:
            md = (md + "\n" + child_md) if md else child_md
    return md


def get_page_title(page: dict) -> str:
    props = page.get("properties", {})
    for v in props.values():
        if v.get("type") == "title":
            return "".join(t["plain_text"] for t in v["title"]).strip()
    return ""


def fetch_one(slug: str, page_id: str) -> tuple[str, str]:
    print(f"[fetch] {slug} ({page_id})", flush=True)
    page = get_page(page_id)
    title = get_page_title(page) or slug
    blocks = get_block_children(page_id)
    parts = []
    for b in blocks:
        bm = block_to_md(b, 0)
        if bm:
            parts.append(bm)
    body = "\n\n".join(parts)
    return title, body


def main():
    pages = list(PAGES)
    # resolve "Where We're Going"
    wwg_id = search_for_where_were_going()
    if wwg_id:
        pages.append(("07_where_were_going", wwg_id))
        print(f"[search] resolved 'Where We're Going' to {wwg_id}", flush=True)
    else:
        print("[warn] could not resolve 'Where We're Going' page id", flush=True)

    index = {}
    for slug, pid in pages:
        try:
            title, body = fetch_one(slug, pid)
        except Exception as e:
            print(f"[error] {slug} ({pid}): {e}", flush=True)
            index[slug] = {"page_id": pid, "title": None, "error": str(e)}
            continue
        out = RAW_DIR / f"{slug}.md"
        out.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
        index[slug] = {"page_id": pid, "title": title, "bytes": len(body)}

    (ROOT / ".scripts" / "index.json").write_text(
        json.dumps(index, indent=2), encoding="utf-8"
    )
    print(json.dumps(index, indent=2))


if __name__ == "__main__":
    main()
