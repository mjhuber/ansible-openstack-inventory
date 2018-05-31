# ansible-openstack-inventory
This dynamic ansible inventory script collects an inventory of compute hosts form openstack.

Ensure the following variables are set:
* url: url to the openstack web service (eg: http://openstack.org:5000/)
* username: username of an account with access to the API for the tracked projects
* password: password of an account with access to the API for the tracked projects
* domain: domain name of an account with access to the API for the tracked projects
* trackedProjects: list of project Ids to collect data from.  You can get this id
  in the openstack web portal by going to Project => API access and downloading the clouds.yaml file.

## Groups
For each openstack project tracked, a group with the project name is added to the ansible inventory.

## Metadata
Metadata is added as hostvars with 'openstack_' prepended to the variable name.  If a special metadata variable named 'group' is present, the variable will be added as a group to the ansible inventory (multiple groups can be created by separating the names with ';')
