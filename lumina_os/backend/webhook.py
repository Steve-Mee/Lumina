"""Compatibility layer: webhook is consolidated in backend.app for simplicity."""

from backend.app import app, submit_trade

__all__ = ["app", "submit_trade"]
