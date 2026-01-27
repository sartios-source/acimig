#!/usr/bin/env python3
"""ACI APIC Data Collector - REST, icurl, moquery fallbacks."""

import argparse
import getpass
import json
import logging
import os
import ssl
import subprocess
import sys
import time
from datetime import datetime
import http.cookiejar
import urllib.request

DEFAULT_ACI_CLASSES = [
    'fabricNode', 'eqptFex', 'fvAEPg', 'fvBD', 'fvCtx', 'fvTenant', 'fvRsPathAtt',
    'fvSubnet', 'ethpmPhysIf', 'physDomP', 'vzBrCP', 'vzSubj', 'vzFilter', 'vzEntry',
    'vzRsSubjFiltAtt', 'fvRsCons', 'fvRsProv', 'vpcDom', 'pcAggrIf', 'lacpEntity',
    'vpcIf', 'l3extOut', 'l3extInstP', 'l3extLNodeP', 'l3extLIfP',
    'l3extRsNodeL3OutAtt', 'l3extSubnet', 'l3extRsEctx', 'bgpPeerP', 'ospfIfP',
    'ipRouteP', 'fvnsVlanInstP', 'fvnsEncapBlk', 'vmmDomP', 'l3extDomP',
    'infraRsVlanNs', 'vmmRsVlanNs', 'l3extRsVlanNs', 'infraAccPortGrp',
    'infraAccBndlGrp', 'infraAccPortP', 'infraHPortS', 'infraRsDomP',
    'infraAttEntityP', 'lldpAdjEp', 'cdpAdjEp', 'fvRsBd', 'fvRsCtx'
]

try:
    import requests
except Exception:
    requests = None


