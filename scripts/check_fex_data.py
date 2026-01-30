#!/usr/bin/env python3
"""FEX data verification script.

Usage:
  python scripts/check_fex_data.py --base-url http://127.0.0.1:5001 --fabric glo_c_ground
"""

import argparse
import json
import sys
from urllib.parse import urljoin
from urllib.request import Request, build_opener
from http.cookiejar import CookieJar


def _request_json(opener, method, url, payload=None):
    data = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
        data = body
    req = Request(url, data=data, headers=headers, method=method)
    with opener.open(req) as resp:
        raw = resp.read().decode('utf-8')
        return resp.status, raw, json.loads(raw) if raw else None


def main():
    parser = argparse.ArgumentParser(description='Verify FEX data pipeline + UI endpoints.')
    parser.add_argument('--base-url', required=True, help='Base URL, e.g. http://127.0.0.1:5001')
    parser.add_argument('--fabric', required=True, help='Fabric name to select')
    parser.add_argument('--size', type=int, default=25, help='Page size for BI endpoints')
    args = parser.parse_args()

    jar = CookieJar()
    from urllib.request import HTTPCookieProcessor
    opener = build_opener(HTTPCookieProcessor(jar))
    opener.addheaders = [('User-Agent', 'fex-check/1.0')]

    base = args.base_url.rstrip('/') + '/'

    # Select fabric
    select_url = urljoin(base, f'fabrics/{args.fabric}/select')
    status, _, payload = _request_json(opener, 'POST', select_url)
    if status >= 400:
        print(f"Select fabric failed ({status}): {payload}")
        sys.exit(1)
    print(f"Selected fabric: {payload.get('fabric')}")

    # Health
    health_url = urljoin(base, 'api/health/fabric')
    status, _, health = _request_json(opener, 'GET', health_url)
    print(f"Health ({status}): ok={health.get('ok')} active_fabric={health.get('active_fabric')}")
    if not health.get('ok'):
        print(json.dumps(health, indent=2))
        sys.exit(1)

    # FEX devices
    fex_devices_url = urljoin(base, f'api/bi/fex_devices?page=1&size={args.size}')
    status, _, fex_devices = _request_json(opener, 'GET', fex_devices_url)
    print(f"FEX devices ({status}): rows={len(fex_devices.get('rows', []))} total={fex_devices.get('total')}")

    # FEX racks
    fex_racks_url = urljoin(base, f'api/bi/fex_racks?page=1&size={args.size}')
    status, _, fex_racks = _request_json(opener, 'GET', fex_racks_url)
    print(f"FEX racks ({status}): rows={len(fex_racks.get('rows', []))} total={fex_racks.get('total')}")

    # Match debug
    debug_url = urljoin(base, 'api/debug/fex-match')
    status, _, debug = _request_json(opener, 'GET', debug_url)
    print(f"Debug match ({status}): fex_total={debug.get('fex_total_objects')} fex_ids={debug.get('fex_count')} match_rate={debug.get('match_rate')}")

    print("\nDone.")


if __name__ == '__main__':
    main()
