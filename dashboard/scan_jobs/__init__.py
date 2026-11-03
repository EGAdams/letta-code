"""Durable scan jobs: one record per physical scan, its immutable artifact, and
the token-protected local façade the StarTrekBridge worker calls.

Dashboard buttons go through ScanJobService.run_recorded (same result as
before, plus a scan_id); the bridge goes through ScanJobService.start.
Concretes are named only in composition.py.
"""
