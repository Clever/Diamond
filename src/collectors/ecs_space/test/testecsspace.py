#!/usr/bin/python
# coding=utf-8
################################################################################

from test import CollectorTestCase
from test import get_collector_config
from test import unittest
from test import run_only
from mock import Mock
from mock import patch

from diamond.collector import Collector
from ecs_space import ECSSpaceCollector


def run_only_if_docker_is_available(func):
    try:
        import docker
    except ImportError:
        docker = None
        pred = lambda: docker is not None
        return run_only(func, pred)


def get_client_mock():
    client_mock = Mock()
    client_mock.info.return_value = {
        "DriverStatus": [
            ["Data Space Available", "2 GB"],
            ["Data Space Total", "10 GB"],
            ["Data Space Used", "8 GB"]
        ]
    }
    return client_mock


class TestECSSpaceCollector(CollectorTestCase):
    def setUp(self):
        config = get_collector_config('DockerStatsCollector', {
            'docker_url': 'localhost:4243',
            'root': '/',
            'interval': 1,
        })
        self.collector = ECSSpaceCollector(config, None)

    def test_import(self):
        self.assertTrue(ECSSpaceCollector)

    def test_parse_human_size(self):
        # Test GB strings
        self.assertEqual(2 * 1000 * 1000 * 1000,
                         self.collector.parseHumanSize("2 GB"))
        self.assertEqual(2.34 * 1000 * 1000 * 1000,
                         self.collector.parseHumanSize("2.34 GB"))

        # test MB strings
        self.assertEqual(215 * 1000 * 1000,
                         self.collector.parseHumanSize("215 MB"))
        self.assertEqual(174.5 * 1000 * 1000,
                         self.collector.parseHumanSize("174.5 MB"))

    @run_only_if_docker_is_available
    @patch.object(Collector, 'publish')
    @patch('docker.Client')
    def test_docker_space_collection(self, docker_client_mock, publish_mock):
        client_mock = get_client_mock()
        docker_client_mock.return_value = client_mock

        # run the collector with a mock docker client and publish mock
        self.collector.collect()

        # verify that the expected metrics were published to the mock
        # These values are based on those queried from the mock docker
        # client
        metrics = {
            'docker.available': (2.0, 2),
            'docker.used': (8.0, 2),
            'docker.total': (10.0, 2),
            'docker.utilization': (80.0, 2),
        }
        self.assertPublishedMany(publish_mock, metrics)

    @patch('os.path.isdir', Mock(return_value=True))
    @patch.object(Collector, 'publish')
    def test_root_collection(self, publish_mock):
        statvfs_mock = Mock()
        statvfs_mock.f_bsize = 4096
        statvfs_mock.f_frsize = 4096
        statvfs_mock.f_blocks = 360540255
        statvfs_mock.f_bfree = 285953527
        statvfs_mock.f_bavail = 267639130
        statvfs_mock.f_files = 91578368
        statvfs_mock.f_ffree = 91229495
        statvfs_mock.f_favail = 91229495
        statvfs_mock.f_flag = 4096
        statvfs_mock.f_namemax = 255
        os_statvfs_mock = patch('os.statvfs', Mock(return_value=statvfs_mock))

        # run the collector with these mocks:
        #   os.path.isdir()
        #   os.statvfs()
        #   publish_*()
        os_statvfs_mock.start()
        self.collector.collect()
        os_statvfs_mock.stop()

        # the published metrics should map to the values reported
        # by os.statvfs()
        metrics = {
            'root.used': (284.525, 2),
            'root.available': (1090.826, 2),
            'root.total': (1375.351, 2),
            'root.utilization': (20.687, 2)
        }
        self.assertPublishedMany(publish_mock, metrics)

################################################################################
if __name__ == "__main__":
    unittest.main()
