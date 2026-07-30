"""Test-wide guarantees.

The network block is the enforcement of "no network calls in tests". Asserting it
at the socket layer rather than by mocking `requests` and `yfinance` individually
means a new module reaching for the network cannot quietly slip past -- including
transitively, through a library we did not think to stub.
"""
from __future__ import annotations

import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError(
            "a test attempted a network connection; mock the data provider instead"
        )

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
