"""Tests for the selector guard that detects a Recreation.gov redesign.

The add-to-cart outage was invisible to CI because every DOM-touching function
was mocked. This guard exists to fail loudly the next time Recreation.gov moves
an element; these tests cover its reporting logic without a real browser.
"""
import playwright_service.browser as browser
from playwright_service.selector_check import (
    missing_campsite_selectors,
    missing_login_selectors,
)


class FakeRoleLocator:
    def __init__(self, count):
        self._count = count

    def count(self):
        return self._count


class FakeProbePage:
    """Page whose selectors resolve only if listed in `present`."""

    def __init__(self, present, submit_button_present=True):
        self.present = set(present)
        self.submit_button_present = submit_button_present

    def locator(self, selector):
        return FakeRoleLocator(1 if selector in self.present else 0)

    def get_by_role(self, role, name=None, exact=False):
        return FakeRoleLocator(1 if self.submit_button_present else 0)


ALL_LOGIN = [browser.EMAIL_SELECTOR, browser.PASSWORD_SELECTOR]


def test_no_missing_login_selectors_when_the_page_is_intact():
    assert missing_login_selectors(FakeProbePage(ALL_LOGIN)) == []


def test_reports_a_renamed_password_field():
    """This is the exact regression that broke add-to-cart."""
    page = FakeProbePage([browser.EMAIL_SELECTOR])
    missing = missing_login_selectors(page)
    assert len(missing) == 1
    assert browser.PASSWORD_SELECTOR in missing[0]


def test_reports_a_renamed_email_field():
    page = FakeProbePage([browser.PASSWORD_SELECTOR])
    missing = missing_login_selectors(page)
    assert len(missing) == 1
    assert browser.EMAIL_SELECTOR in missing[0]


def test_reports_a_missing_submit_button():
    page = FakeProbePage(ALL_LOGIN, submit_button_present=False)
    missing = missing_login_selectors(page)
    assert len(missing) == 1
    assert browser.SUBMIT_BUTTON_NAME in missing[0]


def test_no_missing_campsite_selectors_when_the_page_is_intact():
    assert missing_campsite_selectors(FakeProbePage([browser.CART_SELECTOR])) == []


def test_reports_a_renamed_add_to_cart_button():
    missing = missing_campsite_selectors(FakeProbePage([]))
    assert len(missing) == 1
    assert browser.CART_SELECTOR in missing[0]
