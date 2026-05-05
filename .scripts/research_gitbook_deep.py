"""Deep dive into GitBook OpenAPI for the four specific questions."""
from __future__ import annotations
import json
import re
import sys
from urllib import request

SPEC_URL = "https://api.gitbook.com/openapi.json"

def fetch_spec() -> dict:
    with request.urlopen(SPEC_URL, timeout=30) as r:
        return json.loads(r.read().decode())


def resolve(spec: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        return {}
    cur = spec
    for part in ref[2:].split("/"):
        cur = cur.get(part, {})
    return cur


def schema_keys(spec: dict, schema: dict, depth: int = 0, max_depth: int = 4) -> list[str]:
    if depth > max_depth:
        return ["..."]
    if "$ref" in schema:
        return schema_keys(spec, resolve(spec, schema["$ref"]), depth, max_depth)
    if "oneOf" in schema or "anyOf" in schema:
        out = []
        for s in schema.get("oneOf", []) + schema.get("anyOf", []):
            out.append("|".join(schema_keys(spec, s, depth + 1, max_depth)))
        return [" OR ".join(out)]
    if schema.get("type") == "object" or "properties" in schema:
        return list(schema.get("properties", {}).keys())
    if schema.get("type") == "array":
        return [f"array<{','.join(schema_keys(spec, schema.get('items', {}), depth + 1, max_depth))}>"]
    return [schema.get("type", "unknown")]


def request_body_summary(spec: dict, op: dict) -> str:
    rb = op.get("requestBody", {})
    if not rb:
        return "(no body)"
    content = rb.get("content", {})
    for mt, mt_obj in content.items():
        sch = mt_obj.get("schema", {})
        if "$ref" in sch:
            sch = resolve(spec, sch["$ref"])
        # Look at properties + required
        if "$ref" in sch:
            sch = resolve(spec, sch["$ref"])
        if "oneOf" in sch:
            parts = []
            for variant in sch["oneOf"]:
                v = resolve(spec, variant["$ref"]) if "$ref" in variant else variant
                req = v.get("required", [])
                props = list(v.get("properties", {}).keys())
                parts.append(f"{{required={req}, props={props}}}")
            return f"{mt}: oneOf[{' | '.join(parts)}]"
        if "properties" in sch or sch.get("type") == "object":
            req = sch.get("required", [])
            props = sch.get("properties", {})
            prop_summary = {k: v.get("type", v.get("$ref", "?").split("/")[-1]) for k, v in props.items()}
            return f"{mt}: required={req}, props={prop_summary}"
        return f"{mt}: {sch}"
    return "(no body)"


def find_op(spec: dict, method: str, path: str):
    paths = spec.get("paths", {})
    p = paths.get(path)
    if not p:
        return None
    return p.get(method.lower())


def search_paths(spec: dict, regex: str) -> list[tuple[str, str, str]]:
    pat = re.compile(regex, re.I)
    out = []
    for p, methods in spec.get("paths", {}).items():
        if pat.search(p):
            for m, op in methods.items():
                if isinstance(op, dict) and op.get("operationId"):
                    out.append((m.upper(), p, op.get("operationId", "")))
    return out


def section(title: str):
    print(f"\n{'='*80}\n{title}\n{'='*80}")


def main():
    spec = fetch_spec()
    paths = spec.get("paths", {})

    # ---- Q1: Create new space -----------------------------------------------
    section("Q1: SPACE CREATION")
    space_create_candidates = []
    for p, methods in paths.items():
        if methods.get("post") and ("space" in p.lower()):
            op = methods["post"]
            space_create_candidates.append((p, op.get("operationId"), op.get("summary")))
    for p, oid, s in space_create_candidates:
        print(f"  POST {p}  ({oid})  {s}")
    # Specifically look for orgs/{orgId}/spaces or top-level POST /spaces
    print("\nSpecific probes:")
    for path in ["/spaces", "/orgs/{organizationId}/spaces", "/collections/{collectionId}/spaces"]:
        if path in paths:
            for m in ["post", "get", "patch"]:
                if m in paths[path]:
                    op = paths[path][m]
                    print(f"  {m.upper()} {path}  ({op.get('operationId')})  {op.get('summary')}")
                    if m == "post":
                        print(f"    body: {request_body_summary(spec, op)}")
        else:
            print(f"  NOT FOUND: {path}")

    # Check duplicate as creation alternative
    op = find_op(spec, "post", "/spaces/{spaceId}/duplicate")
    if op:
        print(f"\n  POST /spaces/{{spaceId}}/duplicate body:")
        print(f"    {request_body_summary(spec, op)}")

    # ---- Q2: GitHub sync setup ----------------------------------------------
    section("Q2: GITHUB REPO -> SPACE SYNC")
    # The integration approach
    op = find_op(spec, "post", "/integrations/{integrationName}/installations/{installationId}/spaces")
    if op:
        print(f"POST /integrations/{{name}}/installations/{{id}}/spaces  ({op.get('operationId')})")
        print(f"  body: {request_body_summary(spec, op)}")
    # The git import approach
    op = find_op(spec, "post", "/spaces/{spaceId}/git/import")
    if op:
        print(f"\nPOST /spaces/{{spaceId}}/git/import  ({op.get('operationId')})  {op.get('summary')}")
        print(f"  body: {request_body_summary(spec, op)}")
    op = find_op(spec, "post", "/spaces/{spaceId}/git/export")
    if op:
        print(f"\nPOST /spaces/{{spaceId}}/git/export  ({op.get('operationId')})  {op.get('summary')}")
        print(f"  body: {request_body_summary(spec, op)}")
    op = find_op(spec, "get", "/spaces/{spaceId}/git/info")
    if op:
        print(f"\nGET /spaces/{{spaceId}}/git/info  ({op.get('operationId')})  {op.get('summary')}")
        # Show response schema
        for mt, mt_obj in op.get("responses", {}).get("200", {}).get("content", {}).items():
            sch = mt_obj.get("schema", {})
            if "$ref" in sch:
                sch = resolve(spec, sch["$ref"])
            print(f"  response.{mt}: props={list(sch.get('properties', {}).keys())}")

    # ---- Q3: Password / auth on space or pages ------------------------------
    section("Q3: PASSWORD PROTECTION / VISITOR AUTH")
    # site publishing auth
    op = find_op(spec, "patch", "/orgs/{organizationId}/sites/{siteId}/publishing/auth")
    if op:
        print(f"PATCH .../publishing/auth  ({op.get('operationId')})  {op.get('summary')}")
        print(f"  body: {request_body_summary(spec, op)}")
        for mt, mt_obj in op.get("requestBody", {}).get("content", {}).items():
            sch = mt_obj.get("schema", {})
            if "$ref" in sch:
                sch = resolve(spec, sch["$ref"])
            # walk nested
            print(f"  full request schema name: {mt_obj.get('schema', {}).get('$ref')}")
            print(f"  required={sch.get('required')}, props={list(sch.get('properties', {}).keys())}")
            for pname, pdef in (sch.get("properties") or {}).items():
                if "$ref" in pdef:
                    sub = resolve(spec, pdef["$ref"])
                    print(f"    {pname}: ref={pdef['$ref'].split('/')[-1]}, props={list(sub.get('properties', {}).keys())}, required={sub.get('required')}, oneOf={'oneOf' in sub}")
                elif pdef.get("oneOf"):
                    variants = []
                    for v in pdef["oneOf"]:
                        if "$ref" in v:
                            sub = resolve(spec, v["$ref"])
                            variants.append(f"{v['$ref'].split('/')[-1]}(props={list(sub.get('properties', {}).keys())}, required={sub.get('required')})")
                        else:
                            variants.append(str(v)[:80])
                    print(f"    {pname}: oneOf=[{' | '.join(variants)}]")
                else:
                    print(f"    {pname}: {pdef}")

    op = find_op(spec, "get", "/orgs/{organizationId}/sites/{siteId}/publishing/auth")
    if op:
        print(f"\nGET .../publishing/auth  ({op.get('operationId')})  {op.get('summary')}")
        for mt, mt_obj in op.get("responses", {}).get("200", {}).get("content", {}).items():
            sch = mt_obj.get("schema", {})
            if "$ref" in sch:
                sch = resolve(spec, sch["$ref"])
            print(f"  response props: {list(sch.get('properties', {}).keys())}")

    # share links — short-lived token-gated access alternative
    op = find_op(spec, "post", "/orgs/{organizationId}/sites/{siteId}/share-links")
    if op:
        print(f"\nPOST .../share-links  ({op.get('operationId')})  {op.get('summary')}")
        print(f"  body: {request_body_summary(spec, op)}")

    # site space visibility / access (per-page-tier control)
    site_space_paths = search_paths(spec, r"site-spaces|site-sections|adaptive")
    print(f"\nsite-space / site-section / adaptive endpoints ({len(site_space_paths)}):")
    for m, p, oid in site_space_paths[:30]:
        print(f"  {m:6s} {p:75s}  {oid}")

    # ---- Q4: Custom domain --------------------------------------------------
    section("Q4: CUSTOM DOMAIN")
    domain_paths = search_paths(spec, r"domain|hostname|subdomain")
    for m, p, oid in domain_paths:
        op = paths[p][m.lower()]
        print(f"\n{m} {p}  ({oid})")
        print(f"  summary: {op.get('summary')}")
        if m in ("POST", "PUT", "PATCH"):
            print(f"  body: {request_body_summary(spec, op)}")
        for mt, mt_obj in op.get("responses", {}).get("200", {}).get("content", {}).items():
            sch = mt_obj.get("schema", {})
            if "$ref" in sch:
                sch = resolve(spec, sch["$ref"])
            print(f"  response.{mt}: props={list(sch.get('properties', {}).keys())[:10]}")

    # Look at customization (where domain might also live)
    op = find_op(spec, "put", "/orgs/{organizationId}/sites/{siteId}/customization")
    if op:
        print(f"\nPUT /orgs/.../sites/{{siteId}}/customization  ({op.get('operationId')})")
        print(f"  body: {request_body_summary(spec, op)}")

    op = find_op(spec, "patch", "/orgs/{organizationId}/sites/{siteId}")
    if op:
        print(f"\nPATCH /orgs/.../sites/{{siteId}}  ({op.get('operationId')})")
        print(f"  body: {request_body_summary(spec, op)}")
        for mt, mt_obj in op.get("requestBody", {}).get("content", {}).items():
            sch = mt_obj.get("schema", {})
            if "$ref" in sch:
                sch = resolve(spec, sch["$ref"])
            print(f"  props: {list(sch.get('properties', {}).keys())}")

    # ---- Site creation (for context with auth + domain) ---------------------
    section("BONUS: SITE CREATION + STRUCTURE")
    op = find_op(spec, "post", "/orgs/{organizationId}/sites")
    if op:
        print(f"POST /orgs/{{organizationId}}/sites  ({op.get('operationId')})")
        print(f"  body: {request_body_summary(spec, op)}")
        for mt, mt_obj in op.get("requestBody", {}).get("content", {}).items():
            sch = mt_obj.get("schema", {})
            if "$ref" in sch:
                sch = resolve(spec, sch["$ref"])
            print(f"  props: {list(sch.get('properties', {}).keys())}, required={sch.get('required')}")

    # site spaces (where spaces are bound to a site)
    op = find_op(spec, "post", "/orgs/{organizationId}/sites/{siteId}/site-spaces")
    if op:
        print(f"\nPOST .../site-spaces  ({op.get('operationId')})")
        print(f"  body: {request_body_summary(spec, op)}")
    # search broader
    for m, p, oid in search_paths(spec, r"/orgs/.*/sites/[^/]+/site-spaces"):
        print(f"  {m:6s} {p:75s}  {oid}")


if __name__ == "__main__":
    main()
