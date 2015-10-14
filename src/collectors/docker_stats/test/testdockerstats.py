from test import CollectorTestCase
from test import run_only
from test import get_collector_config
from mock import Mock
from mock import MagicMock
from mock import patch

from diamond.collector import Collector
from docker_stats import DockerStatsCollector

def run_only_if_docker_is_available(func):
  try:
    import docker
  except ImportError:
    docker = None
    pred = lambda: docker is not None
    return run_only(func, pred)


def get_client_mock():
  client_mock = Mock()
  client_mock.containers.return_value = [
    {
      u'Id': u'146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec'
    }]
  stats_mock = MagicMock()
  client_mock.stats.return_value = stats_mock
  stats_mock.next.side_effect = [
    {
      u'cpu_stats': {
        u'cpu_usage': {
          u'percpu_usage': [0,
                            0,
                            0,
                            0],
        }
      },
      u'memory_stats': {
        u'stats': {
          u'total_rss': 100,
        }
      },
      u'network': {
        u'rx_bytes': 100,
        u'tx_bytes': 100,
      }
    },
    {
      u'cpu_stats': {
        u'cpu_usage': {
          u'percpu_usage': [10000000,
                            20000000,
                            30000000,
                            40000000],
        }
      },
      u'memory_stats': {
        u'stats': {
          u'total_rss': 200,
        }
      },
      u'network': {
        u'rx_bytes': 200,
        u'tx_bytes': 200,
      }
    }
  ]

  client_mock.inspect_container.return_value = {
    u'Id': u'146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec',
    u'Name': u'test',
    u'Config': {
      u'Env': ["TEST=/new/name/"]
    }
  }
  return client_mock


class TestDockerStatsCollector(CollectorTestCase):
  def setUp(self):
    config = get_collector_config('DockerStatsCollector', {
      'client_url': 'localhost:4243',
      'name_from_env': None,
      'interval': 1,
    })
    self.collector = DockerStatsCollector(config, None)

  def test_import(self):
    self.assertTrue(DockerStatsCollector)

  @patch.object(Collector, 'publish')
  @patch('docker.Client')
  def test_should_publish_values_correctly(self, docker_client_mock, publish_mock):
    client_mock = get_client_mock()
    docker_client_mock.return_value = client_mock
    self.collector.collect()
    metrics = {
      'test.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.mem.rss': 100,
      'test.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.net.tx_bytes': 100,
      'test.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.net.rx_bytes': 100,
    }
    self.assertPublishedMany(publish_mock, metrics)

    self.collector.collect()
    metrics = {
      'test.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.mem.rss': 200,
      'test.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.net.tx_bytes': 200,
      'test.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.net.rx_bytes': 200,
      'test.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.cpu0.user': 1,
      'test.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.cpu1.user': 2,
      'test.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.cpu2.user': 3,
      'test.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.cpu3.user': 4,
    }
    self.assertPublishedMany(publish_mock, metrics)


class TestDockerStatsCollectorWithEnv(CollectorTestCase):
  def setUp(self):
    config = get_collector_config('DockerStatsCollector', {
      'client_url': 'localhost:4243',
      'name_from_env': 'TEST',
      'interval': 1,
    })
    self.collector = DockerStatsCollector(config, None)

  def test_import(self):
    self.assertTrue(DockerStatsCollector)

  @patch.object(Collector, 'publish')
  @patch('docker.Client')
  def test_should_publish_values_correctly(self, docker_client_mock, publish_mock):
    client_mock = get_client_mock()
    docker_client_mock.return_value = client_mock
    self.collector.collect()
    metrics = {
      'new.name.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.mem.rss': 100,
      'new.name.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.net.tx_bytes': 100,
      'new.name.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.net.rx_bytes': 100,
    }
    self.assertPublishedMany(publish_mock, metrics)

    self.collector.collect()
    metrics = {
      'new.name.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.mem.rss': 200,
      'new.name.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.net.tx_bytes': 200,
      'new.name.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.net.rx_bytes': 200,
      'new.name.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.cpu0.user': 1,
      'new.name.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.cpu1.user': 2,
      'new.name.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.cpu2.user': 3,
      'new.name.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.cpu3.user': 4,
    }
    self.assertPublishedMany(publish_mock, metrics)

class TestDockerStatsCollectorWithoutReplaceSlashes(CollectorTestCase):
  def setUp(self):
    config = get_collector_config('DockerStatsCollector', {
      'client_url': 'localhost:4243',
      'name_from_env': 'TEST',
      'interval': 1,
      'sanitize_slashes': False,
    })
    self.collector = DockerStatsCollector(config, None)

  def test_import(self):
    self.assertTrue(DockerStatsCollector)

  @patch.object(Collector, 'publish')
  @patch('docker.Client')
  def test_should_publish_values_correctly(self, docker_client_mock, publish_mock):
    client_mock = get_client_mock()
    docker_client_mock.return_value = client_mock
    self.collector.collect()
    metrics = {
      '/new/name/.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.mem.rss': 100,
      '/new/name/.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.net.tx_bytes': 100,
      '/new/name/.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.net.rx_bytes': 100,
    }
    self.assertPublishedMany(publish_mock, metrics)

    self.collector.collect()
    metrics = {
      '/new/name/.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.mem.rss': 200,
      '/new/name/.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.net.tx_bytes': 200,
      '/new/name/.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.net.rx_bytes': 200,
      '/new/name/.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.cpu0.user': 1,
      '/new/name/.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.cpu1.user': 2,
      '/new/name/.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.cpu2.user': 3,
      '/new/name/.146979a5328952af505cd43123b45b06c38db8679aaadb2a4c18ad699a5cbeec.cpu3.user': 4,
    }
    self.assertPublishedMany(publish_mock, metrics)
