"""Custom exceptions for the aural package.

These exceptions represent failures of mandatory resources that should abort
processing rather than continuing to the next item.
"""


class MandatoryResourceError(Exception):
    """Base exception for mandatory resource failures.

    When a mandatory resource (like LM Studio or Stashapp) becomes unavailable,
    processing should abort rather than continue failing on subsequent items.
    """



class LMStudioUnavailableError(MandatoryResourceError):
    """Raised when LM Studio is not available for analysis.

    LM Studio is required for post analysis. If it's unavailable, there's no
    point continuing to process additional posts since they'll all fail.
    """

    def __init__(self, url: str, original_error: Exception | None = None):
        self.url = url
        self.original_error = original_error
        message = (
            f"Could not connect to LM Studio at {url}. "
            "Make sure LM Studio is running and serving."
        )
        super().__init__(message)


class StashappUnavailableError(MandatoryResourceError):
    """Raised when Stashapp is not reachable.

    Stashapp is required for importing content. If it's unavailable, there's no
    point continuing to process additional posts since imports will all fail.
    """

    def __init__(self, url: str, original_error: Exception | None = None):
        self.url = url
        self.original_error = original_error
        message = (
            f"Could not connect to Stashapp at {url}. "
            "Make sure Stashapp is running and accessible."
        )
        super().__init__(message)


class DiskSpaceError(MandatoryResourceError):
    """Raised when disk space is insufficient for downloads.

    If the disk is full, there's no point continuing to process additional posts
    since all downloads will fail. The user needs to free up disk space first.
    """

    def __init__(self, message: str, original_error: Exception | None = None):
        self.original_error = original_error
        super().__init__(f"Disk space exhausted: {message}")
