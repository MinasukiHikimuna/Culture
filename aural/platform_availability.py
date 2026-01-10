#!/usr/bin/env python3
"""
Platform Availability Tracker

Tracks audio platform availability for batch processing.
Supports manual skip flags, health checks, and consecutive failure detection.
"""

import httpx


# Platform health check URLs
PLATFORM_HEALTH_URLS = {
    "soundgasm": "https://soundgasm.net",
    "whypit": "https://whyp.it",
    "hotaudio": "https://hotaudio.net",
    "audiochan": "https://audiochan.com",
}


class PlatformAvailabilityTracker:
    """Tracks platform availability for audio extraction."""

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.manually_skipped: set[str] = set()  # From --skip-audio-platform
        self.detected_unavailable: set[str] = set()  # Auto-detected during batch
        self.failure_counts: dict[str, int] = {}  # Consecutive failures per platform
        self.failure_threshold = config.get("failure_threshold", 5)
        self.health_check_results: dict[str, dict] = {}

    def mark_manually_skipped(self, platform: str) -> None:
        """Mark a platform as manually skipped (from CLI flag)."""
        self.manually_skipped.add(platform.lower())

    def is_available(self, platform: str) -> bool:
        """Check if a platform should be attempted."""
        platform = platform.lower()
        if platform in self.manually_skipped:
            return False
        if platform in self.detected_unavailable:
            return False
        return True

    def record_failure(self, platform: str, error: Exception) -> None:
        """
        Record a platform failure.

        Only platform-level errors count toward unavailability threshold.
        File-specific errors (404, 403) don't count.
        """
        platform = platform.lower()

        if not self._is_platform_error(error):
            # File-specific error, don't count toward threshold
            return

        self.failure_counts[platform] = self.failure_counts.get(platform, 0) + 1

        if self.failure_counts[platform] >= self.failure_threshold:
            self.detected_unavailable.add(platform)
            print(
                f"  Platform '{platform}' marked unavailable after "
                f"{self.failure_counts[platform]} consecutive failures"
            )

    def record_success(self, platform: str) -> None:
        """Record a successful extraction, resetting failure count."""
        platform = platform.lower()
        self.failure_counts[platform] = 0

    def _is_platform_error(self, error: Exception) -> bool:
        """
        Determine if error indicates platform-level issue vs file-specific issue.

        Platform errors (count toward unavailability):
        - Connection errors, timeouts
        - Empty responses with 200 status
        - HTTP 500+ server errors

        File errors (don't count):
        - HTTP 404 Not Found
        - HTTP 403 Forbidden (private/deleted content)
        """
        error_str = str(error).lower()

        # File-specific errors - don't count these
        if "404" in error_str or "not found" in error_str:
            return False
        if "403" in error_str or "forbidden" in error_str:
            return False

        # Platform-level errors
        if any(
            x in error_str
            for x in ["connection", "timeout", "empty response", "empty content"]
        ):
            return True
        if "500" in error_str or "502" in error_str or "503" in error_str:
            return True
        if "could not find audio url" in error_str:
            # Soundgasm-specific: empty page means platform down
            return True

        # Default: assume platform error to be safe
        return True

    def check_platform_health(self, platform: str) -> dict:
        """
        Check if platform is reachable and returning valid responses.

        Returns:
            dict with keys: available, status_code, content_length, error
        """
        platform = platform.lower()
        url = PLATFORM_HEALTH_URLS.get(platform)

        if not url:
            return {"available": True, "note": "Unknown platform, assuming available"}

        try:
            # Use GET to check for empty response (Soundgasm's failure mode)
            response = httpx.get(url, timeout=10.0, follow_redirects=True)
            content_length = len(response.content)

            # Check for empty response (Soundgasm-specific issue)
            if response.status_code == 200 and content_length == 0:
                return {
                    "available": False,
                    "status_code": 200,
                    "content_length": 0,
                    "error": "Empty response (platform may be down)",
                }

            # Check for minimal content (page should have at least some HTML)
            if response.status_code == 200 and content_length < 100:
                return {
                    "available": False,
                    "status_code": 200,
                    "content_length": content_length,
                    "error": f"Minimal response ({content_length} bytes)",
                }

            return {
                "available": response.status_code == 200,
                "status_code": response.status_code,
                "content_length": content_length,
                "error": (
                    None if response.status_code == 200 else f"HTTP {response.status_code}"
                ),
            }

        except httpx.TimeoutException:
            return {"available": False, "error": "Connection timeout"}
        except httpx.ConnectError as e:
            return {"available": False, "error": f"Connection failed: {e}"}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def run_health_checks(self, platforms: list[str] | None = None) -> dict[str, dict]:
        """
        Run health checks for specified platforms.

        Args:
            platforms: List of platform names to check. If None, checks all known platforms.

        Returns:
            Dict mapping platform name to health check result
        """
        if platforms is None:
            platforms = list(PLATFORM_HEALTH_URLS.keys())

        results = {}
        for platform in platforms:
            platform = platform.lower()

            # Skip manually skipped platforms
            if platform in self.manually_skipped:
                results[platform] = {
                    "available": False,
                    "error": "Manually skipped via CLI",
                    "skipped": True,
                }
                continue

            result = self.check_platform_health(platform)
            results[platform] = result
            self.health_check_results[platform] = result

            # Mark as unavailable if health check failed
            if not result.get("available"):
                self.detected_unavailable.add(platform)

        return results

    def filter_urls(self, urls: list[dict]) -> list[dict]:
        """
        Filter out URLs from unavailable platforms.

        Args:
            urls: List of URL info dicts with 'platform' and 'url' keys

        Returns:
            Filtered list with only available platform URLs
        """
        return [u for u in urls if self.is_available(u.get("platform", "unknown"))]

    def get_unavailable_platforms(self) -> set[str]:
        """Get all unavailable platforms (manual + detected)."""
        return self.manually_skipped | self.detected_unavailable

    def get_summary(self) -> dict[str, str]:
        """
        Get a summary of platform availability for reporting.

        Returns:
            Dict mapping platform name to status string
        """
        summary = {}
        all_platforms = set(PLATFORM_HEALTH_URLS.keys())

        for platform in sorted(all_platforms):
            if platform in self.manually_skipped:
                summary[platform] = "skipped (CLI flag)"
            elif platform in self.detected_unavailable:
                failures = self.failure_counts.get(platform, 0)
                health_error = self.health_check_results.get(platform, {}).get("error")
                if health_error:
                    summary[platform] = f"unavailable ({health_error})"
                elif failures > 0:
                    summary[platform] = f"unavailable ({failures} consecutive failures)"
                else:
                    summary[platform] = "unavailable"
            else:
                summary[platform] = "available"

        return summary