class APICCollector:
    def __init__(self, apic_host, username, password, output_dir, log_level="INFO"):
        self.apic_host = apic_host
        self.username = username
        self.password = password
        self.output_dir = output_dir
        self.ssl_context = ssl._create_unverified_context()

        os.makedirs(self.output_dir, exist_ok=True)
        self._setup_logging(log_level)

        self.rest_session = None
        self.icurl_token = None

        self.summary = {
            'hostname': apic_host,
            'timestamp': datetime.now().isoformat(),
            'classes_requested': [],
            'classes_collected': [],
            'class_errors': [],
            'methods_used': [],
            'imdata_count': 0,
            'collection_status': 'failed',
            'output_file': ''
        }

    def _setup_logging(self, log_level):
        logging.basicConfig(
            level=getattr(logging, log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(message)s"
        )
        self.logger = logging.getLogger("apic_collector")

    def _escape_single_quotes(self, value):
        return value.replace("'", "'\"'\"'")

    def _clean_apic_json_output(self, text):
        if not text:
            return ""

        lines = text.splitlines()
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Warning: Permanently added"):
                continue
            if stripped.startswith("Last login"):
                continue
            if stripped.startswith("Connection to") and stripped.endswith("closed."):
                continue
            cleaned_lines.append(line)

        cleaned = "\n".join(cleaned_lines).strip()
        start_idx = -1
        for idx, ch in enumerate(cleaned):
            if ch in "{[":
                start_idx = idx
                break
        if start_idx == -1:
            return cleaned
        end_idx = max(cleaned.rfind("}"), cleaned.rfind("]"))
        if end_idx > start_idx:
            cleaned = cleaned[start_idx:end_idx + 1]
        else:
            cleaned = cleaned[start_idx:]
        return cleaned.strip()

    def _rest_login(self):
        apic_url = f"https://{self.apic_host}"
        payload = {
            "aaaUser": {
                "attributes": {
                    "name": self.username,
                    "pwd": self.password
                }
            }
        }

        if requests:
            session = requests.Session()
            session.verify = False
            resp = session.post(f"{apic_url}/api/aaaLogin.json", json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            token = data.get("imdata", [{}])[0].get("aaaLogin", {}).get("attributes", {}).get("token")
            if not token:
                raise ValueError("APIC REST login returned no token")
            self.rest_session = ("requests", session)
            return

        cookie_jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{apic_url}/api/aaaLogin.json",
            data=body,
            headers={"Content-Type": "application/json"}
        )
        with opener.open(req, timeout=30, context=self.ssl_context) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        token = data.get("imdata", [{}])[0].get("aaaLogin", {}).get("attributes", {}).get("token")
        if not token:
            raise ValueError("APIC REST login returned no token")
        self.rest_session = ("urllib", opener)

    def _rest_get_class(self, class_name):
        if not self.rest_session:
            return None
        mode, session = self.rest_session
        url = f"https://{self.apic_host}/api/node/class/{class_name}.json"
        if mode == "requests":
            resp = session.get(url, timeout=60)
            resp.raise_for_status()
            return resp.text
        with session.open(url, timeout=60, context=self.ssl_context) as resp:
            return resp.read().decode("utf-8")

    def _ssh_command(self, command, timeout=120):
        ssh_cmd = [
            'ssh',
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'LogLevel=ERROR',
            f'{self.username}@{self.apic_host}',
            'bash', '-lc', command
        ]
        env = os.environ.copy()
        if self.password:
            ssh_cmd = ['sshpass', '-p', self.password] + ssh_cmd
        result = subprocess.run(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout
        raise RuntimeError(result.stderr.strip() or "SSH command failed")

    def _icurl_login(self):
        safe_user = self._escape_single_quotes(self.username)
        safe_pass = self._escape_single_quotes(self.password)
        payload = f'{{"aaaUser":{{"attributes":{{"name":"{safe_user}","pwd":"{safe_pass}"}}}}}}'
        cmd = f"icurl -k -s -X POST https://127.0.0.1/api/aaaLogin.json -d '{payload}'"
        output = self._ssh_command(cmd, timeout=60)
        data = json.loads(self._clean_apic_json_output(output))
        token = data.get("imdata", [{}])[0].get("aaaLogin", {}).get("attributes", {}).get("token")
        if not token:
            raise ValueError("APIC icurl login returned no token")
        self.icurl_token = token

    def _icurl_get_class(self, class_name):
        if not self.icurl_token:
            return None
        cmd = (
            "icurl -k -s "
            f"-H \"Cookie: APIC-cookie={self.icurl_token}\" "
            f"https://127.0.0.1/api/node/class/{class_name}.json"
        )
        return self._ssh_command(cmd, timeout=60)

    def _moquery_get_class(self, class_name):
        cmd = f"moquery -c {class_name} -o json"
        return self._ssh_command(cmd, timeout=120)

    def collect(self, classes):
        self.summary['classes_requested'] = classes

        # REST login
        try:
            self._rest_login()
            self.logger.info("REST login successful")
        except Exception as exc:
            self.logger.warning("REST login failed: %s", exc)

        # icurl login
        try:
            self._icurl_login()
            self.logger.info("icurl login successful")
        except Exception as exc:
            self.logger.warning("icurl login failed: %s", exc)

        imdata = []
        for class_name in classes:
            output = None
            method = None

            if self.rest_session:
                try:
                    output = self._rest_get_class(class_name)
                    method = "rest"
                except Exception as exc:
                    self.logger.warning("REST fetch failed for %s: %s", class_name, exc)
                    output = None

            if not output and self.icurl_token:
                try:
                    output = self._icurl_get_class(class_name)
                    method = "icurl"
                except Exception as exc:
                    self.logger.warning("icurl fetch failed for %s: %s", class_name, exc)
                    output = None

            if not output:
                try:
                    output = self._moquery_get_class(class_name)
                    method = "moquery"
                except Exception as exc:
                    self.logger.warning("moquery fetch failed for %s: %s", class_name, exc)
                    output = None

            if not output:
                self.summary['class_errors'].append(f"{class_name}: empty output")
                continue

            try:
                cleaned = self._clean_apic_json_output(output)
                data = json.loads(cleaned)
                class_imdata = data.get('imdata', [])
                if not class_imdata:
                    self.summary['class_errors'].append(f"{class_name}: no imdata found")
                    continue
                imdata.extend(class_imdata)
                self.summary['classes_collected'].append(class_name)
                if method and method not in self.summary['methods_used']:
                    self.summary['methods_used'].append(method)
            except Exception as exc:
                self.summary['class_errors'].append(f"{class_name}: {exc}")

        if imdata:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(self.output_dir, f"apic_{self.apic_host}_{timestamp}.json")
            with open(output_path, 'w', encoding='utf-8') as handle:
                json.dump({"imdata": imdata}, handle, indent=2)
            self.summary['imdata_count'] = len(imdata)
            self.summary['output_file'] = output_path
            self.summary['collection_status'] = 'success'
        else:
            self.summary['collection_status'] = 'failed'

        summary_path = os.path.join(self.output_dir, f"apic_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(summary_path, 'w', encoding='utf-8') as handle:
            json.dump(self.summary, handle, indent=2)

        return self.summary


def parse_args():
    parser = argparse.ArgumentParser(description="ACI-only APIC data collector")
    parser.add_argument("--apic-host", help="APIC hostname or IP (prompted if not set)")
    parser.add_argument("--apic-username", help="APIC username (prompted if not set)")
    parser.add_argument("--output-dir", default="network_data", help="Output directory")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    parser.add_argument("--aci-classes", help="Comma-separated ACI classes to collect (defaults to full set)")
    return parser.parse_args()


def main():
    args = parse_args()
    apic_host = args.apic_host or input("APIC hostname or IP: ").strip()
    if not apic_host:
        print("No APIC hostname provided.")
        return 1
    apic_username = args.apic_username or input("APIC username: ").strip()
    if not apic_username:
        print("No APIC username provided.")
        return 1
    apic_password = getpass.getpass("APIC password: ")

    if args.aci_classes:
        classes = [c.strip() for c in args.aci_classes.split(',') if c.strip()]
    else:
        classes = DEFAULT_ACI_CLASSES

    collector = APICCollector(
        apic_host=apic_host,
        username=apic_username,
        password=apic_password,
        output_dir=args.output_dir,
        log_level=args.log_level
    )

    summary = collector.collect(classes)
    status = summary.get('collection_status', 'failed')
    print(f"APIC collection status: {status}")
    print(f"Classes collected: {len(summary.get('classes_collected', []))}/{len(classes)}")
    print(f"Output: {summary.get('output_file', '')}")
    if summary.get('class_errors'):
        print(f"Errors: {len(summary.get('class_errors'))} (see summary JSON)")
    return 0 if status == 'success' else 1


if __name__ == "__main__":
    raise SystemExit(main())
