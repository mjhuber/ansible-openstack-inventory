# ansible-openstack-inventory
This dynamic ansible inventory script collects an inventory of compute hosts from openstack.

## Requirements
Ensure the following variables are set:
* url: url to the openstack web service (eg: http://openstack.org:5000/)
* username: username of an account with access to the API for the tracked projects
* password: password of an account with access to the API for the tracked projects
* domain: domain name of an account with access to the API for the tracked projects

An environment variable named ANSIBLE_OS_PROJECTS must contain a string of comma separated project names that should be tracked.


## Groups
For each openstack project tracked, a group with the project name is added to the ansible inventory.

## Metadata
Metadata is added as hostvars with 'openstack_' prepended to the variable name.  If a special metadata variable named 'group' is present, the variable will be added as a group to the ansible inventory (multiple groups can be created by separating the names with ';')
