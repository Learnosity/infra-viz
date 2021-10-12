#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import json
import csv
from datetime import date, datetime
from hashlib import sha1

import boto3


logger = logging.getLogger('main')
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# ch.setLevel(logging.INFO)

logger.addHandler(ch)



node_fields = [
    'type',
    'name',
    'description',
    'weight'
]

edge_fields = [
    'from_type',
    'from_name',
    'edge',
    'to_type',
    'to_name',
    'weight'
]


def make_dirs(folder):
    ''' Make directories and subdirectories for a location '''
    if not os.path.exists(folder):
        os.makedirs(folder)

def write_json_file(filename, obj):
    ''' Save an object as a json file '''
    with open(filename, 'w+') as file:
        file.write(json.dumps(obj, default=json_serial))
        logger.debug("wrote file: %s", filename)


def read_json_file(filename):
    ''' Read a json file back as an object '''
    with open(filename, 'r') as file:
        obj = json.loads(file.read())
        logger.debug("read file: %s", filename)
        return obj


def write_csv(nodes, filename, fieldnames):
    ''' Write out all the nodes to a CSV File '''

    with open(filename, 'w+', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(nodes)

    logger.debug("wrote file: %s", filename)


def json_serial(obj):
    """
    JSON serializer for objects not serializable by default json code
    """

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    raise TypeError('Type {} not serializable'.format(type(obj)))


def fmt_dns(name):
    ''' Remove any trailing dots from a dns name and format to lower case '''
    return name.lower().rstrip('.').replace('dualstack.', '')


def new_node(**kwargs):
    ''' Creates a new node and will populate the fields that match in kwargs '''
    return {key: kwargs.get(key, None) for key in node_fields}


def new_edge(**kwargs):
    ''' Creates a new edge and will populate the fields that match in kwargs '''
    return {key: kwargs.get(key, None) for key in edge_fields}


def add_update_node(existing_nodes,node):
    '''
    Adds a node - or increments the weight if a duplicate
    '''
    node_name = node['type']+'_'+node['name']
    if node_name in existing_nodes:
        existing_nodes[node_name]['weight'] += 1
    else:
        existing_nodes[node_name] = node
        existing_nodes[node_name]['weight'] = 1


def query_aws(api, method, region, cached=True, **kwargs):
    '''
    Query AWS API using api and method to call for a given region
    Cache the results to the filesystem for faster re-run. Can flush cache
    with flag when required
    '''
    # build up the filename
    filename = [api, method, region]

    # add kwargs as a hash to the filename
    filename.append(sha1(str(kwargs).encode()).hexdigest())

    # construct filename and add path
    filename = os.path.join('cache', '-'.join(filename)) + '.json'

    try:
        # look for a cache file, return result if found
        if cached:
            return read_json_file(filename)

    except IOError:
        pass

    # connect to AWS and grab the data
    client = boto3.client(api, region_name=region)
    if api == 's3' and method == 'list_buckets':
        # s3 list_buckets has no paginator. :/
        records = client.list_buckets().get('Buckets', [])
    elif api == 'sqs' and method == 'list_queues':
        # s3 list_buckets has no paginator. :/
        records = client.list_queues().get('QueueUrls', [])
    elif api == 'elbv2' and method == 'describe_target_health':
        # elbv2 describe_target_health has no paginator. :/
        records = client.describe_target_health(TargetGroupArn=kwargs['TargetGroupArn'])
    else:
        # just use paginator for the method call
        paginator = client.get_paginator(method)
        # get all records as we might overflow maxitems
        records = paginator.paginate(**kwargs).build_full_result()

    write_json_file(filename, records)

    return records


def process_dns_records(zone_id, region, nodes, edges):
    """
    Find nodes and edges in the DNS records
    """
    # get records for zone_id and region
    records = query_aws('route53', 'list_resource_record_sets', region,
                        HostedZoneId=zone_id).get('ResourceRecordSets', [])

    for record in records:
        name = fmt_dns(record['Name'])
        ns_type = record['Type']
        ns_value = fmt_dns(
            record.get('ResourceRecords', [{}])[0].get('Value', '')
        )
        ns_alias = fmt_dns(
            record.get('AliasTarget', {}).get('DNSName', '')
        )

        logger.debug('  - %s %s',name, ns_type)

        if ns_type in ['CNAME', 'A']:
            # add name node to the nodes
            add_update_node(
                nodes,
                new_node(
                    type='dns',
                    name=name,
                    description=ns_type,
                )
            )

            # add the edge value for the CNAME
            edges.append(
                new_edge(
                    from_type='dns',
                    from_name=name,
                    edge='depends',
                    to_type='dns',
                    to_name=ns_alias if ns_alias else ns_value,
                    weight=record.get('Weight', 1)
                )
            )

        if ns_type == 'A':
            # add edge node
            add_update_node(
                nodes,
                new_node(
                    type='dns',
                    name=ns_alias if ns_alias else ns_value,
                    description=ns_type,
                )
            )

        # check node is alive
        if ns_alias:
            # TODO: check alias
            pass

        if ns_value:
            # TODO: check value
            pass


def process_cloudfront(region, nodes, edges):
    """
    Find all the cloudfront CDN nodes
    """
    records = query_aws('cloudfront', 'list_distributions', region)
    records = records.get('DistributionList', {}).get('Items', {})

    for instance in records:
        # add a cloudfront node
        add_update_node(
            nodes,
            new_node(
                type='cloudfront',
                name=fmt_dns(instance['DomainName']),
                description=" ".join([instance['Id'], instance['HttpVersion']]),
                region='global'
            )
        )

        # Add the DNS node for it that is auto created
        add_update_node(
            nodes,
            new_node(
                type='dns',
                name=fmt_dns(instance['DomainName']),
                description='A',
            )
        )

        # add an edge for the DNS cloudfront
        edges.append(
            new_edge(
                from_type='dns',
                from_name=fmt_dns(instance['DomainName']),
                edge='depends',
                to_type='cloudfront',
                to_name=fmt_dns(instance['DomainName']),
                weight=1
            )
        )

        # Loop through each of the origins and link them to endpoints
        for origin in instance['Origins']['Items']:
            edges.append(
                new_edge(
                    from_type='cloudfront',
                    from_name=fmt_dns(instance['DomainName']),
                    edge='depends',
                    to_type='dns',
                    to_name=fmt_dns(origin['DomainName']),
                    weight=1
                )
            )




def process_ec2s(region, nodes, edges):
    """
    Find all the EC2 instances in the given region
    """
    # we're only interested in running instances
    records = query_aws(
        'ec2',
        'describe_instances',
        region,
        Filters=[
            {'Name': 'instance-state-name', 'Values': ['running']}
        ]
    )
    records = records.get('Reservations', [])

    for resv in records:
        for instance in resv.get('Instances'):
            # get instances takes into a dict
            inst_tags = {t['Key']: t['Value'] for t in instance.get('Tags')}

            description = ' '.join(
                [
                    inst_tags.get('Name', ''),
                    inst_tags.get('InstRole', ''),
                    instance.get('InstanceType', '')
                ]
            )

            # add ec2 node
            add_update_node(
                nodes,
                new_node(
                    type='ec2',
                    name=instance['InstanceId'],
                    description=description,
                    region=region
                )
            )

            # Removed Private IP - as not adding much value at this point
            # add_update_node(
            #     nodes,
            #     new_node(
            #         type='IP',
            #         name=instance['PrivateIpAddress'],
            #         description=description,
            #         region=region
            #     )
            # )

            # # add the private ip edge
            # edges.append(
            #     new_edge(
            #         from_type='ec2',
            #         from_name=instance['InstanceId'],
            #         edge='depends',
            #         to_type='IP',
            #         to_name=instance['PrivateIpAddress'],
            #         weight=1
            #     )
            # )

            if instance.get('PublicIpAddress'):
                add_update_node(
                    nodes,
                    new_node(
                        type='dns',
                        name=instance['PublicIpAddress'],
                        description=description,
                        region=region
                    )
                )
                
                # add the public ip edge
                edges.append(
                    new_edge(
                        from_type='ec2',
                        from_name=instance['InstanceId'],
                        edge='depends',
                        to_type='dns',
                        to_name=instance['PublicIpAddress'],
                        weight=1
                    )
                )


def process_elbs(region, nodes, edges):
    """
    Find all the ELB nodes
    """
    records = query_aws('elb', 'describe_load_balancers', region)

    for elb in records['LoadBalancerDescriptions']:
        name = fmt_dns(elb['DNSName'])

        add_update_node(
            nodes,
            new_node(
                type='elb',
                name=name,
                description=elb['LoadBalancerName'],
                region=region
            )
        )

        # Add Edges - of dependent instances
        for instances in elb['Instances']:
            edges.append(
                new_edge(
                    from_type='elb',
                    from_name=name,
                    edge='depends',
                    to_type='ec2',
                    to_name=instances['InstanceId'],
                    weight=1
                )
            )

def process_elbsv2(region, nodes, edges):
    """
    Find all the ELB nodes
    """
    records = query_aws('elbv2', 'describe_load_balancers', region, cached=False)

    print("ELBS")
    print(records)
    for elb in records['LoadBalancers']:
        name = fmt_dns(elb['DNSName'])

        print(elb)
        add_update_node(
            nodes,
            new_node(
                type='elb',
                name=name,
                description=elb['LoadBalancerName'],
                region=region
            )
        )

        # Add the DNS node for it
        add_update_node(
            nodes,
            new_node(
                type='dns',
                name=fmt_dns(elb['DNSName']),
                description='A',
            )
        )

        # add an edge for the RDS to DNS link
        edges.append(
            new_edge(
                from_type='dns',
                from_name=fmt_dns(elb['DNSName']),
                edge='depends',
                to_type='elb',
                to_name=name,
                weight=1
            )
        )


        # TODO - this can likely come out to it's own top level
        target_groups  = query_aws('elbv2',
                                    'describe_target_groups', 
                                    region,
                                    # cached=False,
                                    LoadBalancerArn=elb['LoadBalancerArn']
                                    )

        for target_group in target_groups['TargetGroups']:
            print(target_group)

            print(target_group['TargetGroupArn'])

            # Loop over each target
            target_healths = query_aws('elbv2',
                                    'describe_target_health', 
                                    region,
                                    # cached=False,
                                    TargetGroupArn=target_group['TargetGroupArn']
                                    )
            for target in target_healths['TargetHealthDescriptions']:
                # Connect ELB to the target instance
                edges.append(
                    new_edge(
                        from_type='elb',
                        from_name=name,
                        edge='depends',
                        to_type='ec2',
                        to_name=target['Target']['Id'],
                        weight=1
                    )
                )


def process_rds(region, nodes, edges):
    """
    Find all the RDS nodes
    """
    records = query_aws('rds', 'describe_db_instances', region)

    for rds in records.get('DBInstances'):
        name = fmt_dns(rds.get('Endpoint', {}).get('Address'))
        description = ' '.join(
            [
                rds['DBInstanceIdentifier'],
                rds['DBInstanceClass'],
                rds['Engine']
            ]
        )

        # Add the RDS Node
        add_update_node(
            nodes,
            new_node(
                type='rds',
                name=name,
                description=description,
                region=region
            )
        )

        # Add the DNS node for it
        add_update_node(
            nodes,
            new_node(
                type='dns',
                name=name,
                description='A',
                region=region
            )
        )

        # add an edge for the RDS to DNS link
        edges.append(
            new_edge(
                from_type='dns',
                from_name=name,
                edge='depends',
                to_type='rds',
                to_name=name,
                weight=1
            )
        )



def process_asgs(region, nodes, edges):
    """
    Find all ASGs
    """
    records = query_aws('autoscaling', 'describe_auto_scaling_groups', region)

    for asg in records['AutoScalingGroups']:
        name = fmt_dns(asg.get('AutoScalingGroupName'))
        description = ' '.join(
            [
                asg['AutoScalingGroupName']
            ]
        )

        add_update_node(
            nodes,
            new_node(
                type='asg',
                name=name,
                description=description,
                region=region
            )
        )

        # connect any ELBs
        for elb in asg.get('LoadBalancerNames', []):
            edges.append(
                new_edge(
                    from_type='asg',
                    from_name=name,
                    edge='depends',
                    to_type='elb',
                    to_name=fmt_dns(elb),
                    weight=1
                )
            )

        # connect instances
        # Add Edges - of dependent instances
        for ec2 in asg.get('Instances', []):
            edges.append(
                new_edge(
                    from_type='asg',
                    from_name=name,
                    edge='depends',
                    to_type='ec2',
                    to_name=ec2.get('InstanceId'),
                    weight=1
                )
            )


def process_redshift(region, nodes, edges):
    """
    Find all the redshift clusters
    """
    records = query_aws('redshift', 'describe_clusters', region)

    for redshift in records['Clusters']:
        name = fmt_dns(redshift.get('Endpoint', {}).get('Address'))
        description = ' '.join(
            [
                redshift['ClusterIdentifier'],
                redshift['NodeType']
            ]
        )

        add_update_node(
            nodes,
            new_node(
                type='redshift',
                name=name,
                description=description,
                region=region
            )
        )


def process_elasticache(region, nodes, edges):
    """
    Find all the elasticache clusters
    """
    records = query_aws(
        'elasticache',
        'describe_cache_clusters',
        region,
        ShowCacheNodeInfo=True
    )

    for cache in records['CacheClusters']:
        description = ' '.join(
            [
                cache['CacheClusterId'],
                cache['CacheNodeType'],
                cache['Engine']
            ]
        )

        if 'ConfigurationEndpoint' in cache:
            name = cache.get('ConfigurationEndpoint', {}).get('Address')
        else:
            name = fmt_dns(
                cache.get('CacheNodes', [{}])[0].get('Endpoint', {}).get('Address')
            )

        add_update_node(
            nodes,
            new_node(
                type='elasticache',
                name=name,
                description=description,
                region=region
            )
        )

def process_sqs(region, nodes, edges):
    """
    Find all the SQS Queues
    """
    records = query_aws(
        'sqs',
        'list_queues',
        region
    )

    for queue in records:
        name = queue.rpartition('/')[2]
        add_update_node(
            nodes,
            new_node(
                type='sqs',
                name=name,
                description=queue,
                region=region
            )
        )


def process_s3(region, nodes, edges):
    """
    Find all the S3 buckets
    """
    records = query_aws(
        's3',
        'list_buckets',
        region
    )

    for bucket in records:
        # logger.info('*****&* {}'.format(region))
        add_update_node(
            nodes,
            new_node(
                type='s3',
                name=bucket['Name'],
                description=bucket['Name'],
                region='global'
            )
        )


def main():
    ''' Main function to kick it all off '''

    nodes = {}
    edges = []


    region_list = [
        'us-west-1', 'us-west-2', 'us-east-1', 'us-east-2', 'ap-southeast-2'
        # 'us-west-1'
    ]

    # used for "global" AWS services
    region = 'us-east-1'

    nodes_filename = 'data/nodes.csv'
    edges_filename = 'data/edges.csv'

    # Make dirs for storage
    make_dirs('data')
    make_dirs('cache')

    # -------------------------------------------------------------------------
    # Route53
    # -------------------------------------------------------------------------
    zones = query_aws('route53', 'list_hosted_zones', region)

    for zone in zones.get('HostedZones', []):
        process_dns_records(zone['Id'], region, nodes, edges)

    # ---------------------------------------------------------------------
    # Global services - S3, Cloudfront
    # ---------------------------------------------------------------------
    process_cloudfront(region, nodes, edges)
    process_s3(region, nodes, edges)

    # -------------------------------------------------------------------------
    # Regions loop
    # -------------------------------------------------------------------------
    for region in region_list:
        logger.info('** %s', region)

        process_ec2s(region, nodes, edges)
        process_elbs(region, nodes, edges)
        process_elbsv2(region, nodes, edges)
        process_rds(region, nodes, edges)
        process_redshift(region, nodes, edges)
        process_elasticache(region, nodes, edges)
        process_asgs(region, nodes, edges)
        process_sqs(region, nodes, edges)

    write_csv(nodes.values(), nodes_filename, node_fields)
    write_csv(edges, edges_filename, edge_fields)


if __name__ == "__main__":
    # execute only if run as a script
    main()
