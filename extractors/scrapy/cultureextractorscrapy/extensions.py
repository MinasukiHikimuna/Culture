import logging

from scrapy import signals


class _CollectorHandler(logging.Handler):
    """Logging handler that collects WARNING and ERROR records."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


class LogSummaryExtension:
    """Collects warnings and errors during a crawl and prints a summary at the end."""

    @classmethod
    def from_crawler(cls, crawler):
        ext = cls()
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    def spider_opened(self, spider):
        self.handler = _CollectorHandler()
        logging.getLogger().addHandler(self.handler)

    def spider_closed(self, spider):
        logging.getLogger().removeHandler(self.handler)

        records = self.handler.records
        if not records:
            return

        warnings = [r for r in records if r.levelno == logging.WARNING]
        errors = [r for r in records if r.levelno >= logging.ERROR]

        lines = ["", "=== WARNINGS AND ERRORS SUMMARY ==="]
        if errors:
            lines.append(f"  Errors ({len(errors)}):")
            for r in errors:
                lines.append(f"    [{r.name}] {r.getMessage()}")
        if warnings:
            lines.append(f"  Warnings ({len(warnings)}):")
            for r in warnings:
                lines.append(f"    [{r.name}] {r.getMessage()}")
        lines.append("=" * 37)

        spider.logger.info("\n".join(lines))
