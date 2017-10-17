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
        'background-image': 'static/icons/Compute_AmazonEC2_instance_LARGE.png',
      }
    },
    {
      selector: 'node[type = "elb"]',
      css: {
        'background-image': 'static/icons/Compute_ElasticLoadBalancing_ClassicLoadbalancer_LARGE.png',
      }
    },
    {
      selector: 'node[type = "cloudfront"]',
      css: {
        'background-image': 'static/icons/NetworkingContentDelivery_AmazonCloudFront_LARGE.png',
      }
    },
    {
      selector: 'node[type = "rds"]',
      css: {
        'background-image': 'static/icons/Database_AmazonRDS_DBinstance_LARGE.png',
      }
    },
    {
      selector: 'node[type = "asg"]',
      css: {
        'background-image': 'static/icons/Compute_AmazonEC2_AutoScaling_LARGE.png',
      }
    },
    {
      selector: 'node[type = "elasticache"]',
      css: {
        'background-image': 'static/icons/Database_AmazonElasticCache_cachenode_LARGE.png',
      }
    },
     {
      selector: 'node[type = "s3"]',
      css: {
        'background-image': 'static/icons/Storage_AmazonS3_bucketwithobjects_LARGE.png',
      }
    },
     {
      selector: 'node[type = "sqs"]',
      css: {
        'background-image': 'static/icons/Database_AmazonElasticCache_cachenode_LARGE.png',
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
        'source-arrow-shape': 'tee',
        'source-arrow-color' : 'rgb(0,0,0)',
        'target-arrow-shape': 'triangle',
        'target-arrow-color' : 'rgb(0,0,0)',
        'line-style': 'solid',
        'width': 'data(weight)',
        'curve-style': 'bezier'
      }
    },
     {
      selector: 'edge[weight="0"]',
      css: {
        'line-style': 'dashed',
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