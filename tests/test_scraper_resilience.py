from playwright.sync_api import Error as PlaywrightError

from scraper import _extract_search_cards


class RedirectingPage:
    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0
        self.waits: list[int] = []

    def eval_on_selector_all(self, _selector, _script):
        self.calls += 1
        if self.calls <= self.failures:
            raise PlaywrightError("Execution context was destroyed")
        return [
            {
                "title": "Security Engineer",
                "company": "Example AG",
                "link": "https://linkedin.com/jobs/view/1234567890",
            }
        ]

    def wait_for_timeout(self, milliseconds: int):
        self.waits.append(milliseconds)

    def wait_for_load_state(self, _state: str, timeout: int):
        assert timeout == 5_000


def test_search_card_extraction_retries_destroyed_context():
    page = RedirectingPage(failures=2)

    cards = _extract_search_cards(page, attempts=3)

    assert page.calls == 3
    assert page.waits == [300, 600]
    assert cards[0]["title"] == "Security Engineer"


def test_search_card_extraction_raises_after_retry_limit():
    page = RedirectingPage(failures=3)

    try:
        _extract_search_cards(page, attempts=3)
    except PlaywrightError as exc:
        assert "Execution context was destroyed" in str(exc)
    else:
        raise AssertionError("Expected the final Playwright error to be raised")
