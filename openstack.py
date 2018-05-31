#!/usr/bin/env python

"""
This script queries an openstack API and returns an ansible inventory.

Ensure the following global variables are set:
url: url to the openstack web service (ex: http://openstack.org:5000/)
username: username of an account with access to the API for the tracked projects
password: password of an account with access to the API for the tracked projects
domain: domain name of an account with access to the API for the tracked projects
trackedProjects: list of project Ids to collect data from.  You can get this id
                 in the openstack web portal by going to Project => API access
                 and downloading the clouds.yaml file.
"""


from __future__ import print_function
import requests
import json


token = None
catalog = []
projectName = None
projectId = None

url = ''
username = ''
password = ''
domain = ''
trackedProjects = []


def set_auth_token(refresh=False):
    """Gets an auth token from the identity service."""
    global token
    global catalog
    global projectName

    if token is None or validateToken(token) == False or refresh:
        data = requests.post("{}v3/auth/tokens".format(url), data=json.dumps(auth_payload(projectId)), headers={'Content-Type':'application/json'})
        token = data.headers['X-Subject-Token']
        catalog = json.loads(data.text)['token']['catalog']
        projectName = json.loads(data.text)['token']['project']['name']


def auth_payload(projId=None):
    """Returns an authentication payload, useable by the identity api

    Arguments:
    projId -- (string) Id of the project to scope to
    """
    return {
        "auth": {
            "identity": {
                "methods": [ "password" ],
                "password": {
                    "user": {
                        "name": username,
                        "domain": {
                            "name": domain
                        },
                        "password": password
                    }
                }
            },
            "scope": {
                "project": {
                    "id": projId if projId is not None else projectId
                }
            }
        }
    }


def validateToken(authToken):
    """Validates the provided auth token with the identity api

    Arguments:
    authToken -- (string) The authentication to validate

    Returns: (bool) true if the token is valid, false if the token is not valid
    """
    response = requests.get("{}v3/auth/tokens".format(url), headers={'X-Auth-Token':token, 'X-Subject-Token':authToken})
    return response.status_code == 200


def getEndpointUrl(name='compute'):
    """Returns the url of an endpoint for the specified api

    Arguments:
    name -- (string) The name of the api to get the endpoint for.

    Returns: (string) Url to the endpoint for the specified api
    """
    set_auth_token()
    endpoint = [n['url'] for ep in [c['endpoints'] for c in catalog if c['type'] == name] for n in ep if n['interface'] == 'public']
    return endpoint[0]


def submit(url, headers={}, method='GET', data={}):
    """Submit an http request.  Appends an authentication token to the request.

    Arguments:
    url -- (string) Uri to the endpoint
    headers -- (dict) dictionary of any http headers to append to the request
    method -- (string) GET or POST
    data -- (dict) json data

    Returns: (requests.response) Response from the server
    """
    set_auth_token()

    headers['X-Auth-Token'] = token
    if method.upper() == 'POST':
        return requests.post(url, data=data, headers=headers)

    return requests.get(url, headers=headers)


def getIPAddresses(serverPayload, ipType='floating'):
    """Extracts a list of ip addresses from a server payload.

    Arguments:
    serverPayload: json server payload from the openstack Compute API
    ipType: (string) type of ip to return - fixed or floating (default: floating)
    """
    return [n['addr'] for network in serverPayload['addresses'] for n in serverPayload['addresses'][network] if n['OS-EXT-IPS:type'] == ipType]


if __name__ == '__main__':
    data = {"_meta": {"hostvars": {}}, "all": { "hosts": [], "vars": {}, "children": []}}
    for project in trackedProjects:
        projectId = project
        set_auth_token(refresh=True)

        # get our endpoint url for the web service
        endpoint = getEndpointUrl('compute')

        # load data about our servers
        servers = json.loads(submit("{}/servers/detail".format(endpoint)).text)['servers']

        #create a project group
        data[projectName] = { "hosts": [], "vars": {}}

        for server in servers:
            # all openstack data thats a string is added as hostvars
            data['_meta']['hostvars'][server['name']] = {"openstack_{}".format(k):v for k,v in server.items() if isinstance(v,str)}

            #append ip address if public IP available
            pubIPs = getIPAddresses(server)
            if pubIPs is not None and len(pubIPs) > 0:
                data['_meta']['hostvars'][server['name']]['ansible_host'] = pubIPs[0]


            #add the server to the 'all' and project groups
            data['all']['hosts'].append(server['name'])
            data[projectName]["hosts"].append(server['name'])

            if len(server['metadata']) > 0:
                data['_meta']['hostvars'][server['name']].update(server['metadata'])

                #if groups are defined in metadata, add them
                if 'groups' in server['metadata']:
                    grps = server['metadata']['groups'].split(';') if ';' in server['metadata']['groups'] else [server['metadata']['groups']]
                    for group in grps:
                        if group not in data:
                            data[group] = { "hosts": [server['name']], "vars": {}}

                            #add the group to the all group
                            data['all']['children'].append(group)
                        else:
                            data[group]["hosts"].append(server['name'])


    print(json.dumps(data))
