"""A shared deadline across pagination, retries and sources in one sync job."""
from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar


class SyncDeadlineExceeded(TimeoutError):
    pass


_deadline: ContextVar[float | None] = ContextVar('sync_deadline', default=None)


@contextmanager
def sync_budget(seconds: float):
    until = time.monotonic() + seconds
    parent = _deadline.get()
    token = _deadline.set(min(parent, until) if parent is not None else until)
    try:
        yield
    finally:
        _deadline.reset(token)


def remaining_timeout(request_timeout: float) -> float:
    deadline = _deadline.get()
    if deadline is None:
        return request_timeout
    remaining = deadline - time.monotonic()
    if remaining < 1:
        raise SyncDeadlineExceeded('同步时间预算耗尽，保留上次完整论文快照')
    return min(request_timeout, remaining)


def retry_sleep(seconds: float) -> None:
    # Do not sleep through the remaining execution window.
    remaining_timeout(seconds + 1)
    deadline = _deadline.get()
    if deadline is not None and time.monotonic() + seconds + 1 >= deadline:
        raise SyncDeadlineExceeded('上游限流等待超过同步时间预算')
    time.sleep(seconds)
