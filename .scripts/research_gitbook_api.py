"""Research GitBook API capabilities.

Pulls the OpenAPI spec + key developer docs pages, then extracts the
endpoints relevant to: spaces, GitHub sync, visibility/auth, custom domains.

Reports findings to stdout. No mutations, no auth required for the spec.
"""
from __future__ import annotations

import json
import re
import sys
from urllib import request, error

CANDIDATE_OPENAPI_URLS = [
    "https://api.gitbook.com/openapi.json",
    "https://api.gitbook.com/v1/openapi.json",
    "https://api.gitbook.com/openapi.yaml",
    "https://gitbook.com/openapi.json",
    "https://developer.gitbook.com/api-reference/openapi.json",
]

DOC_URLS = [
    "https://developer.gitbook.com/",
    "https://developer.gitbook.com/api-reference/spaces",
    "https://developer.gitbook.com/api-reference/git-sync",
    "https://developer.gitbook.com/api-reference/sites",
    "https://developer.gitbook.com/api-reference/collections",
    "https://gitbook.com/docs/getting-started/git-sync",
    "https://gitbook.com/docs/publishing-documentation/publish-your-docs",
    "https://gitbook.com/docs/publishing-documentation/share/visitor-authentication",
    "https://gitbook.com/docs/publishing-documentation/customize-your-content/custom-domain",
]


def fetch(url: str, timeout: int = 30) -> tuple[int, bytes, str]:
    req = request.Request(url, headers={"User-Agent": "rpd-research/1.0"})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, resp.read(), ctype
    except error.HTTPError as e:
        return e.code, e.read() if e.fp else b"", e.headers.get("Content-Type", "")
    except Exception as e:
        return 0, str(e).encode(), ""


def find_openapi() -> dict | None:
    for url in CANDIDATE_OPENAPI_URLS:
        status, body, ctype = fetch(url)
        print(f"[probe] {url} -> {status} ({ctype}, {len(body)} bytes)", file=sys.stderr)
        if status == 200 and body and (b'"openapi"' in body[:500] or b"openapi:" in body[:200]):
            try:
                if "json" in ctype or body.lstrip().startswith(b"{"):
                    return json.loads(body.decode())
            except Exception as e:
                print(f"[parse] {url}: {e}", file=sys.stderr)
                continue
    return None


def summarize_openapi(spec: dict) -> None:
    print("\n=== OpenAPI ===")
    info = spec.get("info", {})
    print(f"Title: {info.get('title')}")
    print(f"Version: {info.get('version')}")
    servers = [s.get("url") for s in spec.get("servers", [])]
    print(f"Servers: {servers}")

    paths = spec.get("paths", {})
    print(f"Total paths: {len(paths)}\n")

    keywords = {
        "spaces":   re.compile(r"/spaces", re.I),
        "git-sync": re.compile(r"git[-_]?sync|github|integration", re.I),
        "auth/visibility": re.compile(r"visibility|publish|share|auth|password|access|protect", re.I),
        "domain":   re.compile(r"domain|custom", re.I),
        "sites":    re.compile(r"/sites|publish", re.I),
    }

    grouped: dict[str, list[tuple[str, str, str, str]]] = {k: [] for k in keywords}
    for p, methods in paths.items():
        for k, pattern in keywords.items():
            if pattern.search(p):
                for m, op in methods.items():
                    if m.lower() in {"get", "post", "put", "patch", "delete"}:
                        op_id = op.get("operationId", "") if isinstance(op, dict) else ""
                        summary = op.get("summary", "") if isinstance(op, dict) else ""
                        grouped[k].append((m.upper(), p, op_id, summary))

    for cat, ops in grouped.items():
        print(f"--- {cat} ({len(ops)}) ---")
        for m, p, oid, s in ops[:30]:
            print(f"  {m:6s} {p:65s}  {oid}  {s[:80]}")
        if len(ops) > 30:
            print(f"  ... +{len(ops)-30} more")
        print()


def fetch_docs() -> None:
    print("\n=== Doc pages ===")
    for url in DOC_URLS:
        status, body, ctype = fetch(url)
        size = len(body)
        # Strip HTML tags crudely + trim
        text = re.sub(r"<[^>]+>", " ", body.decode("utf-8", "ignore"))
        text = re.sub(r"\s+", " ", text).strip()
        snippet = text[:400]
        print(f"\n[{status}] {url}  ({size} bytes)")
        print(f"  {snippet}")


def main():
    spec = find_openapi()
    if spec:
        summarize_openapi(spec)
    else:
        print("No OpenAPI spec located via candidate URLs.")
    fetch_docs()


if __name__ == "__main__":
    main()
