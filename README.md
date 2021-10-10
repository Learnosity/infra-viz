# infra-viz
Infrastructure dependency visualisation


## Usage

There are 2 parts to this

1. Collect the data from AWS

For this you will need read-only access to the AWS environment.

Then run:
$ python3 collect.py

Once this has run you can explore the data.


2. View and explore the visualised data:

$ python3 server.py

Browse to:
http://127.0.0.1:5000


## Roadmap

### Frontend/JS
- [X] Migrate core to python 
- [X] Control how far it can zoom out or in
- [ ] Add search field to find nodes
- [ ] Add info on each of the nodes
- [ ] Add icon for type of each node
- [ ] Make layouts much better
- [ ] Filter to unconnected nodes
- [ ] General filtering of nodes
- [ ] Add ability to filter by region
- [ ] Add ability to search for nodesx

### Collect Script
- [X] Move to infra-viz project
- [X] Add support for RDS
- [X] Ability to create a dependency graph for infraviz
- [X] make DNS Cacheable
- [X] Add redshift
- [X] Add elasticache
- [X] Add cloudfront
- [X] Add ASGs
- [X] Fix up memcache linkages
- [X] Deduplicate nodes
- [X] Publish as open source
- [ ] Add click options - http://click.pocoo.org/6/
- [ ] Command line option for regions etc
- [ ] Add mode for exceptions only
- [ ] Add IP addresses for machines
- [ ] Add ability to flush all or a single resource type
- [ ] Ability to link in non AWS data - eg internal config - maybe via CSV or seperate file
- [ ] link up cloudfront to ELB's and S3


## Screenshots

ASG with 10 nodes: 
![alt text](https://github.com/Learnosity/infra-viz/raw/master/screenshots/ASG_with_10_nodes.png "ASG with 10 nodes")

DNS with different weights: 
![alt text](https://github.com/Learnosity/infra-viz/raw/master/screenshots/DNS_with_different_weights.png "DNS with different weights")

Weighted DNS pointing to ASG nodes: 
![alt text](https://github.com/Learnosity/infra-viz/raw/master/screenshots/Weighted_DNS_pointing_to_ASG_nodes.png "Weighted DNS pointing to ASG nodes")


## Dependencies:

The infra-viz project utilised the following open source or free resources:

* Cytoscape JS library - http://js.cytoscape.org/  MIT licence
* Dagre - https://github.com/cpettitt/dagre/wiki  MIT licence 
* JQuery - https://jquery.org MIT licence
* PapaParse - http://papaparse.com MIT licence
* AWS Simple icons - https://aws.amazon.com/architecture/icons/  Permissive licence
* Flask - http://flask.pocoo.org/ - BSD licence
* Python 3 - https://docs.python.org/3/license.html - PSF License Agreement 
 


Linked Entities

DNS
 - DNS Node
 - Edge Link via A record, CNAME and ALIAS

Cloudfront
 - Cloudfront Node
 - DNS Node
 - Edge between Cloudfront and DNS

RDS
 - RDS Node
 - DNS Node
 - Edge between DNS and RDS
 - Replicas - Node and Edge

Elasticache
 - Elasticache Node
 - DNS Node
 - Edge between DNS and Elasticache
 - Replicas? - Node and Edge

Redshift
 - Redshift Node
 - DNS Node
 - Edge between DNS and Redshift

ALB
 - ALB Node
 - DNS Node
 - Edge between DNS and ALB
 - Edge betetween Target Group and ALB

Target Groups
 - Target Group Nodes (ARN)
 - Edge to Load Balancer ARN

ASG
 - ASG Node
 - Edge to Target Group ARN Node
 - Edge to Instances

