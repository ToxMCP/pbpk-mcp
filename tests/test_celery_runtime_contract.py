from __future__ import annotations

import unittest

from mcp_bridge.config import AppConfig
from mcp_bridge.services.celery_app import configure_celery
from mcp_bridge.services.job_service import CeleryJobService, JobStatus


class CeleryRuntimeContractTests(unittest.TestCase):
    def test_configure_celery_tracks_started_tasks(self) -> None:
        app = configure_celery(AppConfig())

        self.assertTrue(app.conf.task_track_started)

    def test_received_state_is_treated_as_running(self) -> None:
        service = CeleryJobService.__new__(CeleryJobService)

        self.assertEqual(service._map_state("RECEIVED"), JobStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()
