"""
The DockerStatsCollector collects stats from the docker daemon about currently running
containers.
"""

import diamond.collector
from diamond.utils.signals import SIGALRMException

try:
  import docker
except ImportError:
  docker = None

def env_list_to_dict(env_list):
  env_dict = {}
  for pair in env_list:
    tokens = pair.split("=",1)
    env_dict[tokens[0]] = tokens[1]
  return env_dict

def sanitize_delim(name, delim):
  return ".".join(name.strip(delim).split(delim))

class DockerStatsCollector(diamond.collector.Collector):

  def get_default_config_help(self):
    config_help = super(DockerStatsCollector, self).get_default_config_help()
    config_help.update({
      'client_url': 'The url to connect to the docker daemon',
      'name_from_env': 'If specified, use the named environment variable to populate container name',
      'sanitize_slashes': 'Replace slashes in container name with \".\"\'s, defaults to True',
      'ecs_mode': 'Enables pulling container name and env from \'tag\' docker label, and using task ARN instead of container id, defaults to False',
    })
    return config_help

  def get_default_config(self):
    """
    Returns the default collector settings
    """
    config = super(DockerStatsCollector, self).get_default_config()
    config.update({
      'client_url': 'unix://var/run/docker.sock',
      'name_from_env': None,
      'path': 'docker',
      'sanitize_slashes': True,
      'ecs_mode': False,
    })
    return config

  def collect(self):
    """
    Collect docker stats
    """

    # Require docker client lib to get stats
    if docker is None:
      self.log.error('Unable to import docker')
      return None

    try:
      client = docker.Client(base_url=self.config['client_url'], version='auto')
      container_ids = [container['Id'] for container in client.containers()]

      for container_id in container_ids:
        container = client.inspect_container(container_id)
        name = container['Name']
        idlabel = container_id[:12]
        if self.config['name_from_env']:
          # Grab name from environment variable if configured
          env_dict = env_list_to_dict(container['Config']['Env'])
          name = env_dict.get(self.config['name_from_env'], name)
        if self.config['sanitize_slashes']:
          name = sanitize_delim(name, "/")
        if self.config['ecs_mode']:
          labels = container['Config']['Labels']
          tag = labels.get('tag', '')
          arn = labels.get('com.amazonaws.ecs.task-arn', '')
          if arn and tag:
            # only grab the first part of the task UUID
            parts = arn.split("/")
            idlabel = parts[1][:8]
            name = sanitize_delim(tag, "--")


        metrics_prefix = '.'.join([name, idlabel, "docker"])
        stats = client.stats(container_id, True, stream=False)

        # CPU Stats
        for ix, cpu_time in enumerate(stats['cpu_stats']['cpu_usage']['percpu_usage']):
          metric_name = '.'.join([metrics_prefix, 'cpu' + str(ix), 'user'])
          self.publish(metric_name,
                       int(self.derivative(metric_name,
                                           cpu_time / 10000000.0,
                                           diamond.collector.MAX_COUNTER)))
        # Total CPU
        metric_name = '.'.join([metrics_prefix, 'cpu_total', 'user'])
        self.publish(metric_name,
                     int(self.derivative(metric_name,
                                         stats['cpu_stats']['cpu_usage']['total_usage'] / 10000000.0,
                                         diamond.collector.MAX_COUNTER)))

        # Memory Stats
        metric_name = '.'.join([metrics_prefix, 'mem', 'rss'])
        self.publish(metric_name,
                     stats['memory_stats']['stats']['total_rss'])

        metric_name = '.'.join([metrics_prefix, 'mem', 'limit'])
        self.publish(metric_name,
                     stats['memory_stats']['limit'])


        # Network Stats
        networks = stats.get('networks', [])
        if not networks:
          networks = {'eth0': stats['network']}

        for network_name, network in networks.iteritems():
          for stat in [u'rx_bytes', u'tx_bytes']:
            self.publish('.'.join([metrics_prefix, 'net', network_name, stat]),
                         network[stat])
      return True

    except SIGALRMException as e:
      # sigalrm is raised if the collector takes too long
      raise e
    except Exception as e:
      self.log.error("Couldn't collect from docker: %s", e)
      return None
