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

from cloudify.decorators import operation

from cloudstack_plugin.cloudstack_common import get_cloud_driver


__author__ = 'uri1803, boul'


@operation
def create(ctx, **kwargs):
    """ Create network with rules.
    """

    cloud_driver = get_cloud_driver(ctx)

    network = {
        'description': None,
        'name': ctx.node_id,
    }

    ctx.logger.debug('reading network configuration.')
    network.update(ctx.properties['network'])

    network_name = network['name']
    zone = network['zone']
    location = get_location(cloud_driver, zone)
    netoffer = network['service_offering']
    network_offering = get_network_offering(cloud_driver, netoffer)

    if 'vpc' in network:
        if network['vpc']:
            vpc = get_vpc_id(cloud_driver, network['vpc'])
            ctx.logger.info('DEBUG: VPC id: '.format(vpc.id))
    else:
        vpc = None

    ctx.logger.info('Current node {0}{1}'.format(ctx.node_id, ctx.properties))

    ctx['network_id'] = ctx.node_id

    if not _network_exists(cloud_driver, network_name):

        if vpc:
            ctx.logger.info('creating network: {0} in VPC with ID: {1}'.
                            format(network_name, vpc.id))

            net = cloud_driver.ex_create_network(
                display_text=network_name,
                name=network_name,
                network_offering=network_offering,
                location=location,
                gateway=network['gateway'],
                netmask=network['netmask'],
                vpc_id=vpc.id)

            # Create ACL for the network if it's is part of a VPC
            acl_list = create_acl_list(cloud_driver, network_name,
                                       vpc.id, net.id)

            if 'firewall' in ctx.properties:
                firewall_config = ctx.properties['firewall']

                for acl in firewall_config:
                    acl_cidr = acl.get('cidr')
                    acl_protocol = acl.get('protocol')
                    acl_ports = acl.get('ports')
                    acl_type = acl.get('type')

                    for port in acl_ports:
                        create_acl(cloud_driver, acl_protocol, acl_list.id,
                                   acl_cidr, port, port, acl_type)

        else:
            ctx.logger.info('creating network: {0}'.format(network_name))

            net = cloud_driver.ex_create_network(
                display_text=network_name,
                name=network_name,
                network_offering=network_offering,
                location=location)

            if 'firewall' in ctx.properties:
                firewall_config = ctx.properties['firewall']

                for rule in firewall_config:
                    rule_cidr = rule.get('cidr')
                    rule_protocol = rule.get('protocol')
                    rule_ports = rule.get('ports')

                    for port in rule_ports:
                        _create_egress_rules(cloud_driver, net.id,
                                             rule_cidr,
                                             rule_protocol,
                                             port, port)

    else:
        ctx.logger.info('using existing management network {0}'.
                        format(network_name))
        net = get_network(cloud_driver, network_name)

    ctx['network_id'] = net.id
    ctx['network_name'] = net.name


@operation
def delete(ctx, **kwargs):

    network_name = ctx.runtime_properties['network_name']
    cloud_driver = get_cloud_driver(ctx)
    network = get_network(cloud_driver, network_name)

    try:

        cloud_driver.ex_delete_network(network)
    except Exception as e:
        ctx.logger.warn('network {0} may not have been deleted: {1}'
                        .format(ctx.runtime_properties['network_name'], str(e)))
        return False
        pass

    return True


def _network_exists(cloud_driver, network_name):
    exists = get_network(cloud_driver, network_name)
    if not exists:
        return False
    return True


def get_network(cloud_driver, network_name):
    networks = [net for net in cloud_driver
        .ex_list_networks() if net.name == network_name]

    if networks.__len__() == 0:
        return None
    return networks[0]


def get_location(cloud_driver, location_name):
    locations = [location for location in cloud_driver
        .list_locations() if location.name == location_name]
    if locations.__len__() == 0:
        return None
    return locations[0]


def get_network_offering(cloud_driver, netoffer_name):
    netoffers = [offer for offer in cloud_driver
        .ex_list_network_offerings() if offer.name == netoffer_name]
    if netoffers.__len__() == 0:
        return None
    return netoffers[0]


def get_vpc_id(cloud_driver, vpc_name):
    vpcs = [vpc for vpc in cloud_driver
        .ex_list_vpcs() if vpc.name == vpc_name]
    if vpcs.__len__() == 0:
        return None
    return vpcs[0]


def create_acl_list(cloud_driver, name, vpc_id, network_id):
    acllist = cloud_driver.ex_create_network_acllist(
        name=name,
        vpc_id=vpc_id,
        description=name)

    # Replace the newly created ACL list on to the network
    cloud_driver.ex_replace_network_acllist(
        acl_id=acllist.id,
        network_id=network_id)

    return acllist


def create_acl(cloud_driver, protocol, acl_id,
               cidr_list, start_port, end_port, traffic_type):
    acl = cloud_driver.ex_create_network_acl(
        protocol=protocol,
        acl_id=acl_id,
        cidr_list=cidr_list,
        start_port=start_port,
        end_port=end_port,
        traffic_type=traffic_type)
    return acl


def _create_egress_rules(cloud_driver, network_id, cidr_list, protocol,
                         start_port, end_port):

    cloud_driver.ex_create_egress_firewall_rule(
        network_id=network_id,
        cidr_list=cidr_list,
        protocol=protocol,
        start_port=start_port,
        end_port=end_port)