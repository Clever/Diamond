# coding=utf-8

"""
Collects root and docker disk usage for ECS instances
Inspired by https://github.com/convox/agent/blob/master/disk.go

#### Examples

    # mount point to report as root (default shown)
    root = /mnt/host_root

    # docker url to connect to (default shown)
    docker_url = unix:///var/run/docker.sock

"""

import diamond.collector
import diamond.convertor
from diamond.utils.signals import SIGALRMException
import re
import os

try:
    import docker
except ImportError:
    docker = None


SIZE_REGEX = re.compile("^(\d+(\.\d+)*) ?([kKmMgGtTpP])?[bB]?$")
UNIT_MAP = {
    'k': 1000,
    'm': 1000 * 1000,
    'g': 1000 * 1000 * 1000,
    't':  1000 * 1000 * 1000 * 1000,
    'p': 1000 * 1000 * 1000 * 1000 * 1000
}

ROOT = "root"
DOCKER_URL = "docker_url"


class ECSSpaceCollector(diamond.collector.Collector):
    def get_default_config_help(self):
        config_help = super(ECSSpaceCollector, self).get_default_config_help()
        config_help.update({
            ROOT: "mount point of the root volume",
            DOCKER_URL: "URL of the docker daemon"
        })
        return config_help

    def get_default_config(self):
        config = super(ECSSpaceCollector, self).get_default_config()
        config.update({
            "path": "ecsdisk",
            ROOT: "/mnt/host_root",
            DOCKER_URL: "unix:///var/run/docker.sock"
        })
        return config

    def collect_root_volume(self):
        root_dir = self.config[ROOT]
        if not os.path.isdir(root_dir):
            self.log.error("root path %s does not exist" % (root_dir))
            return None

        root_stats = os.statvfs(root_dir)
        t = root_stats.f_bsize * root_stats.f_blocks
        f = root_stats.f_bsize * root_stats.f_bfree

        total = float(t) / 1024 / 1024 / 1024
        available = float(f) / 1024 / 1024 / 1024
        used = float(t-f) / 1024 / 1024 / 1024
        utilization = used / total * 100

        self.publish_gauge("root.total", total, 2)
        self.publish_gauge("root.available", available, 2)
        self.publish_gauge("root.used", used, 2)
        self.publish_gauge("root.utilization", utilization, 2)

    def parseHumanSize(self, value):
        # Inspired from https://github.com/docker/go-units/blob/master/size.go
        matches = SIZE_REGEX.findall(value)
        if len(matches) == 1:
            num = float(matches[0][0])
            unit = matches[0][-1].lower()
            return int(num * UNIT_MAP[unit])

        raise ValueError("Unable to parse %s" % (value))

    def collect_container_volume(self):
        if docker is None:
            self.log.error('Unable to import docker')
            return

        available = None
        used = None
        total = None

        try:
            client = docker.Client(base_url=self.config[DOCKER_URL],
                                   version='auto')
            info = client.info()
            for status in info.get("DriverStatus"):
                # DriverStatus is a list of lists
                if status[0] == "Data Space Available":
                    available = status[1]
                elif status[0] == "Data Space Total":
                    total = status[1]
                elif status[0] == "Data Space Used":
                    used = status[1]

        except SIGALRMException as e:
            # sigalrm is raised if the collector takes too long
            raise e
        except Exception as e:
            self.log.error("Couldn't collect from docker: %s", e)
            return

        if available and used and total:
            try:
                available = self.parseHumanSize(available)
                used = self.parseHumanSize(used)
                total = self.parseHumanSize(total)
            except ValueError as e:
                self.log.error(str(e))
                return

            available = float(available) / UNIT_MAP['g']
            total = float(total) / UNIT_MAP['g']
            used = float(used) / UNIT_MAP['g']
            utilization = used / total * 100

            self.publish_gauge("docker.available", available, 2)
            self.publish_gauge("docker.used", used, 2)
            self.publish_gauge("docker.total", total, 2)
            self.publish_gauge("docker.utilization", utilization, 2)

    def collect(self):
        self.collect_root_volume()
        self.collect_container_volume()
