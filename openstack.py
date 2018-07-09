#!/usr/bin/python

"""
This script queries an openstack API and returns an ansible inventory.

Ensure the following global variables are set:
url: url to the openstack web service (ex: http://10.66.240.110:5000/)
username: username of an account with access to the API for the tracked projects
password: password of an account with access to the API for the tracked projects
user_domain: domain name of an account with access to the API for the tracked projects
project_domain: domain name the tracked projects are in
PROJECT_ENVIRON_VAR: The name of an environment variable that contains the names of the tracked project(s).
                     Each project name should be separated by a comma.

host_vars::
All metadata is set as a hostvar, excluding the special 'group' metadata key, which is explained below
under group_vars.

In addition, the following hostvars will be set:
- ansible_host: set to a floating IP if any are configured
- accesss_ip: set to a floating IP if any are configured
- ip: set to a fixed IP if any are configured

group_vars::
A group is added for each group name in a metadata key 'group'.  Separate each group name with
a ;.
"""


from __future__ import print_function
import requests
import json
import os


token = None
catalog = []
projectName = None

url = ''
username = ''
password = ''
user_domain = ''
project_domain = ''
PROJECT_ENVIRON_VAR = 'ANSIBLE_OS_PROJECTS'


def set_auth_token(refresh=False, projId=None):
    """Gets an auth token from the identity service."""
    global token
    global catalog
    global projectName

    if token is None or validateToken(token) == False or refresh:
        data = requests.post("{}v3/auth/tokens".format(url),
                             data=json.dumps(auth_payload(scope='domain' if projId is None else 'project', projId=projId)),
                             headers={'Content-Type':'application/json'})

        token = data.headers['X-Subject-Token']

        if projId is not None:
            catalog = json.loads(data.text)['token']['catalog']
            projectName = json.loads(data.text)['token']['project']['name']


def auth_payload(scope, projId=None):
    """Returns an authentication payload, useable by the identity api

    Arguments:
    projId -- (string) Id of the project to scope to, if scoping to a project.
    scope: (string) domain or project.  What to scope to.  If project, must supply projId.
    """

    scopes = {
        "domain": {
                    "domain": {
                                "name": project_domain
                    }
        },
        "project": {
                    "project": {
                        "id": projId
                    }

        }
    }

    auth = {
        "auth": {
            "identity": {
                "methods": [ "password" ],
                "password": {
                    "user": {
                        "name": username,
                        "domain": {
                            "name": user_domain
                        },
                        "password": password
                    }
                }
            }
        }
    }

    if scope in scopes:
        auth['auth']['scope'] = scopes[scope]
    return auth


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


def projNamesToIds(projects=[]):
    """Convert a list of project names to a list of project Ids.

    Arguments:
    projects: (list) A list of project names.

    Returns: (list) A list of project Ids.
    """
    allProjects = json.loads(submit("{}v3/projects".format(url)).text)['projects']
    return [proj['id'] for proj in allProjects if not proj['is_domain'] and proj['name'] in projects]


def getProjects():
    """Get list of tracked project Ids

    Returns: (list) A list of project Ids.
    """
    if PROJECT_ENVIRON_VAR in os.environ:
        tracked = os.environ[PROJECT_ENVIRON_VAR].split(',') if ',' in os.environ[PROJECT_ENVIRON_VAR] else [os.environ[PROJECT_ENVIRON_VAR]]
        return projNamesToIds(tracked)









if __name__ == '__main__':
    #scope to domain
    set_auth_token()

    data = {"_meta": {"hostvars": {}}, "all": { "hosts": [], "vars": {}, "children": []}}
    for project in getProjects():

        #scope to project
        set_auth_token(refresh=True, projId=project)

        # get our endpoint url for the web service
        endpoint = getEndpointUrl('compute')

        # load data about our servers
        servers = json.loads(submit("{}/servers/detail".format(endpoint)).text)['servers']

        #create a project group
        data[projectName] = { "hosts": [], "vars": {}}

        for server in servers:
            # all openstack data thats a string is added as hostvars
            data['_meta']['hostvars'][server['name']] = {"openstack_{}".format(k):v for k,v in server.items() if isinstance(v,str)}

            #append floating IP to 'ansible_host & access_ip'
            pubIPs = getIPAddresses(server)
            if pubIPs is not None and len(pubIPs) > 0:
                data['_meta']['hostvars'][server['name']]['ansible_host'] = pubIPs[0]
                data['_meta']['hostvars'][server['name']]['access_ip'] = pubIPs[0]

            #append private ip to a hostvar 'ip'
            privIps = getIPAddresses(server,ipType='fixed')
            if privIps is not None and len(privIps) > 0:
                data['_meta']['hostvars'][server['name']]['ip'] = privIps[0]


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
