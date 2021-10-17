var cy = window.cy = cytoscape({
  container: document.getElementById('cy'),

  boxSelectionEnabled: false,
  autounselectify: true,

  style: [
    {
      selector: 'node[importance]',
      css: {
        'content': 'data(id)',
        'text-valign': 'center',
        'text-halign': 'right',
        'width' : 'mapData(importance,0,100,10,100)',
        'height' : 'mapData(importance,0,100,10,100)',

        // 'width': function( ele ){ return ele.data('importance')}
        'background-fit': 'cover cover',
        'background-image-opacity': 1,
        'background-clip': 'none',
        'min-zoomed-font-size': 30

      }
    },
    {
      selector: 'node[type = "ec2"]',
      css: {
        'background-image': 'static/icons_aws/Arch_Amazon-EC2_64.svg',
      }
    },
    {
      selector: 'node[type = "elb"]',
      css: {
        'background-image': 'static/icons_aws/Arch_Elastic-Load-Balancing_64.svg',
      }
    },
    {
      selector: 'node[type = "elbv2"]',
      css: {
        'background-image': 'static/icons_aws/Arch_Elastic-Load-Balancing_64.svg',
      }
    },
    {
      selector: 'node[type = "cloudfront"]',
      css: {
        'background-image': 'static/icons_aws/Arch_Amazon-CloudFront_64.svg',
      }
    },
    {
      selector: 'node[type = "rds"]',
      css: {
        'background-image': 'static/icons_aws/Arch_Amazon-RDS_64.svg',
      }
    },
    {
      selector: 'node[type = "asg"]',
      css: {
        'background-image': 'static/icons_aws/Arch_Amazon-Application-Auto-Scaling_64.svg',
      }
    },
    {
      selector: 'node[type = "elasticache"]',
      css: {
        'background-image': 'static/icons_aws/Arch_Amazon-ElastiCache_64.svg',
      }
    },
     {
      selector: 'node[type = "s3"]',
      css: {
        'background-image': 'static/icons_aws/Arch_Amazon-Simple-Storage-Service_64.svg',
      }
    },
     {
      selector: 'node[type = "sqs"]',
      css: {
        'background-image': 'static/icons_aws/Arch_Amazon-Simple-Queue-Service_64.svg',
      }
    },
     {
      selector: 'node[type = "redshift"]',
      css: {
        'background-image': 'static/icons_aws/Arch_Amazon-Redshift_64.svg',
      }
    },
     {
      selector: 'node[type = "opensearch"]',
      css: {
        'background-image': 'static/icons_aws/Arch_Amazon-OpenSearch-Service_64.svg',
      }
    },
    {
      selector: 'node[type = "externalservice"]',
      css: {
        'background-image': 'static/icons/cloud.png',
      }
    }, 
    {
      selector: '$node > node',
      css: {
        'padding-top': '10px',
        'padding-left': '10px',
        'padding-bottom': '10px',
        'padding-right': '10px',
        'text-valign': 'top',
        'text-halign': 'center',
        'background-color': '#bbb'
      }
    },
    {
      selector: 'edge[weight]',
      css: {
        'opacity': 0.2,
        'line-color' : 'rgb(0,0,0)',
        'source-arrow-shape': 'none',
        'source-arrow-color' : 'rgb(0,0,0)',
        'target-arrow-shape': 'triangle',
        'target-arrow-color' : 'rgb(0,0,0)',
        'line-style': 'solid',
        'width': 'data(weight)',
        'curve-style': 'bezier'
      }
    },
     {
      selector: 'edge[type="replicates"]',
      css: {
        'line-color' : 'rgb(0,0,255)',
        'width': 1
      }
    },
     {
      selector: 'edge[weight="0"]',
      css: {
        'line-style': 'dashed',
        'line-color' : 'rgb(255,0,0)',
        'width': 1
      }
    },
    {
      selector: ':selected',
      css: {
        'background-color': 'black',
        'line-color': 'black',
        'target-arrow-color': 'black',
        'source-arrow-color': 'black'
      }
    },
    {
      selector : 'node[root = 1]',
      css : {
        'background-color' : 'rgb(0,252,0)'
      }
    },
    {
      selector : 'node[leaf = 1]',
      css : {
        'background-color' : 'rgb(0,0,252)'
      }
    },
    {
      selector : 'node[dead = 1]',
      css : {
        'background-color' : 'rgb(252,0,0)'
      }
    },
    {
      selector : 'node[partlydead = 1]',
      css : {
        'background-color' : 'rgb(252,165,0)'
      }
    }
  ],

  elements: elements,

  layout: {
    name: 'preset',
    padding: 5
  }
});