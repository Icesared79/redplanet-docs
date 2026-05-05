"""Inspect specific schemas: visitor auth variants, site customization, hostname creation flow."""
from __future__ import annotations
import json
from urllib import request

with request.urlopen("https://api.gitbook.com/openapi.json", timeout=30) as r:
    spec = json.loads(r.read().decode())

components = spec["components"]["schemas"]

def show(name: str):
    s = components.get(name)
    if not s:
        print(f"!! {name} not in components.schemas")
        return
    print(f"\n--- {name} ---")
    print(json.dumps(s, indent=2)[:4000])

for n in [
    "VisitorAuthCustomBackend",
    "VisitorAuthIntegrationBackend",
    "SitePublishingAuth",
    "SitePublishingAuthUpdate",
    "SiteVisibility",
    "SiteCustomizationSettingsBase",
    "SiteCustomization",
    "SiteCustomizationSettings",
    "CustomHostname",
    "CustomHostnameStatus",
    "Site",
    "SitePermissionsModel",
    "SiteShareLink",
    "ShareLinkName",
    "DefaultLevel",
    "SiteSpace",
    "SiteSection",
    "Visibility",
]:
    show(n)

# Also list any schema with "auth", "password", "hostname", "domain" in the name
print("\n\n--- schema names matching auth|password|hostname|domain|visitor ---")
import re
for n in components.keys():
    if re.search(r"auth|password|hostname|domain|visitor|publish", n, re.I):
        print(f"  {n}")

# Find any path that creates a custom hostname
print("\n\n--- paths mentioning hostname / domain in request body ---")
for p, methods in spec["paths"].items():
    for m, op in methods.items():
        if not isinstance(op, dict):
            continue
        body = json.dumps(op.get("requestBody", {}))
        if "ostname" in body or "domain" in body.lower() or "ostname" in p:
            print(f"  {m.upper()} {p}  ({op.get('operationId')})")

# Inspect addSpaceToSite, updateSiteSpaceById to see if auth can be set per-section
print("\n\n--- addSpaceToSite & updateSiteSpaceById full schemas ---")
for path, method in [
    ("/orgs/{organizationId}/sites/{siteId}/site-spaces", "post"),
    ("/orgs/{organizationId}/sites/{siteId}/site-spaces/{siteSpaceId}", "patch"),
    ("/orgs/{organizationId}/sites/{siteId}/site-spaces/{siteSpaceId}/customization", "patch"),
]:
    op = spec["paths"].get(path, {}).get(method)
    if not op:
        continue
    print(f"\n{method.upper()} {path}  ({op.get('operationId')})")
    print(f"summary: {op.get('summary')}")
    rb = op.get("requestBody", {})
    print(json.dumps(rb, indent=2)[:2500])

# Look at sections (where private/public split lives in site structure)
print("\n\n--- sections endpoints ---")
for p, methods in spec["paths"].items():
    if "section" in p:
        for m, op in methods.items():
            if isinstance(op, dict) and op.get("operationId"):
                print(f"  {m.upper():6s} {p:75s}  {op.get('operationId')}  {op.get('summary','')[:60]}")
