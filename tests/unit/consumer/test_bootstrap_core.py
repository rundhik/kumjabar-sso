from dataclasses import dataclass

import pytest

from idp_pegawai.consumer.bootstrap import (
    BootstrapCoordinator,
    BootstrapError,
    BootstrapPage,
)


@dataclass
class Row:
    change_sequence: int


def test_start_captures_cutoff_atomically_and_pages_never_cross_it():
    rows = [Row(1), Row(2), Row(3)]
    calls = []

    def capture():
        calls.append("capture")
        return 2

    coordinator = BootstrapCoordinator(rows=rows, capture_cutoff=capture)
    session = coordinator.start(page_size=10)
    assert session.cutoff_sequence == 2
    assert [r.change_sequence for r in session.page().items] == [1, 2]
    assert calls == ["capture"]


def test_continuation_requires_completed_bootstrap_and_uses_opaque_checkpoint():
    coordinator = BootstrapCoordinator(rows=[Row(1), Row(2)])
    session = coordinator.start(page_size=1)
    with pytest.raises(BootstrapError):
        session.continue_changes("opaque-checkpoint")
    first = session.page()
    assert first.next_page_cursor is not None
    assert session.apply_page(status_code=200, applied=True)
    session = session.advance(first.next_page_cursor)
    assert session.page().next_page_cursor is None
    assert session.apply_page(status_code=200, applied=True)
    assert session.complete("opaque-checkpoint") == "opaque-checkpoint"
    assert session.continue_changes("opaque-checkpoint") == "opaque-checkpoint"


def test_http_success_is_not_treated_as_atomic_apply():
    coordinator = BootstrapCoordinator(rows=[Row(1)])
    session = coordinator.start(page_size=10)
    assert session.apply_page(status_code=200, applied=False) is False
    with pytest.raises(BootstrapError):
        session.complete("cp")


def test_page_cursor_is_opaque_and_invalid_cursor_rejected():
    coordinator = BootstrapCoordinator(rows=[Row(1), Row(2)])
    session = coordinator.start(page_size=1)
    cursor = session.page().next_page_cursor
    assert isinstance(cursor, str)
    with pytest.raises(BootstrapError):
        session.advance(cursor + "x")


def test_bootstrap_page_shape():
    page = BootstrapPage(items=[], next_page_cursor=None, has_more=False)
    assert not page.has_more
    assert page.next_page_cursor is None
