#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import json
import csv
from datetime import date, datetime
from hashlib import sha1
import botocore
import boto3

logger = logging.getLogger('main')
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# ch.setLevel(logging.INFO)

account_id = None

logger.addHandler(ch)

node_fields = [
    'type',
    'name',
    'description',
    'weight',
    'counter'
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
    Adds a node to the array - or increments the weight if a duplicate
    '''
    node_name = node['type']+'_'+node['name']
    if node_name in existing_nodes:
        existing_nodes[node_name]['counter'] += 1
    else:
        existing_nodes[node_name] = node
        existing_nodes[node_name]['counter'] = 1

def get_aws_account_id():
    global account_id
    if account_id is None:
        account_id = boto3.client("sts").get_caller_identity()["Account"]

    return account_id

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
    elif api == 's3' and method == 'get_bucket_location':
        # s3 get_bucket_location has no paginator. :/
        records = client.get_bucket_location(Bucket=kwargs['Bucket']).get('LocationConstraint',None)
        # Format the us-east-1 (aka VA) buckets to be correct.
        if records is None:
            records = "us-east-1"
    elif api == 's3' and method == 'get_bucket_website':
        # s3 list_buckets has no paginator. :/
        try:
            records = client.get_bucket_website(Bucket=kwargs['Bucket'])
        except botocore.exceptions.ClientError as error:
            # boto3.exceptions.ClientError.NoSuchWebsiteConfiguration:
            records = {}
    elif api == 'sqs' and method == 'list_queues':
        # sqs list_queues has no paginator. :/
        records = client.list_queues().get('QueueUrls', [])
    elif api == 'opensearch' and method == 'list_domain_names':
        # opensearch list_queues has no paginator. :/
        records = client.list_domain_names().get('DomainNames', [])
    elif api == 'opensearch' and method == 'describe_domains':
        # opensearch describe_domains has no paginator. :/
        records = client.describe_domains(DomainNames=kwargs['DomainNames']).get('DomainStatusList', [])
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


def check_external_service(dns_name):
    '''
    Checks for known external services
    '''

    #TODO: Make this is a proper dictionary lookup.
    if dns_name.endswith('pardot.com'):
        return "pardot.com"
    if dns_name.endswith('zendesk.com'):
        return "Zendesk.com"

    # Certs
    if dns_name.endswith('acm-validations.aws'):
        return "AWS Certs"
    if dns_name.endswith('comodoca.com'):
        return "Comodo CA"
    if dns_name.endswith('sectigo.com'):
        return "Sectigo CA"

    # Google
    if dns_name.endswith('ghs.google.com'):
        return "Google Hosted"
    if dns_name.endswith('googlehosted.com'):
        return "Google Hosted"


    if dns_name.endswith('dkim.amazonses.com'):
        return "dkim.amazonses.com"

    if dns_name.endswith('azurewebsites.net'):
        return "azurewebsites.net"
    
    if dns_name.endswith('stspg-customer.com'):
        return "Status Page"




    return None


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

            # Clamp dns weights to 1 or 0
            weight = 1 if record.get('Weight', 1) > 0 else 0
            # add the edge value for the CNAME
            edges.append(
                new_edge(
                    from_type='dns',
                    from_name=name,
                    edge='depends',
                    to_type='dns',
                    to_name=ns_alias if ns_alias else ns_value,
                    weight=weight
                )
            )


            # Check if external service endpoint (returned None if not found)
            external_service_name = check_external_service(ns_value)

            # If an external service create a node for it.
            if external_service_name is not None:
                add_update_node(
                    nodes,
                    new_node(
                        type='dns',
                        name=ns_value,
                        description=ns_type,
                    )
                )
                add_update_node(
                    nodes,
                    new_node(
                        type='externalservice',
                        name=external_service_name,
                        description=external_service_name
                    )
                )
                edges.append(
                    new_edge(
                        from_type='dns',
                        from_name=ns_value,
                        edge='depends',
                        to_type='externalservice',
                        to_name=external_service_name,
                        weight=1
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
                # Add node for the public IP address
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

    for elb in records['LoadBalancers']:
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
                                    LoadBalancerArn=elb['LoadBalancerArn']
                                    )

        for target_group in target_groups['TargetGroups']:
            # Loop over each target
            target_healths = query_aws('elbv2',
                                    'describe_target_health',
                                    region,
                                    TargetGroupArn=target_group['TargetGroupArn']
                                    )
            for target in target_healths['TargetHealthDescriptions']:
                # Connect ELB to the target instance
                edges.append(
                    new_edge(
                        from_type='ec2',
                        from_name=target['Target']['Id'],
                        edge='depends',
                        to_type='elb',
                        to_name=name,
                        weight=1
                    )
                )


def process_rds(region, nodes, edges):
    """
    Find all the RDS nodes
    """
    records = query_aws('rds', 'describe_db_instances', region)

    for rds in records.get('DBInstances'):
        name = rds.get('DBInstanceArn',"")
        dnsname = fmt_dns(rds.get('Endpoint', {}).get('Address'))
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
                name=dnsname,
                description='A',
                region=region
            )
        )
        # add an edge for the RDS to DNS link
        edges.append(
            new_edge(
                from_type='dns',
                from_name=dnsname,
                edge='depends',
                to_type='rds',
                to_name=name,
                weight=1
            )
        )

        replica_source = rds.get('ReadReplicaSourceDBInstanceIdentifier',None)
        if replica_source:
            # If not an ARN then make an ARN
            if replica_source[0:4] != 'arn:':
                account_id = get_aws_account_id()
                replica_source = f"arn:aws:rds:{region}:{account_id}:db:{replica_source}"

            edges.append(
                new_edge(
                    from_type='rds',
                    from_name=replica_source,
                    edge='replicates',
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
                    from_type='ec2',
                    from_name=ec2.get('InstanceId'),
                    edge='depends',
                    to_type='asg',
                    to_name=name,
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
        # Add the DNS node for it
        add_update_node(
            nodes,
            new_node(
                type='dns',
                name=name,
                description=description,
                region=region
            )
        )
        # add an edge for the RDS to DNS link
        edges.append(
            new_edge(
                from_type='dns',
                from_name=name,
                edge='depends',
                to_type='redshift',
                to_name=name,
                weight=1
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
        name = cache['ARN']
        description = ' '.join(
            [
                cache['CacheClusterId'],
                cache['CacheNodeType'],
                cache['Engine']
            ]
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

        # Get all the DNS endpoints for cache
        dns_endpoints = []
        if 'ConfigurationEndpoint' in cache:
            dns_endpoints.append(cache.get('ConfigurationEndpoint', {}).get('Address'))
        
        for cachenode in cache.get('CacheNodes', [{}]):
            dns_endpoints.append(cachenode.get('Endpoint', {}).get('Address'))

        # Link in each dns_endpoint
        for endpoint in dns_endpoints:
            # Add the DNS node for it
            add_update_node(
                nodes,
                new_node(
                    type='dns',
                    name=endpoint,
                    description=description,
                    region=region
                )
            )
            # add an edge for the RDS to DNS link
            edges.append(
                new_edge(
                    from_type='dns',
                    from_name=endpoint,
                    edge='depends',
                    to_type='elasticache',
                    to_name=name,
                    weight=1
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

def process_opensearch(region, nodes, edges):
    """
    Find all the opensearch/elasticsearch clusters
    """
    records = query_aws(
        'opensearch',
        'list_domain_names',
        region
    )

    domain_names = []
    for record in records:
        print(record)
        domain_names.append(record['DomainName'])

    # Get the domain details
    records = query_aws(
        'opensearch',
        'describe_domains',
        region,
        DomainNames=domain_names
    )

    for opensearch in records:
        name = opensearch['ARN']
        description = ' '.join(
            [
                opensearch['DomainName'],
                opensearch['ClusterConfig']['InstanceType'],
                str(opensearch['ClusterConfig']['InstanceCount']),
                opensearch['EngineVersion']
            ]
        )
        endpoint = opensearch['Endpoints']['vpc']

        add_update_node(
            nodes,
            new_node(
                type='opensearch',
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
                name=endpoint,
                description=description,
                region=region
            )
        )
        # add an edge for the Cluster to DNS link
        edges.append(
            new_edge(
                from_type='dns',
                from_name=endpoint,
                edge='depends',
                to_type='opensearch',
                to_name=name,
                weight=1
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

        #Get the bucket location
        bucket_region = query_aws(
            's3',
            'get_bucket_location',
            region,
            Bucket=bucket['Name']
        )



        #Add the node or the S3 Domain
        add_update_node(
            nodes,
            new_node(
                type='s3',
                name=bucket['Name'],
                description=bucket['Name'],
                region=bucket_region
            )
        )

        # Build a DNS for the full bucket name
        # protocol://service-code.region-code.amazonaws.com
        # assets.learnosity.com.s3.amazonaws.com
        full_bucket_names = []

        # Add fully qualified domain
        full_bucket_names.append(f"{bucket['Name']}.s3.{bucket_region}.amazonaws.com")
        # Add special case VA name
        if bucket_region == 'us-east-1':
            full_bucket_names.append(f"{bucket['Name']}.s3.amazonaws.com")

        # If it's a domain name style (ie has at least 1 . in it) - then add that too.
        if bucket['Name'].find('.') != -1:
            full_bucket_names.append(bucket['Name'])

        # Add DNS and links for each of these
        for full_bucket_name in full_bucket_names:

            # Add the DNS node for it
            add_update_node(
                nodes,
                new_node(
                    type='dns',
                    name=full_bucket_name,
                    description=full_bucket_name,
                    region=bucket_region
                )
            )
            # add an edge for the RDS to DNS link
            edges.append(
                new_edge(
                    from_type='dns',
                    from_name=full_bucket_name,
                    edge='depends',
                    to_type='s3',
                    to_name=bucket['Name'],
                    weight=1
                )
            )

        # Check if the is a website configuration for this - if so then link it in
        bucket_website = query_aws(
            's3',
            'get_bucket_website',
            region,
            Bucket=bucket['Name']
        )
        
        if bucket_website != {}:

            # S3 Website domain names from here:
            # https://docs.aws.amazon.com/general/latest/gr/s3.html#s3_website_region_endpoints
            s3_website_regions = {
                "us-east-1": "s3-website-us-east-1.amazonaws.com",
                "us-east-2": "s3-website.us-east-1.amazonaws.com",
                "us-west-1": "s3-website-us-west-1.amazonaws.com",
                "us-west-2": "s3-website-us-west-2.amazonaws.com",
                "us-east-1": "s3-website-us-east-1.amazonaws.com",
                "af-south-1":"s3-website.af-south-1.amazonaws.com",
                "ap-east-1":"s3-website.ap-east-1.amazonaws.com",
                "ap-south-1":"s3-website.ap-south-1.amazonaws.com",
                "ap-northeast-3":"s3-website.ap-northeast-3.amazonaws.com",
                "ap-northeast-2":"s3-website.ap-northeast-2.amazonaws.com",
                "ap-southeast-1":"s3-website-ap-southeast-1.amazonaws.com",
                "ap-southeast-2":"s3-website-ap-southeast-2.amazonaws.com",
                "ap-northeast-1":"s3-website-ap-northeast-1.amazonaws.com",
                "ca-central-1":"s3-website.ca-central-1.amazonaws.com",
                "cn-northwest-1.amazonaws.com.cn":"s3-website.cn-northwest-1.amazonaws.com.cn",
                "eu-central-1":"s3-website.eu-central-1.amazonaws.com",
                "eu-west-1":"s3-website-eu-west-1.amazonaws.com",
                "eu-west-2":"s3-website.eu-west-2.amazonaws.com",
                "eu-south-1":"s3-website.eu-south-1.amazonaws.com",
                "eu-west-3":"s3-website.eu-west-3.amazonaws.com",
                "eu-north-1":"s3-website.eu-north-1.amazonaws.com",
                "me-south-1":"s3-website.me-south-1.amazonaws.com",
                "sa-east-1":"s3-website-sa-east-1.amazonaws.com",
                "us-gov-east-1":"s3-website.us-gov-east-1.amazonaws.com",
                "us-gov-west-1":"s3-website-us-gov-west-1.amazonaws.com",
            }

            s3_website_host = f"{bucket['Name']}.{s3_website_regions.get(bucket_region,'UNKNOWN_REGION')}"

            # Add the DNS node for it
            add_update_node(
                nodes,
                new_node(
                    type='dns',
                    name=s3_website_host,
                    description=s3_website_host,
                    region=bucket_region
                )
            )
            # add an edge for the RDS to DNS link
            edges.append(
                new_edge(
                    from_type='dns',
                    from_name=s3_website_host,
                    edge='depends',
                    to_type='s3',
                    to_name=bucket['Name'],
                    weight=1
                )
            )

        
        # Check if it's a redirector 
        # if(bucket_website.get('RedirectAllRequestsTo',{}).get('HostName'),None):
            # TODO Add DNS Node
            # TODO dd Edge node



def main():
    ''' Main function to kick it all off '''

    nodes = {}
    edges = []

    # TODO: This should come from config file

    region_list = [
        'us-west-1', 'us-west-2', 'us-east-1', 'eu-west-1', 'ap-southeast-2'
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
        process_opensearch(region, nodes, edges)

        # TODO: handle external DNS names - eg go.pardot.com etc.

    write_csv(nodes.values(), nodes_filename, node_fields)
    write_csv(edges, edges_filename, edge_fields)


if __name__ == "__main__":
    # execute only if run as a script
    main()
