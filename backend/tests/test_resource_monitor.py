"""Unit tests for hermeshq.services.resource_monitor."""

import unittest
from unittest.mock import patch

from hermeshq.services.resource_monitor import ResourceMonitor


class TestResourceMonitorGetSemaphoreInfo(unittest.TestCase):
    """Tests for ResourceMonitor.get_semaphore_info."""

    @patch("hermeshq.services.resource_monitor.get_settings")
    def test_default_settings_4_active_utilization_50(self, mock_get_settings):
        mock_get_settings.return_value.concurrency_semaphore = 8
        monitor = ResourceMonitor()
        result = monitor.get_semaphore_info(4)
        self.assertEqual(result["current"], 8)
        self.assertEqual(result["active_tasks"], 4)
        self.assertEqual(result["max_tasks"], 8)
        self.assertEqual(result["utilization_pct"], 50)

    @patch("hermeshq.services.resource_monitor.get_settings")
    def test_zero_active_utilization_0(self, mock_get_settings):
        mock_get_settings.return_value.concurrency_semaphore = 8
        monitor = ResourceMonitor()
        result = monitor.get_semaphore_info(0)
        self.assertEqual(result["active_tasks"], 0)
        self.assertEqual(result["max_tasks"], 8)
        self.assertEqual(result["utilization_pct"], 0)

    @patch("hermeshq.services.resource_monitor.get_settings")
    def test_max_active_utilization_100(self, mock_get_settings):
        mock_get_settings.return_value.concurrency_semaphore = 8
        monitor = ResourceMonitor()
        result = monitor.get_semaphore_info(8)
        self.assertEqual(result["active_tasks"], 8)
        self.assertEqual(result["max_tasks"], 8)
        self.assertEqual(result["utilization_pct"], 100)

    @patch("hermeshq.services.resource_monitor.get_settings")
    def test_returns_all_expected_keys(self, mock_get_settings):
        mock_get_settings.return_value.concurrency_semaphore = 8
        monitor = ResourceMonitor()
        result = monitor.get_semaphore_info(4)
        expected_keys = {"current", "active_tasks", "max_tasks", "utilization_pct"}
        self.assertEqual(set(result.keys()), expected_keys)


class TestResourceMonitorCalculateSizing(unittest.TestCase):
    """Tests for ResourceMonitor.calculate_sizing."""

    def test_1_agent(self):
        result = ResourceMonitor().calculate_sizing(1)
        self.assertEqual(result["agents"], 1)
        self.assertEqual(result["concurrent"], 1)
        self.assertEqual(result["semaphore"], 1)
        self.assertEqual(result["ram_backend_mb"], 550)
        self.assertEqual(result["ram_postgres_mb"], 210)
        self.assertEqual(result["cpu_needed"], 1)
        self.assertEqual(result["disk_gb"], 6)

    def test_10_agents(self):
        result = ResourceMonitor().calculate_sizing(10)
        self.assertEqual(result["agents"], 10)
        self.assertEqual(result["concurrent"], 5)
        self.assertEqual(result["semaphore"], 5)
        self.assertEqual(result["ram_backend_mb"], 750)
        self.assertEqual(result["ram_postgres_mb"], 250)
        self.assertEqual(result["cpu_needed"], 1)
        self.assertEqual(result["disk_gb"], 20)

    def test_100_agents(self):
        result = ResourceMonitor().calculate_sizing(100)
        self.assertEqual(result["agents"], 100)
        self.assertEqual(result["concurrent"], 50)
        self.assertEqual(result["semaphore"], 50)
        self.assertEqual(result["ram_backend_mb"], 3000)
        self.assertEqual(result["ram_postgres_mb"], 700)
        self.assertEqual(result["cpu_needed"], 9)
        self.assertEqual(result["disk_gb"], 155)

    def test_0_agents_concurrent_is_1(self):
        result = ResourceMonitor().calculate_sizing(0)
        self.assertEqual(result["agents"], 0)
        self.assertEqual(result["concurrent"], 1)
        self.assertEqual(result["semaphore"], 1)
        self.assertEqual(result["cpu_needed"], 1)
        self.assertEqual(result["disk_gb"], 5)

    def test_returns_all_expected_keys(self):
        result = ResourceMonitor().calculate_sizing(10)
        expected_keys = {
            "agents",
            "concurrent",
            "semaphore",
            "ram_backend_mb",
            "ram_postgres_mb",
            "cpu_needed",
            "disk_gb",
        }
        self.assertEqual(set(result.keys()), expected_keys)


if __name__ == "__main__":
    unittest.main()
