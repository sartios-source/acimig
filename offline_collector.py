#!/usr/bin/env python3
"""ACI Offline Data Collector"""
import argparse
import getpass
import json
import sys
import time
from typing import Dict, List

import requests

DEFAULT_CLASSES = [
    "fabricNode",
    "eqptFex",
    "fvAEPg",
    "fvBD",
    "fvCtx",
    "fvTenant",
    "vzBrCP",
    "fvRsPathAtt",
    "fvSubnet",
    "ethpmPhysIf",
    "physDomP",
]


def normalize_apic_url(apic: str) -> str:
    if apic.startswith("http://") or apic.startswith("https://"):
        return apic.rstrip("/")
    return f"https://{apic.rstrip('/')}"


def apic_login(session: requests.Session, base_url: str, username: str, password: str, verify: bool,
               timeout: int) -> None:
    url = f"{base_url}/api/aaaLogin.json"
    payload = {"aaaUser": {"attributes": {"name": username, "pwd": password}}}
    response = session.post(url, json=payload, verify=verify, timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(f"Login failed: HTTP {response.status_code} - {response.text}")


def fetch_class(session: requests.Session, base_url: str, class_name: str, page_size: int,
                verify: bool, timeout: int, retries: int, sleep_seconds: float) -> List[Dict[str, Dict]]:
    url = f"{base_url}/api/node/class/{class_name}.json"
    imdata: List[Dict[str, Dict]] = []
    page = 0

    while True:
        params = {"page-size": page_size, "page": page}
        last_error = None
        for attempt in range(retries + 1):
            try:
                response = session.get(url, params=params, verify=verify, timeout=timeout)
                if response.status_code != 200:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
                payload = response.json()
                items = payload.get("imdata", [])
                imdata.extend(items)

                total_count = payload.get("totalCount")
                if total_count is not None and isinstance(total_count, str) and total_count.isdigit():
                    total = int(total_count)
                    if len(imdata) >= total:
                        return imdata

                if len(items) < page_size:
                    return imdata

                page += 1
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
                break
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(1.0)
                    continue
                raise RuntimeError(f"Failed to fetch {class_name}: {last_error}") from last_error


def build_output(imdata: List[Dict[str, Dict]]) -> Dict[str, List[Dict[str, Dict]]]:
    return {"imdata": imdata}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect ACI data from APIC for offline analysis")
    parser.add_argument("--apic", required=True, help="APIC hostname or URL")
    parser.add_argument("--username", required=True, help="APIC username")
    parser.add_argument("--password", help="APIC password (prompted if omitted)")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--classes", help="Comma-separated APIC classes to collect")
    parser.add_argument("--page-size", type=int, default=500, help="APIC page size")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout seconds")
    parser.add_argument("--retries", type=int, default=2, help="Retry count per request")
    parser.add_argument("--sleep", type=float, default=0.0, help="Sleep between pages")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = args.password or getpass.getpass("APIC Password: ")
    base_url = normalize_apic_url(args.apic)
    classes = DEFAULT_CLASSES
    if args.classes:
        classes = [c.strip() for c in args.classes.split(",") if c.strip()]

    session = requests.Session()
    if args.insecure:
        requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]

    print(f"Connecting to {base_url}...")
    apic_login(session, base_url, args.username, password, not args.insecure, args.timeout)
    print("Login successful. Collecting data...")

    all_imdata: List[Dict[str, Dict]] = []
    for class_name in classes:
        print(f"Collecting {class_name}...")
        class_data = fetch_class(
            session=session,
            base_url=base_url,
            class_name=class_name,
            page_size=args.page_size,
            verify=not args.insecure,
            timeout=args.timeout,
            retries=args.retries,
            sleep_seconds=args.sleep,
        )
        all_imdata.extend(class_data)
        print(f"  {class_name}: {len(class_data)} objects")

    output = build_output(all_imdata)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)

    print(f"Wrote {len(all_imdata)} objects to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
