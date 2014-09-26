########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
# * limitations under the License.
import copy
from cloudify.decorators import operation
from libcloud.compute.types import Provider
from cloudstack_plugin.cloudstack_common import get_cloud_driver


__author__ = 'adaml'


def _get_server_from_context(ctx):
    server = {
        'name': ctx.node_id.replace('_', '-')
    }
    server.update(copy.deepcopy(ctx.properties['server']))
    return server


@operation
def start(ctx, **kwargs):

    ctx.logger.info("initializing {0} cloud driver"
                    .format(Provider.CLOUDSTACK))
    cloud_driver = get_cloud_driver(ctx)
    #Change to debug level
    ctx.logger.info('reading server config from context')
    server_config = _get_server_from_context(ctx)

    name = server_config['name']
    image_id = server_config['image_id']
    size_name = server_config['size']
    keypair_name = server_config['keypair_name']
    #security_groups = server_config['security_groups']
    networks = server_config['networks']
    ipaddress = server_config['ip_address']

    network_list = cloud_driver.ex_list_networks()

    nets = [net for net in network_list if net.name in networks]

    for net in nets:
        ctx.logger.info('id: {0} name: {1}'.format(net.id, net.name))

    ctx.logger.info('getting required size {0}'.format(size_name))
    sizes = [size for size in cloud_driver.list_sizes() if size.name
                                                          == size_name]
    if sizes is None:
        raise RuntimeError(
            'Could not find size with name {0}'.format(size_name))
    size = sizes[0]

    ctx.logger.info('getting required image with ID {0}'.format(image_id))
    images = [template for template in cloud_driver.list_images()
              if image_id == template.id]
    if images is None:
        raise RuntimeError('Could not find image with ID {0}'.format(image_id))
    image = images[0]

    ctx.logger.info(
        "creating server vm with the following details: {0}".format(
            server_config))
    node = cloud_driver.create_node(name=name,
                                    image=image,
                                    size=size,
                                    ex_keyname=keypair_name,
                                    networks=nets,
                                    ex_ip_address=ipaddress)
    ctx.logger.info(
        'vm {0} was started successfully {1}'.format(
            node.name, server_config))

    ctx['instance_id'] = node.id


@operation
def delete(ctx, **kwargs):

    ctx.logger.info("initializing {0} cloud driver"
                    .format(Provider.CLOUDSTACK))
    cloud_driver = get_cloud_driver(ctx)

    instance_id = ctx['instance_id']
    if instance_id is None:
        raise NameError('could not find node ID in runtime context: {0} '
                        .format(instance_id))

    ctx.logger.info('getting node with ID: {0} '.format(instance_id))
    node = _get_node_by_id(cloud_driver, instance_id)
    if node is None:
        raise NameError('could not find node with ID: {0} '
                        .format(instance_id))

    ctx.logger.info('destroying vm with details: {0}'.format(node))
    cloud_driver.destroy_node(node)


@operation
def stop(ctx, **kwargs):

    ctx.logger.info("initializing {0} cloud driver"
                    .format(Provider.CLOUDSTACK))
    cloud_driver = get_cloud_driver(ctx)

    instance_id = ctx.runtime_properties['instance_id']
    if instance_id is None:
        raise RuntimeError(
            'could not find node ID in runtime context: {0} '
            .format(instance_id))

    ctx.logger.info('getting node with ID: {0} '.format(instance_id))
    node = _get_node_by_id(cloud_driver, instance_id)
    if node is None:
        raise RuntimeError('could not find node with ID {0}'
                           .format(instance_id))

    ctx.logger.info('stopping node with details {0}'.format(node))
    cloud_driver.ex_stop(node)


def _get_node_by_id(cloud_driver, instance_id):

    nodes = [node for node in cloud_driver.list_nodes() if instance_id
                                                          == node.id]
    if nodes is None:
        raise RuntimeError('could not find node by ID {0}'.format(instance_id))
        return None

    return nodes[0]


@operation
def get_state(ctx, **kwargs):

    ctx.logger.info("initializing {0} cloud driver"
                    .format(Provider.CLOUDSTACK))
    cloud_driver = get_cloud_driver(ctx)

    instance_id = ctx.runtime_properties['instance_id']

    ctx.logger.info('getting node with ID {0}'.format(instance_id))
    node = _get_node_by_id(cloud_driver, instance_id)
    if node is None:
        return False

    ctx.runtime_properties['ip'] = node.private_ips[0]
    ctx.runtime_properties['ip_address'] = node.private_ips[0]
    ctx.logger.info(
        'instance started successfully with IP {0}'
        .format(ctx.runtime_properties['ip']))
    return True