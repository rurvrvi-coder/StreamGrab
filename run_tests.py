#!/usr/bin/env python3
"""
Test runner script for StreamGrab

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py --cov       # Run with coverage
    python run_tests.py --fast      # Skip slow tests
    python run_tests.py --verbose   # Verbose output
"""

import sys
import os
import subprocess


def main():
    args = sys.argv[1:]

    base_cmd = ["python", "-m", "pytest", "tests/", "-v"]

    if "--cov" in args:
        base_cmd.extend(
            [
                "--cov=downloader",
                "--cov-report=term-missing",
                "--cov-report=html",
                "--cov-report=xml",
            ]
        )
        args.remove("--cov")

    if "--fast" in args:
        base_cmd.extend(["-m", "not slow"])
        args.remove("--fast")

    if "--verbose" in args or "-v" in args:
        base_cmd.append("-vv")

    base_cmd.extend(args)

    print("=" * 60)
    print("StreamGrab Test Suite")
    print("=" * 60)
    print(f"Running: {' '.join(base_cmd)}")
    print("=" * 60)

    result = subprocess.run(base_cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
