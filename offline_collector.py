#!/usr/bin/env python3
"""Network Data Collector - SSH-based device inventory and interface collection."""

# SECTION: imports
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import threading
import time
import getpass
import logging
from datetime import datetime

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


class NetworkDataCollector:
    """SSH-based data collector."""

    # SECTION: init
    def __init__(self, hosts_file="hosts.txt", output_dir="network_data", log_level="INFO",
                 default_username=None, threads=4, use_password=True):
        self.hosts_file = hosts_file
        self.output_dir = output_dir
        self.default_username = default_username
        self.threads = max(1, threads)
        self.use_password = use_password

        self.collected_data = []
        self.password_cache = {}
        self.connection_failures = []
        self.command_failures = []
        self.missing_data = []
        self.lock = threading.Lock()

        os.makedirs(output_dir, exist_ok=True)
        self.setup_logging(log_level)

        self.error_categories = {
            'CONNECTION_TIMEOUT': 'SSH connection timeout',
            'AUTH_FAILURE': 'Authentication failed',
            'PERMISSION_DENIED': 'Permission denied',
            'HOST_UNREACHABLE': 'Host unreachable',
            'COMMAND_TIMEOUT': 'Command execution timeout',
            'COMMAND_ERROR': 'Command returned error',
            'PARSING_ERROR': 'Data parsing failed',
            'UNKNOWN_PLATFORM': 'Platform detection failed',
            'MISSING_SSHPASS': 'sshpass not installed',
            'INVALID_COMMAND': 'Invalid command for platform'
        }

        self.platform_commands = {
            'arista_eos': {
                'version': 'show version',
                'interfaces': 'show interfaces status',
                'neighbors': 'show lldp neighbors',
                'paging_disable': 'terminal length 0',
                'timeouts': {
                    'version': 30,
                    'interfaces': 45,
                    'neighbors': 30,
                    'paging_disable': 10
                }
            },
            'cisco_ios': {
                'version': 'show version',
                'interfaces': 'show interface status',
                'neighbors': 'show cdp neighbors',
                'paging_disable': 'terminal length 0',
                'timeouts': {
                    'version': 30,
                    'interfaces': 60,
                    'neighbors': 30,
                    'paging_disable': 10
                }
            },
            'cisco_nxos': {
                'version': 'show version',
                'interfaces': 'show interface status',
                'neighbors': 'show cdp neighbors',
                'paging_disable': 'terminal length 0',
                'timeouts': {
                    'version': 30,
                    'interfaces': 45,
                    'neighbors': 30,
                    'paging_disable': 10
                }
            },
            'cisco_catos': {
                'version': 'show version',
                'interfaces': 'show port',
                'neighbors': 'show cdp neighbors',
                'paging_disable': 'set length 0',
                'timeouts': {
                    'version': 30,
                    'interfaces': 90,
                    'neighbors': 45,
                    'paging_disable': 10
                }
            }
        }

    # SECTION: logging and errors
    def setup_logging(self, log_level):
        log_dir = os.path.join(self.output_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

        logging.basicConfig(
            level=getattr(logging, log_level.upper(), logging.INFO),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )

        self.logger = logging.getLogger(__name__)
        self.logger.info("Starting network data collection session")
        self.logger.info("Log file: %s", log_file)

    def log_error(self, hostname, error_category, error_message, command=None):
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'hostname': hostname,
            'category': error_category,
            'message': error_message,
            'command': command,
            'description': self.error_categories.get(error_category, 'Unknown error')
        }

        if error_category in ['CONNECTION_TIMEOUT', 'AUTH_FAILURE', 'HOST_UNREACHABLE', 'PERMISSION_DENIED']:
            self.connection_failures.append(error_entry)
            self.logger.error("CONNECTION FAILURE - %s: %s - %s", hostname, error_category, error_message)
        elif error_category in ['COMMAND_TIMEOUT', 'COMMAND_ERROR', 'INVALID_COMMAND']:
            self.command_failures.append(error_entry)
            self.logger.error("COMMAND FAILURE - %s: %s [%s] - %s",
                              hostname, error_category, command, error_message)
        else:
            self.logger.error("ERROR - %s: %s - %s", hostname, error_category, error_message)

    def log_missing_data(self, hostname, missing_type, details):
        missing_entry = {
            'timestamp': datetime.now().isoformat(),
            'hostname': hostname,
            'missing_type': missing_type,
            'details': details
        }

        self.missing_data.append(missing_entry)
        self.logger.warning("MISSING DATA - %s: %s - %s", hostname, missing_type, details)

    # SECTION: password handling
    def get_password(self, username, hostname):
        cache_key = f"{username}@{hostname}"
        if cache_key in self.password_cache:
            return self.password_cache[cache_key]

        global_key = f"global_{username}"
        if global_key in self.password_cache:
            return self.password_cache[global_key]

        prompt = f"Password for {username}@{hostname}: "
        try:
            password = getpass.getpass(prompt)
        except KeyboardInterrupt:
            self.logger.info("Password input cancelled by user")
            raise
        except Exception as exc:
            self.log_error(hostname, 'AUTH_FAILURE', f"Failed to get password: {exc}")
            raise

        hosts_with_same_user = [h for h in self.load_hosts() if h[1] == username]
        if len(hosts_with_same_user) > 1:
            try:
                use_global = input(f"Use this password for all '{username}' connections? (y/N): ").lower() == 'y'
                if use_global:
                    self.password_cache[global_key] = password
                    self.logger.info("Password cached globally for user: %s", username)
                else:
                    self.password_cache[cache_key] = password
                    self.logger.info("Password cached for: %s", cache_key)
            except KeyboardInterrupt:
                self.password_cache[cache_key] = password
        else:
            self.password_cache[cache_key] = password

        return password

    # SECTION: platform detection
    def detect_platform_from_version(self, version_output, hostname):
        if not version_output:
            self.log_error(hostname, 'UNKNOWN_PLATFORM', 'Empty show version output')
            return {
                'vendor': 'unknown',
                'os': 'unknown',
                'model': 'unknown',
                'platform_type': 'cisco_ios',
                'commands': self.platform_commands['cisco_ios']
            }

        text = version_output.lower()
        platform = {
            'vendor': 'unknown',
            'os': 'unknown',
            'model': 'unknown',
            'platform_type': 'cisco_ios',
            'commands': self.platform_commands['cisco_ios']
        }

        try:
            if 'arista' in text or 'eos' in text:
                platform['vendor'] = 'Arista'
                platform['os'] = 'EOS'
                platform['platform_type'] = 'arista_eos'
                platform['commands'] = self.platform_commands['arista_eos']

                if 'dcs-7050' in text:
                    platform['model'] = 'DCS-7050'
                elif 'dcs-7280' in text:
                    platform['model'] = 'DCS-7280'
                elif 'dcs-7150' in text:
                    platform['model'] = 'DCS-7150'
                elif 'dcs-' in text:
                    match = re.search(r'dcs-(\\w+)', text)
                    platform['model'] = f"DCS-{match.group(1).upper()}" if match else 'DCS Series'

            elif 'catalyst operating system' in text or 'ws-c61' in text:
                platform['vendor'] = 'Cisco'
                platform['os'] = 'CatOS'
                platform['platform_type'] = 'cisco_catos'
                platform['commands'] = self.platform_commands['cisco_catos']

                if 'ws-c6100' in text:
                    platform['model'] = 'Catalyst 6100'
                elif 'ws-c61' in text:
                    platform['model'] = 'Catalyst 6100 Series'

            elif 'nexus' in text or 'nx-os' in text:
                platform['vendor'] = 'Cisco'
                platform['os'] = 'NX-OS'
                platform['platform_type'] = 'cisco_nxos'
                platform['commands'] = self.platform_commands['cisco_nxos']

                if 'nexus9000' in text or 'n9k' in text:
                    platform['model'] = 'Nexus 9000'
                elif 'nexus7000' in text or 'n7k' in text:
                    platform['model'] = 'Nexus 7000'
                elif 'nexus5000' in text or 'n5k' in text:
                    platform['model'] = 'Nexus 5000'
                elif 'nexus3000' in text or 'n3k' in text:
                    platform['model'] = 'Nexus 3000'

            elif 'cisco ios' in text or 'ios software' in text:
                platform['vendor'] = 'Cisco'
                platform['os'] = 'IOS'
                platform['platform_type'] = 'cisco_ios'
                platform['commands'] = self.platform_commands['cisco_ios']

                if 'ws-c6506' in text or '6506' in text:
                    platform['model'] = 'Catalyst 6506'
                elif 'ws-c6509' in text or '6509' in text:
                    platform['model'] = 'Catalyst 6509'
                elif 'ws-c6500' in text:
                    platform['model'] = 'Catalyst 6500 Series'
                elif 'ws-c3750' in text:
                    platform['model'] = 'Catalyst 3750'
                elif 'ws-c3560' in text:
                    platform['model'] = 'Catalyst 3560'
                elif 'ws-c2960' in text:
                    platform['model'] = 'Catalyst 2960'
                elif 'asr1000' in text:
                    platform['model'] = 'ASR 1000'
                elif 'isr4' in text:
                    platform['model'] = 'ISR 4000'
                elif 'ws-c' in text:
                    match = re.search(r'ws-c(\\d+)', text)
                    platform['model'] = f"Catalyst {match.group(1)}" if match else 'Catalyst Series'
            else:
                self.log_error(hostname, 'UNKNOWN_PLATFORM', 'Could not identify platform from show version output')

            self.logger.info("Platform detected for %s: %s %s %s",
                             hostname, platform['vendor'], platform['os'], platform['model'])

        except Exception as exc:
            self.log_error(hostname, 'PARSING_ERROR', f"Error parsing show version: {exc}")

        return platform

    # SECTION: SSH helpers
    def ssh_command_with_retry(self, hostname, username, password, command, timeout=30, max_retries=2):
        for attempt in range(max_retries + 1):
            if attempt > 0:
                self.logger.info("Retry attempt %s for command '%s' on %s", attempt, command, hostname)
                time.sleep(2)

            result = self.ssh_command(hostname, username, password, command, timeout, attempt)

            if result is not None:
                return result
            if attempt < max_retries:
                self.logger.warning("Command failed, will retry: %s on %s", command, hostname)

        self.log_error(hostname, 'COMMAND_TIMEOUT',
                       f"Command failed after {max_retries} retries: {command}", command)
        return None

    def ssh_command_interactive(self, hostname, username, password, command, timeout=30, attempt=0):
        try:
            self.logger.debug("Executing interactive command on %s: %s (timeout: %ss, attempt: %s)",
                              hostname, command, timeout, attempt)

            if password:
                ssh_cmd = [
                    'sshpass', '-p', password,
                    'ssh',
                    '-o', 'ConnectTimeout=10',
                    '-o', 'StrictHostKeyChecking=no',
                    '-o', 'UserKnownHostsFile=/dev/null',
                    '-o', 'LogLevel=ERROR',
                    '-t',
                    f'{username}@{hostname}',
                    command
                ]
            else:
                ssh_cmd = [
                    'ssh',
                    '-o', 'ConnectTimeout=10',
                    '-o', 'StrictHostKeyChecking=no',
                    '-o', 'UserKnownHostsFile=/dev/null',
                    '-o', 'LogLevel=ERROR',
                    '-t',
                    f'{username}@{hostname}',
                    command
                ]

            process = subprocess.Popen(
                ssh_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=0
            )

            output_buffer = ""
            error_buffer = ""
            pagination_handled = False

            def timeout_handler():
                time.sleep(timeout)
                if process.poll() is None:
                    self.logger.warning("Command timeout after %ss on %s: %s", timeout, hostname, command)
                    process.terminate()

            timeout_thread = threading.Thread(target=timeout_handler)
            timeout_thread.daemon = True
            timeout_thread.start()

            while process.poll() is None:
                try:
                    chunk = process.stdout.read(1024)
                    if chunk:
                        output_buffer += chunk

                        if self.has_pagination_prompt(output_buffer):
                            self.logger.debug("Pagination prompt detected on %s, sending space", hostname)
                            process.stdin.write(' ')
                            process.stdin.flush()
                            pagination_handled = True
                            output_buffer = self.clean_pagination_prompt(output_buffer)

                    time.sleep(0.1)

                except Exception as exc:
                    self.logger.error("Error reading output from %s: %s", hostname, exc)
                    break

            try:
                remaining_output, remaining_error = process.communicate(timeout=5)
                output_buffer += remaining_output
                error_buffer += remaining_error
            except subprocess.TimeoutExpired:
                process.kill()
                self.log_error(hostname, 'COMMAND_TIMEOUT',
                               f"Process killed due to timeout: {command}", command)
                return None

            final_output = self.clean_ssh_output(output_buffer)

            if process.returncode == 0:
                if final_output.strip():
                    if pagination_handled:
                        self.logger.info("Pagination handled successfully for %s on %s", command, hostname)
                    return final_output
                self.log_missing_data(hostname, 'EMPTY_OUTPUT', f"Command '{command}' returned no output")
                return ""

            error_msg = error_buffer.strip()

            if 'permission denied' in error_msg.lower():
                self.log_error(hostname, 'PERMISSION_DENIED', error_msg, command)
            elif 'connection refused' in error_msg.lower():
                self.log_error(hostname, 'CONNECTION_TIMEOUT', error_msg, command)
            elif 'no route to host' in error_msg.lower():
                self.log_error(hostname, 'HOST_UNREACHABLE', error_msg, command)
            elif 'invalid command' in error_msg.lower() or 'unrecognized command' in error_msg.lower():
                self.log_error(hostname, 'INVALID_COMMAND', error_msg, command)
            else:
                self.log_error(hostname, 'COMMAND_ERROR', error_msg, command)

            return None

        except OSError as exc:
            if 'sshpass' in str(exc):
                self.log_error(hostname, 'MISSING_SSHPASS',
                               "sshpass not found - install with: sudo apt-get install sshpass")
            else:
                self.log_error(hostname, 'CONNECTION_TIMEOUT', f"SSH client error: {exc}")
            return None
        except Exception as exc:
            self.log_error(hostname, 'COMMAND_ERROR',
                           f"Unexpected error executing SSH command: {exc}", command)
            return None

    def has_pagination_prompt(self, text):
        pagination_patterns = [
            r'--More--',
            r'--\\(more\\)--',
            r'--- more ---',
            r'Press any key to continue',
            r'--More-- \\(Press space for more or q to quit\\)',
            r'\\(Press space for more\\)'
        ]

        for pattern in pagination_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def clean_pagination_prompt(self, text):
        patterns_to_remove = [
            r'--More--.*?\\r',
            r'--\\(more\\)--.*?\\r',
            r'--- more ---.*?\\r',
            r'Press any key to continue.*?\\r',
            r'--More-- \\(Press space for more or q to quit\\).*?\\r',
            r'\\(Press space for more\\).*?\\r',
            r'\\x1b\\[[0-9;]*[mGKH]',
            r'\\r\\s*\\r',
        ]

        cleaned = text
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)

        return cleaned

    def clean_ssh_output(self, text):
        if not text:
            return ""

        lines = text.split('\\n')
        if len(lines) > 1 and lines[0].strip() in text:
            lines = lines[1:]

        cleaned = '\\n'.join(lines)
        cleaned = self.clean_pagination_prompt(cleaned)

        ansi_escape = re.compile(r'\\x1b\\[[0-9;]*[mGKH]')
        cleaned = ansi_escape.sub('', cleaned)

        cleaned = re.sub(r'\\r\\n', '\\n', cleaned)
        cleaned = re.sub(r'\\r', '\\n', cleaned)
        cleaned = re.sub(r'\\n{3,}', '\\n\\n', cleaned)

        return cleaned.strip()

    def ssh_command(self, hostname, username, password, command, timeout=30, attempt=0):
        pagination_commands = ['show interface', 'show port', 'show run', 'show config']
        needs_interactive = any(cmd in command.lower() for cmd in pagination_commands)

        if needs_interactive:
            return self.ssh_command_interactive(hostname, username, password, command, timeout, attempt)
        return self.ssh_command_simple(hostname, username, password, command, timeout, attempt)

    def ssh_command_simple(self, hostname, username, password, command, timeout=30, attempt=0):
        try:
            self.logger.debug("Executing simple command on %s: %s (timeout: %ss, attempt: %s)",
                              hostname, command, timeout, attempt)

            if password:
                ssh_cmd = [
                    'sshpass', '-p', password,
                    'ssh',
                    '-o', 'ConnectTimeout=10',
                    '-o', 'StrictHostKeyChecking=no',
                    '-o', 'UserKnownHostsFile=/dev/null',
                    '-o', 'LogLevel=ERROR',
                    f'{username}@{hostname}',
                    command
                ]
            else:
                ssh_cmd = [
                    'ssh',
                    '-o', 'ConnectTimeout=10',
                    '-o', 'StrictHostKeyChecking=no',
                    '-o', 'UserKnownHostsFile=/dev/null',
                    '-o', 'LogLevel=ERROR',
                    f'{username}@{hostname}',
                    command
                ]

            result = subprocess.run(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=timeout
            )

            if result.returncode == 0:
                if result.stdout.strip():
                    return result.stdout
                self.log_missing_data(hostname, 'EMPTY_OUTPUT', f"Command '{command}' returned no output")
                return ""

            error_msg = result.stderr.strip()

            if 'permission denied' in error_msg.lower():
                self.log_error(hostname, 'PERMISSION_DENIED', error_msg, command)
            elif 'connection refused' in error_msg.lower():
                self.log_error(hostname, 'CONNECTION_TIMEOUT', error_msg, command)
            elif 'no route to host' in error_msg.lower():
                self.log_error(hostname, 'HOST_UNREACHABLE', error_msg, command)
            else:
                self.log_error(hostname, 'COMMAND_ERROR', error_msg, command)

            return None

        except subprocess.TimeoutExpired:
            self.log_error(hostname, 'COMMAND_TIMEOUT', f"Command timeout after {timeout}s: {command}", command)
            return None
        except Exception as exc:
            self.log_error(hostname, 'COMMAND_ERROR', f"Error executing SSH command: {exc}", command)
            return None

    # SECTION: collection flow
    def collect_apic_data(self, hostname, username, classes, use_password=True):
        print("\n{}".format("=" * 60))
        print(f"Connecting to APIC {hostname} (user: {username})")
        print("{}".format("=" * 60))

        self.logger.info("Starting APIC data collection for %s (user: %s)", hostname, username)

        apic_data = {
            'hostname': hostname,
            'timestamp': datetime.now().isoformat(),
            'classes_requested': classes,
            'classes_collected': [],
            'class_errors': [],
            'imdata_count': 0,
            'collection_status': 'failed',
            'output_file': ''
        }

        password = None
        if use_password:
            try:
                password = self.get_password(username, hostname)
            except Exception as exc:
                apic_data['class_errors'].append(f"Password authentication failed: {exc}")
                self.logger.error("Failed to get password for %s: %s", hostname, exc)
                return apic_data

        imdata = []
        for class_name in classes:
            cmd = f"moquery -c {class_name} -o json"
            output = self.ssh_command_with_retry(hostname, username, password, cmd, timeout=120)
            if not output:
                apic_data['class_errors'].append(f"{class_name}: empty output")
                continue
            try:
                data = json.loads(output)
                class_imdata = data.get('imdata', [])
                if not class_imdata:
                    apic_data['class_errors'].append(f"{class_name}: no imdata found")
                    continue
                imdata.extend(class_imdata)
                apic_data['classes_collected'].append(class_name)
                self.logger.info("Collected %s objects for %s", len(class_imdata), class_name)
            except Exception as exc:
                apic_data['class_errors'].append(f"{class_name}: {exc}")
                self.logger.error("Failed to parse %s output: %s", class_name, exc)

        if imdata:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(self.output_dir, f"apic_{hostname}_{timestamp}.json")
            self.write_json(output_path, {"imdata": imdata})
            apic_data['imdata_count'] = len(imdata)
            apic_data['output_file'] = output_path
            apic_data['collection_status'] = 'success'
            print(f"APIC collection complete: {len(imdata)} objects")
        else:
            apic_data['collection_status'] = 'failed'
            print("APIC collection failed: no imdata collected")

        return apic_data

    def collect_apic_worker(self, queue, classes):
        while True:
            try:
                hostname, username = queue.pop()
            except IndexError:
                return

            apic_data = self.collect_apic_data(hostname, username, classes, use_password=self.use_password)
            with self.lock:
                self.collected_data.append(apic_data)

    def collect_device_data(self, hostname, username, use_password=True):
        print("\n{}".format("=" * 60))
        print(f"Connecting to {hostname} (user: {username})")
        print("{}".format("=" * 60))

        self.logger.info("Starting data collection for %s (user: %s)", hostname, username)

        device_data = {
            'hostname': hostname,
            'timestamp': datetime.now().isoformat(),
            'show_version': '',
            'interface_output': '',
            'neighbor_output': '',
            'platform': {},
            'commands_executed': [],
            'commands_failed': [],
            'pagination_disabled': False,
            'collection_status': 'failed',
            'error_summary': [],
            'missing_data_summary': []
        }

        password = None
        if use_password:
            try:
                password = self.get_password(username, hostname)
            except Exception as exc:
                device_data['error_summary'].append(f"Password authentication failed: {exc}")
                self.logger.error("Failed to get password for %s: %s", hostname, exc)
                return device_data

        print("Step 1: Platform Detection")
        self.logger.info("Step 1: Platform detection for %s", hostname)

        version_timeout = 30
        version_output = self.ssh_command_with_retry(hostname, username, password, 'show version', version_timeout)

        if not version_output:
            device_data['error_summary'].append("Failed to get show version output")
            device_data['missing_data_summary'].append("show version")
            print(f"Failed to get show version from {hostname}")
            return device_data

        device_data['show_version'] = version_output
        device_data['commands_executed'].append('show version')
        self.logger.info("Successfully collected show version from %s", hostname)

        platform = self.detect_platform_from_version(version_output, hostname)
        device_data['platform'] = platform

        print("Detected Platform:")
        print(f"   Vendor: {platform['vendor']}")
        print(f"   OS: {platform['os']}")
        print(f"   Model: {platform['model']}")
        print(f"   Platform Type: {platform['platform_type']}")

        print("\nStep 2: Attempt to Disable Paging")
        self.logger.info("Step 2: Attempting to disable paging on %s", hostname)

        paging_cmd = platform['commands']['paging_disable']
        paging_timeout = platform['commands']['timeouts']['paging_disable']

        print(f"   Command: {paging_cmd}")
        print("   Note: This may fail due to AAA authorization restrictions")

        paging_result = self.ssh_command(hostname, username, password, paging_cmd, paging_timeout)
        if paging_result and 'invalid' not in paging_result.lower() and 'error' not in paging_result.lower():
            device_data['commands_executed'].append(paging_cmd)
            device_data['pagination_disabled'] = True
            print("Paging disabled successfully")
            self.logger.info("Paging disabled successfully on %s", hostname)
        else:
            device_data['pagination_disabled'] = False
            device_data['commands_failed'].append(paging_cmd)
            print("Paging could not be disabled (AAA restrictions or insufficient privileges)")
            print("   Will handle pagination automatically during command execution")
            self.logger.warning("Paging could not be disabled on %s - will handle automatically", hostname)

        print("\nStep 3: Interface Status Collection")
        self.logger.info("Step 3: Collecting interface status from %s", hostname)

        interface_cmd = platform['commands']['interfaces']
        interface_timeout = platform['commands']['timeouts']['interfaces']

        print(f"   Command: {interface_cmd}")
        print(f"   Timeout: {interface_timeout}s (extended for {platform['os']} devices)")

        if not device_data['pagination_disabled']:
            print("   Pagination handling: Automatic (paging not disabled)")

        interface_output = self.ssh_command_with_retry(hostname, username, password, interface_cmd, interface_timeout)
        if interface_output:
            device_data['interface_output'] = interface_output
            device_data['commands_executed'].append(interface_cmd)
            line_count = len(interface_output.splitlines())
            print(f"Interface data collected ({line_count} lines)")
            self.logger.info("Successfully collected interface data from %s (%s lines)", hostname, line_count)

            if line_count < 3:
                print("Warning: Interface output seems too short, may be incomplete")
                self.log_missing_data(hostname, 'INSUFFICIENT_INTERFACE_DATA',
                                      f"Interface output only {line_count} lines, may be incomplete")
        else:
            device_data['commands_failed'].append(interface_cmd)
            device_data['error_summary'].append("Failed to collect interface status")
            device_data['missing_data_summary'].append("interface status")
            print(f"Failed to get interface data from {hostname}")
            return device_data

        print("\nStep 4: Neighbor Discovery")
        self.logger.info("Step 4: Collecting neighbor data from %s", hostname)

        neighbor_cmd = platform['commands']['neighbors']
        neighbor_timeout = platform['commands']['timeouts']['neighbors']

        print(f"   Command: {neighbor_cmd}")
        print(f"   Timeout: {neighbor_timeout}s")

        neighbor_output = self.ssh_command_with_retry(hostname, username, password, neighbor_cmd, neighbor_timeout)
        if neighbor_output:
            device_data['neighbor_output'] = neighbor_output
            device_data['commands_executed'].append(neighbor_cmd)
            neighbor_line_count = len(neighbor_output.splitlines())
            print(f"Neighbor data collected ({neighbor_line_count} lines)")
            self.logger.info("Successfully collected neighbor data from %s (%s lines)",
                             hostname, neighbor_line_count)
        else:
            device_data['commands_failed'].append(neighbor_cmd)
            device_data['missing_data_summary'].append("neighbor discovery")
            print("Warning: Could not collect neighbor data")
            self.logger.warning("Failed to collect neighbor data from %s", hostname)
            device_data['neighbor_output'] = ''

        device_data['collection_status'] = 'success'

        print(f"\nSUCCESS: Data collection complete for {hostname}")
        print(f"   Commands executed: {', '.join(device_data['commands_executed'])}")
        print(f"   Pagination disabled: {'Yes' if device_data['pagination_disabled'] else 'No (handled automatically)'}")

        if device_data['commands_failed']:
            print(f"   Commands failed: {', '.join(device_data['commands_failed'])}")

        self.logger.info("Successfully completed data collection for %s", hostname)

        return device_data

    # SECTION: hosts file
    def create_example_hosts_file(self):
        example_lines = [
            "# hostname,username",
            "switch1.example.com,admin",
            "switch2.example.com,admin",
            "# or username@hostname",
            "admin@switch3.example.com"
        ]
        with open(self.hosts_file, 'w', encoding='utf-8') as handle:
            handle.write("\n".join(example_lines) + "\n")

    def load_hosts(self):
        hosts = []

        if not os.path.exists(self.hosts_file):
            print(f"Creating example hosts file: {self.hosts_file}")
            self.create_example_hosts_file()
            return hosts

        try:
            with open(self.hosts_file, 'r', encoding='utf-8') as handle:
                for line_num, line in enumerate(handle, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    hostname = None
                    username = None

                    if ',' in line:
                        parts = [part.strip() for part in line.split(',', 1)]
                        hostname = parts[0]
                        username = parts[1] if len(parts) > 1 else None
                    elif '@' in line:
                        username, hostname = line.split('@', 1)
                    else:
                        hostname = line

                    if not hostname:
                        self.logger.warning("Invalid host line %s: %s", line_num, line)
                        continue

                    if not username:
                        username = self.default_username

                    if not username:
                        self.logger.warning("No username for host %s (line %s)", hostname, line_num)
                        continue

                    hosts.append((hostname, username))

        except Exception as exc:
            self.logger.error("Error reading hosts file: %s", exc)

        return hosts

    # SECTION: output writers
    def write_json(self, path, data):
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2)

    def write_csv(self, path, rows, headers):
        with open(path, 'w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def save_outputs(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        summary_path = os.path.join(self.output_dir, f"collection_summary_{timestamp}.json")
        self.write_json(summary_path, {
            'generated_at': datetime.now().isoformat(),
            'host_count': len(self.collected_data),
            'success_count': len([d for d in self.collected_data if d['collection_status'] == 'success']),
            'failures': self.connection_failures,
            'command_failures': self.command_failures,
            'missing_data': self.missing_data,
            'devices': self.collected_data
        })

        if self.connection_failures:
            self.write_csv(
                os.path.join(self.output_dir, f"connection_failures_{timestamp}.csv"),
                self.connection_failures,
                ['timestamp', 'hostname', 'category', 'message', 'command', 'description']
            )

        if self.command_failures:
            self.write_csv(
                os.path.join(self.output_dir, f"command_failures_{timestamp}.csv"),
                self.command_failures,
                ['timestamp', 'hostname', 'category', 'message', 'command', 'description']
            )

        if self.missing_data:
            self.write_csv(
                os.path.join(self.output_dir, f"missing_data_{timestamp}.csv"),
                self.missing_data,
                ['timestamp', 'hostname', 'missing_type', 'details']
            )

        for device in self.collected_data:
            device_path = os.path.join(self.output_dir, f"{device['hostname']}_raw.json")
            self.write_json(device_path, device)

        self.logger.info("Saved summary to %s", summary_path)

    # SECTION: worker + run
    def collect_worker(self, queue):
        while True:
            try:
                hostname, username = queue.pop()
            except IndexError:
                return

            device_data = self.collect_device_data(hostname, username, use_password=self.use_password)
            with self.lock:
                self.collected_data.append(device_data)

    def run(self):
        hosts = self.load_hosts()
        if not hosts:
            print("No hosts loaded. Please update hosts file and retry.")
            return 1

        queue = hosts[:]
        threads = []
        for _ in range(min(self.threads, len(queue))):
            thread = threading.Thread(target=self.collect_worker, args=(queue,))
            thread.daemon = True
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        self.save_outputs()
        print("\nCollection complete.")
        print(f"Total devices: {len(self.collected_data)}")
        print(f"Successful: {len([d for d in self.collected_data if d['collection_status'] == 'success'])}")
        print(f"Failed: {len([d for d in self.collected_data if d['collection_status'] != 'success'])}")
        return 0

    def run_apic(self, classes):
        hosts = self.load_hosts()
        if not hosts:
            print("No hosts loaded. Please update hosts file and retry.")
            return 1

        queue = hosts[:]
        threads = []
        for _ in range(min(self.threads, len(queue))):
            thread = threading.Thread(target=self.collect_apic_worker, args=(queue, classes))
            thread.daemon = True
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        self.save_outputs()
        print("\nAPIC collection complete.")
        print(f"Total APICs: {len(self.collected_data)}")
        print(f"Successful: {len([d for d in self.collected_data if d['collection_status'] == 'success'])}")
        print(f"Failed: {len([d for d in self.collected_data if d['collection_status'] != 'success'])}")
        return 0


# SECTION: cli
def parse_args():
    parser = argparse.ArgumentParser(description="SSH-based network data collector")
    parser.add_argument("--hosts-file", default="hosts.txt", help="Hosts file (hostname,username)")
    parser.add_argument("--output-dir", default="network_data", help="Output directory")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    parser.add_argument("--threads", type=int, default=4, help="Parallel threads")
    parser.add_argument("--username", help="Default username for hosts without one")
    parser.add_argument("--no-password", action="store_true", help="Do not prompt for passwords")
    parser.add_argument("--apic", action="store_true", help="Collect ACI data from APIC via SSH")
    parser.add_argument("--aci-classes", help="Comma-separated ACI classes to collect (defaults to full set)")
    return parser.parse_args()


def main():
    args = parse_args()
    collector = NetworkDataCollector(
        hosts_file=args.hosts_file,
        output_dir=args.output_dir,
        log_level=args.log_level,
        default_username=args.username,
        threads=args.threads,
        use_password=not args.no_password
    )
    if args.apic:
        if args.aci_classes:
            classes = [c.strip() for c in args.aci_classes.split(',') if c.strip()]
        else:
            classes = DEFAULT_ACI_CLASSES
        return collector.run_apic(classes)
    return collector.run()


if __name__ == "__main__":
    raise SystemExit(main())
