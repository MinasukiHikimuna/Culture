#!/usr/bin/env python3
"""
Simple script to format Python code with Black.
Usage: python format.py [--check]
"""

import subprocess
import sys
from pathlib import Path


def run_black(check_only=False):
    """Run Black on the scripts directory."""
    cmd = ["uv", "run", "black"]

    if check_only:
        cmd.extend(["--check", "--diff"])

    cmd.append("scripts/")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode


def main():
    """Main function."""
    check_only = "--check" in sys.argv

    if check_only:
        print("🔍 Checking code formatting...")
        exit_code = run_black(check_only=True)
        if exit_code == 0:
            print("✅ All files are properly formatted!")
        else:
            print("❌ Some files need formatting. Run without --check to fix.")
    else:
        print("🎨 Formatting code with Black...")
        exit_code = run_black(check_only=False)
        if exit_code == 0:
            print("✅ Code formatting complete!")
        else:
            print("❌ Formatting failed.")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
