#!/usr/bin/env python3
"""
Service connectivity status check script.
Uses the same StashappClient and patterns as the actual import scripts.

Usage:
    python check_status.py          # Single check
    python check_status.py --loop   # Continuous loop for Zellij testing
"""

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
from exceptions import StashappUnavailableError
from stashapp_importer import LM_STUDIO_URL, StashappClient


LOG_FILE = Path(__file__).parent / "connectivity_test.log"


def check_stashapp_status() -> dict:
    """Check Stashapp connectivity using StashappClient."""
    result = {
        "service": "Stashapp",
        "connected": False,
        "version": None,
        "response_time_ms": None,
        "error": None,
        "url": None,
    }

    start_time = time.time()
    try:
        client = StashappClient()
        result["url"] = client.url
        version = client.get_version()
        result["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
        result["connected"] = True
        result["version"] = version
    except ValueError as e:
        result["error"] = str(e)
    except StashappUnavailableError as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def check_lmstudio_status() -> dict:
    """Check LM Studio connectivity."""
    result = {
        "service": "LM Studio",
        "connected": False,
        "model": None,
        "response_time_ms": None,
        "error": None,
        "url": LM_STUDIO_URL,
    }

    models_url = LM_STUDIO_URL.replace("/v1/chat/completions", "/v1/models")

    start_time = time.time()
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(models_url)
            result["response_time_ms"] = round((time.time() - start_time) * 1000, 2)

            if response.status_code != 200:
                result["error"] = f"HTTP {response.status_code}"
                return result

            data = response.json()
            if data.get("data"):
                result["model"] = data["data"][0].get("id", "unknown")
            result["connected"] = True

    except httpx.ConnectError as e:
        result["error"] = f"Connection failed: {e}"
    except httpx.TimeoutException:
        result["error"] = "Timeout (10s)"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def print_status(status: dict):
    """Print status for a service."""
    icon = "OK" if status["connected"] else "FAIL"
    print(f"[{icon}] {status['service']}")
    if status["url"]:
        print(f"    URL: {status['url']}")

    if status["connected"]:
        if status.get("version"):
            print(f"    Version: {status['version']}")
        if status.get("model"):
            print(f"    Model: {status['model']}")
        print(f"    Response: {status['response_time_ms']}ms")
    else:
        print(f"    Error: {status['error']}")


def run_single_check() -> bool:
    """Run a single status check. Returns True if all services are up."""
    print("=" * 50)
    print(f"Service Status Check - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    stash = check_stashapp_status()
    lm = check_lmstudio_status()

    print_status(stash)
    print()
    print_status(lm)
    print("=" * 50)

    return stash["connected"] and lm["connected"]


def log(msg: str):
    """Print and append to log file."""
    print(msg)
    with LOG_FILE.open("a") as f:
        f.write(msg + "\n")


def get_network_diagnostics() -> str:
    """Get network diagnostics for debugging."""
    lines = []
    try:
        # Check default route
        result = subprocess.run(
            ["netstat", "-rn"],
            check=False, capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if "default" in line and "en0" in line:
                lines.append(f"  Route: {line.strip()}")
                break

        # Quick ping to gateway
        result = subprocess.run(
            ["ping", "-c", "1", "-t", "2", "10.0.0.1"],
            check=False, capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            lines.append("  Gateway 10.0.0.1: reachable")
        else:
            lines.append("  Gateway 10.0.0.1: UNREACHABLE")

        # Quick ping to LM Studio host
        result = subprocess.run(
            ["ping", "-c", "1", "-t", "2", "10.0.1.1"],
            check=False, capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            lines.append("  Host 10.0.1.1: reachable")
        else:
            lines.append("  Host 10.0.1.1: UNREACHABLE")

        # DNS resolution test
        try:
            ip = socket.gethostbyname("stash-aural.chiefsclub.com")
            lines.append(f"  DNS stash-aural.chiefsclub.com: {ip}")
        except socket.gaierror as e:
            lines.append(f"  DNS stash-aural.chiefsclub.com: FAILED ({e})")

        # Raw socket test to LM Studio port
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(("10.0.1.1", 1234))
            sock.close()
            lines.append("  Socket 10.0.1.1:1234: connectable")
        except Exception as e:
            lines.append(f"  Socket 10.0.1.1:1234: FAILED ({e})")

        # Raw socket test to Stashapp (port 443)
        try:
            ip = socket.gethostbyname("stash-aural.chiefsclub.com")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((ip, 443))
            sock.close()
            lines.append(f"  Socket {ip}:443: connectable")
        except Exception as e:
            lines.append(f"  Socket stash-aural:443: FAILED ({e})")

        # Check open file descriptors
        try:
            pid = os.getpid()
            result = subprocess.run(
                ["lsof", "-p", str(pid)],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )
            fd_count = len(result.stdout.splitlines()) - 1
            lines.append(f"  Open FDs (this process): {fd_count}")
        except Exception:
            pass

        # Check system-wide socket count
        try:
            result = subprocess.run(
                ["netstat", "-an"],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )
            established = sum(1 for l in result.stdout.splitlines() if "ESTABLISHED" in l)
            time_wait = sum(1 for l in result.stdout.splitlines() if "TIME_WAIT" in l)
            lines.append(f"  Sockets: {established} ESTABLISHED, {time_wait} TIME_WAIT")
        except Exception:
            pass

        # Check proxy env vars
        proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy"]
        proxies = {k: os.environ.get(k) for k in proxy_vars if os.environ.get(k)}
        if proxies:
            lines.append(f"  Proxy env: {proxies}")
        else:
            lines.append("  Proxy env: none set")

        # curl test (bypasses Python stack entirely)
        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "--connect-timeout", "2", "http://10.0.1.1:1234/v1/models"],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )
            lines.append(f"  curl 10.0.1.1:1234: HTTP {result.stdout}")
        except Exception as e:
            lines.append(f"  curl 10.0.1.1:1234: FAILED ({e})")

        # Test external HTTPS (internet connectivity)
        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "--connect-timeout", "2", "https://www.google.com"],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )
            lines.append(f"  curl google.com (HTTPS): HTTP {result.stdout}")
        except Exception as e:
            lines.append(f"  curl google.com (HTTPS): FAILED ({e})")

        # Test external socket connection
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(("8.8.8.8", 443))
            sock.close()
            lines.append("  Socket 8.8.8.8:443 (Google): connectable")
        except Exception as e:
            lines.append(f"  Socket 8.8.8.8:443 (Google): FAILED ({e})")

        # Check if en0 has valid IP
        try:
            result = subprocess.run(
                ["ipconfig", "getifaddr", "en0"],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )
            en0_ip = result.stdout.strip()
            lines.append(f"  en0 IP: {en0_ip if en0_ip else 'NO IP'}")
        except Exception:
            pass

        # ARP cache for the target
        try:
            result = subprocess.run(
                ["arp", "-n", "10.0.1.1"],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )
            lines.append(f"  ARP 10.0.1.1: {result.stdout.strip()}")
        except Exception:
            pass

        # Check active SSH connections
        try:
            result = subprocess.run(
                ["netstat", "-an"],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )
            ssh_conns = [l for l in result.stdout.splitlines() if ":22 " in l or ".22 " in l]
            lines.append(f"  SSH connections: {len(ssh_conns)}")
        except Exception:
            pass

        # traceroute to see where it breaks (quick, 2 hops max)
        try:
            result = subprocess.run(
                ["traceroute", "-n", "-m", "2", "-w", "1", "10.0.1.1"],
                check=False, capture_output=True,
                text=True,
                timeout=10,
            )
            tr_lines = [l.strip() for l in result.stdout.splitlines() if l.strip() and not l.startswith("traceroute")]
            lines.append(f"  Traceroute: {'; '.join(tr_lines[:2])}")
        except Exception as e:
            lines.append(f"  Traceroute: {e}")

        # Check connections TO the Windows server
        try:
            result = subprocess.run(
                ["netstat", "-an"],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )
            to_windows = [l.strip() for l in result.stdout.splitlines()
                         if "10.0.1.1" in l and ("ESTABLISHED" in l or "SYN_SENT" in l)]
            lines.append(f"  Connections to 10.0.1.1: {len(to_windows)}")
            for conn in to_windows[:3]:  # Show first 3
                lines.append(f"    {conn}")
        except Exception:
            pass

        # Try connecting to different ports on same host
        for port, name in [(22, "SSH"), (3389, "RDP"), (445, "SMB"), (135, "RPC")]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect(("10.0.1.1", port))
                sock.close()
                lines.append(f"  Socket 10.0.1.1:{port} ({name}): connectable")
            except Exception as e:
                err = str(e).split("]")[-1].strip() if "]" in str(e) else str(e)
                lines.append(f"  Socket 10.0.1.1:{port} ({name}): FAILED ({err})")

        # Try a different local IP on same subnet
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(("10.0.0.1", 80))  # Gateway
            sock.close()
            lines.append("  Socket 10.0.0.1:80 (Gateway): connectable")
        except Exception as e:
            lines.append(f"  Socket 10.0.0.1:80 (Gateway): FAILED ({e})")

        # Check Zellij session info
        try:
            result = subprocess.run(
                ["zellij", "list-sessions"],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )
            lines.append(f"  Zellij sessions: {result.stdout.strip()}")
        except Exception:
            pass

        # Check current TTY
        try:
            tty = os.ttyname(0) if os.isatty(0) else "not a tty"
            lines.append(f"  TTY: {tty}")
        except Exception as e:
            lines.append(f"  TTY: {e}")

        # Check Zellij environment variables
        zellij_vars = [k for k in os.environ if "ZELLIJ" in k.upper()]
        if zellij_vars:
            lines.append(f"  Zellij env vars: {', '.join(zellij_vars)}")
            for var in zellij_vars[:3]:
                lines.append(f"    {var}={os.environ.get(var, '')[:50]}")

        # Check for any unusual environment that might affect networking
        network_env = ["LD_PRELOAD", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH"]
        for var in network_env:
            if os.environ.get(var):
                lines.append(f"  {var}: {os.environ.get(var)}")

        # Check process parent
        try:
            ppid = os.getppid()
            result = subprocess.run(
                ["ps", "-p", str(ppid), "-o", "comm="],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )
            lines.append(f"  Parent process: {result.stdout.strip()} (PID {ppid})")
        except Exception:
            pass

        # Check if running under any wrapper
        try:
            result = subprocess.run(
                ["ps", "-p", str(os.getpid()), "-o", "ppid=,comm="],
                check=False, capture_output=True,
                text=True,
                timeout=5,
            )
            lines.append(f"  Process info: {result.stdout.strip()}")
        except Exception:
            pass

    except Exception as e:
        lines.append(f"  Diagnostics error: {e}")

    return "\n".join(lines)


def run_loop(interval: int = 5):
    """Run continuous connectivity test loop."""
    log(f"Starting connectivity test loop at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Logging to: {LOG_FILE}")
    log("Press Ctrl+C to stop")
    log("")

    try:
        while True:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            stash = check_stashapp_status()
            lm = check_lmstudio_status()

            all_ok = stash["connected"] and lm["connected"]
            status = "ALL_OK" if all_ok else "FAIL"

            log(f"[{timestamp}] Status: {status}")

            if not all_ok:
                if not stash["connected"]:
                    log(f"  Stashapp: {stash['error']}")
                if not lm["connected"]:
                    log(f"  LM Studio: {lm['error']}")
                # Add network diagnostics on failure
                log(get_network_diagnostics())

            time.sleep(interval)

    except KeyboardInterrupt:
        log(f"\nStopped at {time.strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    parser = argparse.ArgumentParser(description="Check service connectivity")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run in continuous loop mode for Zellij testing",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Seconds between checks in loop mode (default: 5)",
    )
    args = parser.parse_args()

    if args.loop:
        run_loop(args.interval)
    else:
        all_ok = run_single_check()
        sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
