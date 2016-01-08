# (c) Copyright 2014,2015 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from oslo_config import cfg
from oslo_log import log
from oslo_utils import importutils
from osha.fencers.common.manager import FencerManager

CONF = cfg.CONF
LOG = log.getLogger(__name__)


class EvacuationManager(object):

    def __init__(self, enable_fencing=True):
        evcuation_conf = CONF.get('evacuation')
        self.driver = importutils.import_object(
            evcuation_conf.get('driver'),
            evcuation_conf.get('wait'),
            evcuation_conf.get('retries'),
            **evcuation_conf.get('options')
        )
        self.enable_fencing = enable_fencing
        self.wait = evcuation_conf.get('wait')
        self.retires = evcuation_conf.get('retries', 1)
        if self.retires <= 0:
            self.retires = 1

    def evacuate(self, nodes):
        # try to disable node
        # @todo needs more error handling like if the status didn't update or
        # we are unable to disable the node ???
        failed_nodes = []  # maintain nodes that are going to fail at any state
        succeeded_nodes = []
        for node in nodes:
            for i in range(0, self.retires):
                status = self._disable_node(node)
                # if True ( node disabled ) break the loop
                if status:
                    break
                else:
                    status = False
            node['status'] = status
            # make sure the disable request was successful
            if not self.driver.get_node_status(node):
                failed_nodes.append(node)
                nodes.remove(node)  # if the node failed at any step no reason
                # to move it to the next step
            else:
                succeeded_nodes.append(node)

        nodes = succeeded_nodes
        if self.enable_fencing:
            fencer = FencerManager(nodes)
            nodes = fencer.fence()

        succeeded_nodes = []
        for node in nodes:
            node['instances'] = self.driver.get_node_instances(node)
            succeeded_nodes.append(node)

        nodes = succeeded_nodes

        # Start evacuation calls ...
        from time import sleep
        for i in range(0, 10):
            try:
                sleep(30)
                evacuated_nodes = self.driver.evacuate_nodes(nodes)
            except Exception as e:
                LOG.error(e)
        return evacuated_nodes

    def _disable_node(self, node):
        if not self.driver.is_node_disabled(node):
                return self.driver.disable_node(node)
        else:
            True

    def reinitialize_driver(self):
        evcuation_conf = CONF.get('evacuation')
        self.driver = importutils.import_object(
            evcuation_conf.get('driver'),
            evcuation_conf.get('wait'),
            evcuation_conf.get('retries'),
            **evcuation_conf.get('options')
        )

