"""Compose the independent service monitor at the HTTP application's boundary."""
from monitoring.service_management import MONITOR

from .models import BackgroundTask


def service_monitor_task() -> BackgroundTask:
    return BackgroundTask(
        label='service-management-monitor', target=MONITOR.run,
        banner='Monitoring API, watchdog, and worker service states every 15 seconds')
