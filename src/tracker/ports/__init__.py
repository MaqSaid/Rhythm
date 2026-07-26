"""Tracker ports: interface definitions (protocols) for external dependencies.

All ports use typing.Protocol (PEP 544) for structural subtyping. Adapters
implement these protocols without inheriting from them, enabling clean
dependency inversion in the hexagonal architecture.
"""

from tracker.ports.input_monitor import ActivityMonitorPort
from tracker.ports.local_storage import LocalStoragePort
from tracker.ports.logger import StructuredLoggerPort
from tracker.ports.notification import FocusModePort, ToastNotificationPort
from tracker.ports.remote_store import RemoteStorePort
from tracker.ports.time_service import TimeServicePort
from tracker.ports.wifi_detector import WifiDetectionPort, WifiInfo

__all__ = [
    "ActivityMonitorPort",
    "FocusModePort",
    "LocalStoragePort",
    "RemoteStorePort",
    "StructuredLoggerPort",
    "TimeServicePort",
    "ToastNotificationPort",
    "WifiDetectionPort",
    "WifiInfo",
]
