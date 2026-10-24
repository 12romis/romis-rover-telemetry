"""Помічники браузерних тестів: збір порушень CSP, помилок консолі та запитів сторінки."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Watch:
    """Що сторінка зробила: порушення CSP, помилки консолі, усі запити."""

    violations: list[str] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    requests: list[str] = field(default_factory=list)

    def assert_clean(self, base_url: str) -> None:
        assert self.violations == []
        assert self.console_errors == []
        assert self.requests, "сторінка не робила запитів"
        foreign = [u for u in self.requests if not u.startswith((base_url, "data:", "blob:"))]
        assert foreign == [], foreign


def watch_page(page: Any) -> Watch:
    watch = Watch()
    page.set_default_timeout(10_000)  # провал має бути швидким, а не 30-секундним
    page.expose_function("report_violation", lambda detail: watch.violations.append(str(detail)))
    page.add_init_script(
        "document.addEventListener('securitypolicyviolation', e =>"
        " window.report_violation(e.violatedDirective + ' ' + e.blockedURI));"
    )
    page.on("console", lambda m: watch.console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: watch.console_errors.append(str(e)))
    page.on("request", lambda r: watch.requests.append(r.url))
    return watch
