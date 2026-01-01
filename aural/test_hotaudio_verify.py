#!/usr/bin/env python3
"""
HotAudio Decryption Verification Tests

Pytest-based verification suite that runs the Python hotaudio_extractor.py
and compares output against known good values to validate the decryption.

Usage:
    uv run pytest test_hotaudio_verify.py -v                    # Run all tests
    uv run pytest test_hotaudio_verify.py -v -k "short"         # Run specific case
    uv run pytest test_hotaudio_verify.py -v --check-output     # Verify existing files only
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Known good values from verified extractions
TEST_CASES = {
    "short_audio": {
        "name": "Short Audio (37s)",
        "url": "https://hotaudio.net/u/SweetnEvil86/Lurky-and-Emma-Airplane-Collab-Blooper",
        "expected": {
            "hax": {
                "size_bytes": 310092,
                "sha256": "a2b02d7509e5d397cc9333fdb904e45c6ff579b41ecec01d07ceb5c223249ed9",
                "header_hex": "48415830e4060b0006020000",
            },
            "metadata": {
                "base_key_hex": "9d75bba6e2f08bebd4886ddc177da300",
                "codec": "aac",
                "duration_ms": 37175,
                "segment_count": 37,
            },
            "output": {
                "size_bytes": 721388,
                "sha256": "0e3e7d6c3117278b2efb5356d35a23e5c2f6cd0a64b62b53633ca3a5252d94eb",
            },
            # Key derivation info for documentation
            "key_info": {
                "tree_depth": 6,
                "segment_key_base": 129,
                "root_key_node": 1,
                "note": "Short files receive root key (node 1), allowing full tree derivation",
            },
        },
    },
    "long_audio": {
        "name": "Long Audio (7:12)",
        "url": "https://hotaudio.net/u/Lurkydip/BBW-Belly-Blowjob-Wank",
        "expected": {
            "hax": {
                "size_bytes": 8116321,
                "sha256": "2f0818966979f38f9b48f43e0d564d3b4888ea00d3b61fc4f77ac48acb97d127",
            },
            "metadata": {
                "codec": "aac",
                "duration_ms": 432810,  # ~7:12.81
                "segment_count": 432,
            },
            "output": {
                "size_bytes": 8116321,
                "sha256": "9477eb72c99299f0fe7c95593146c0464da57956e860b17a92bdaaa375f991c1",
            },
            # Key derivation info
            "key_info": {
                "tree_depth": 9,
                "segment_key_base": 1025,
                "note": "Long files receive subtree keys progressively during playback",
            },
        },
    },
}


def sha256_file(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def run_extractor(url: str) -> dict:
    """Run the HotAudio Python extractor with --verify flag and return verification data."""
    result = subprocess.run(
        ["uv", "run", "python", "hotaudio_extractor.py", url, "--verify"],
        capture_output=True,
        text=True,
        timeout=600,  # 10 minute timeout for long audio playback
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Extractor failed with code {result.returncode}\n{result.stderr}"
        )

    # Extract verification JSON from output
    marker = "--- VERIFICATION DATA ---"
    stdout = result.stdout

    marker_index = stdout.find(marker)
    if marker_index == -1:
        raise RuntimeError("No verification data found in output")

    json_str = stdout[marker_index + len(marker) :].strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse verification JSON: {e}")


def compare_values(actual: dict, expected: dict, path: str = "") -> list[dict]:
    """Recursively compare actual vs expected values, returning list of comparisons."""
    results = []

    if expected is None:
        return results

    for key, exp_val in expected.items():
        # Skip documentation fields
        if key in ("note", "key_info"):
            continue

        current_path = f"{path}.{key}" if path else key
        act_val = actual.get(key) if actual else None

        if isinstance(exp_val, dict):
            results.extend(compare_values(act_val, exp_val, current_path))
        else:
            results.append(
                {
                    "path": current_path,
                    "expected": exp_val,
                    "actual": act_val,
                    "match": act_val == exp_val,
                }
            )

    return results


class TestHotAudioVerification:
    """Test suite for HotAudio decryption verification."""

    @pytest.mark.parametrize(
        "case_id,test_case",
        [(k, v) for k, v in TEST_CASES.items()],
        ids=[v["name"] for v in TEST_CASES.values()],
    )
    def test_extraction(self, case_id: str, test_case: dict, check_output_only: bool):
        """Test extraction and verify against known good values."""
        url = test_case["url"]
        expected = test_case["expected"]

        if check_output_only:
            # Just verify existing output file
            slug = url.split("/")[-1]
            output_path = Path(f"./data/hotaudio/{slug}.m4a")

            if not output_path.exists():
                pytest.skip(f"Output file not found: {output_path}")

            stat = output_path.stat()
            sha256 = sha256_file(output_path)

            verify_data = {
                "output": {
                    "path": str(output_path),
                    "size_bytes": stat.st_size,
                    "sha256": sha256,
                }
            }

            # Only compare output fields in check-output mode
            comparisons = compare_values(verify_data, {"output": expected["output"]})
        else:
            # Run full extraction
            try:
                verify_data = run_extractor(url)
            except Exception as e:
                pytest.fail(f"Extraction failed: {e}")

            comparisons = compare_values(verify_data, expected)

        # Check all comparisons
        failures = []
        for comp in comparisons:
            if not comp["match"]:
                failures.append(
                    f"{comp['path']}: expected {comp['expected']}, got {comp['actual']}"
                )

        if failures:
            pytest.fail("\n".join(failures))

    def test_short_audio_output_exists(self):
        """Verify short audio output file exists and has correct hash."""
        test_case = TEST_CASES["short_audio"]
        slug = test_case["url"].split("/")[-1]
        output_path = Path(f"./data/hotaudio/{slug}.m4a")

        if not output_path.exists():
            pytest.skip(f"Output file not found: {output_path}")

        expected_sha256 = test_case["expected"]["output"]["sha256"]
        expected_size = test_case["expected"]["output"]["size_bytes"]

        actual_sha256 = sha256_file(output_path)
        actual_size = output_path.stat().st_size

        assert actual_size == expected_size, (
            f"Size mismatch: {actual_size} != {expected_size}"
        )
        assert actual_sha256 == expected_sha256, (
            f"SHA256 mismatch: {actual_sha256} != {expected_sha256}"
        )

    def test_long_audio_output_exists(self):
        """Verify long audio output file exists and has correct hash."""
        test_case = TEST_CASES["long_audio"]
        slug = test_case["url"].split("/")[-1]
        output_path = Path(f"./data/hotaudio/{slug}.m4a")

        if not output_path.exists():
            pytest.skip(f"Output file not found: {output_path}")

        expected_sha256 = test_case["expected"]["output"]["sha256"]
        expected_size = test_case["expected"]["output"]["size_bytes"]

        actual_sha256 = sha256_file(output_path)
        actual_size = output_path.stat().st_size

        assert actual_size == expected_size, (
            f"Size mismatch: {actual_size} != {expected_size}"
        )
        assert actual_sha256 == expected_sha256, (
            f"SHA256 mismatch: {actual_sha256} != {expected_sha256}"
        )


def main():
    """CLI entry point for running verification directly."""
    import argparse

    parser = argparse.ArgumentParser(
        description="HotAudio Decryption Verification Suite"
    )
    parser.add_argument(
        "--check-output",
        action="store_true",
        help="Only verify existing output files, don't run extraction",
    )
    parser.add_argument(
        "--case",
        type=str,
        choices=list(TEST_CASES.keys()),
        help="Run specific test case",
    )

    args = parser.parse_args()

    print("╔════════════════════════════════════════════════════════════╗")
    print("║         HotAudio Decryption Verification Suite             ║")
    print("╚════════════════════════════════════════════════════════════╝")

    if args.check_output:
        print("\nMode: Checking existing output files only")
    else:
        print("\nMode: Full extraction and verification")
        print("⚠️  Note: This will open browser windows and may take several minutes")

    cases_to_run = {args.case: TEST_CASES[args.case]} if args.case else TEST_CASES

    total_passed = 0
    total_failed = 0

    for case_id, test_case in cases_to_run.items():
        print(f"\n{'=' * 60}")
        print(f"TEST CASE: {test_case['name']}")
        print(f"URL: {test_case['url']}")
        print("=" * 60)

        url = test_case["url"]
        expected = test_case["expected"]

        if args.check_output:
            slug = url.split("/")[-1]
            output_path = Path(f"./data/hotaudio/{slug}.m4a")

            if not output_path.exists():
                print(f"\n❌ File not found: {output_path}")
                total_failed += 1
                continue

            stat = output_path.stat()
            sha256 = sha256_file(output_path)

            verify_data = {
                "output": {
                    "path": str(output_path),
                    "size_bytes": stat.st_size,
                    "sha256": sha256,
                }
            }

            print(f"\nChecking existing file: {output_path}")
            comparisons = compare_values(verify_data, {"output": expected["output"]})
        else:
            print("\nRunning extractor with --verify...")
            print("(This will open a browser window)")

            try:
                verify_data = run_extractor(url)
                print("✅ Extraction completed successfully")
            except Exception as e:
                print(f"\n❌ Extraction failed: {e}")
                total_failed += 1
                continue

            comparisons = compare_values(verify_data, expected)

        print("\n--- VERIFICATION RESULTS ---\n")

        case_passed = 0
        case_failed = 0

        for comp in comparisons:
            if comp["match"]:
                print(f"✅ {comp['path']}")
                print(f"   {comp['actual']}")
                case_passed += 1
            else:
                print(f"❌ {comp['path']}")
                print(f"   Expected: {comp['expected']}")
                print(f"   Actual:   {comp['actual']}")
                case_failed += 1

        print(f"\n{'─' * 40}")
        if case_failed == 0:
            print(f"✅ All {case_passed} checks passed")
        else:
            print(f"❌ {case_failed} failed / {case_passed} passed")

        total_passed += case_passed
        total_failed += case_failed

    # Final summary
    print("\n" + "═" * 60)
    print("FINAL SUMMARY")
    print("═" * 60)
    print(f"Total checks: {total_passed + total_failed}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")

    if total_failed == 0:
        print("\n✅ All verification checks passed!")
        return 0
    else:
        print(f"\n❌ {total_failed} check(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
