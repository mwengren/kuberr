import os
import sys
import argparse
import yaml
import re
import requests
import json
from pprint import pprint
import xml.etree.ElementTree as ET

from .clients import shared_client
from .util import *

from kubernetes import client, config
from kubernetes.client.rest import ApiException


ERDDAP_VERSION = os.environ.get('ERDDAP_VERSION', 1.82)
APPNAME = os.environ.get('APPNAME', "noapp").lower()
DOMAINNAME = os.environ.get('DOMAINNAME')
RELEASENAME = os.environ.get('RELEASENAME', "release-name").lower()
# Removed because we just use APPNAME instead:
#NAMESPACE = os.environ.get('POD_NAMESPACE', 'erddap')


VALID_QUERY_ACTIONS = ['create_configmaps','update_setup_configmap', 'update_datasets_configmap']


def main():
    """
    Entrypoint/command line interface
    """
    kwargs = {
        'description': 'Kuberr performs a few small orchestration tasks to deploy ERDDAP pods and other resources on Kubernetes. \
Execute different tasks by passing an -a|--action parameter to this module.',
        'formatter_class': argparse.RawDescriptionHelpFormatter,
    }
    parser = argparse.ArgumentParser(**kwargs)

    parser.add_argument('-a', '--action', type=str, required=True,
                        help='Kuberr config action to execute.  Implemented actions: {}'.format(", ".join(VALID_QUERY_ACTIONS)))

    args = parser.parse_args()

    # check to make sure the 'action' argument passed matches an expected query action type:
    if args.action not in VALID_QUERY_ACTIONS:
        sys.exit("Error: '--action' parameter value must contain a known query action.  Valid query actions: {valid}.  Value passed: {param}".format(valid=", ".join(VALID_QUERY_ACTIONS), param=args.action))


    # Load the Kubernetes cluster configuration, if running within a cluster, or
    # otherwise by loading a config file by looking for the path set by env var KUBECONFIG
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
        # test that config loaded properly and there are some contexts available
        # (will only work with a KUBECONFIG config file - in other words outside
        # of a cluster):
        contexts, active_context = config.list_kube_config_contexts()
        if not contexts:
            print("Cannot find any context in kube-config file.")
            return
        contexts = [context['name'] for context in contexts]
        print(contexts)

    core_api = shared_client('CoreV1Api')
    extensions_v1beta1_api = shared_client('ExtensionsV1beta1Api')
    api = shared_client('ApiClient')
    #from dask-kubernetes:
    #self.core_api = kubernetes.client.CoreV1Api()
    #extensions_v1beta1 = client.ExtensionsV1beta1Api()



    if args.action == "create_configmaps":
        # make a 'content' configmap with both datasets.xml and setup.xml:
        setup = requests.get("https://raw.githubusercontent.com/mwengren/erddap-content/master/{version}/content/erddap/setup.xml".format(version=ERDDAP_VERSION)).text
        datasets = requests.get("https://raw.githubusercontent.com/mwengren/erddap-content/master/{version}/content/erddap/datasets.xml".format(version=ERDDAP_VERSION)).text
        content = {
            'setup.xml': setup,
            'datasets.xml': datasets
        }
        configmap = create_configmap(core_api, "{}-{}".format("content", APPNAME), APPNAME, content)
        if configmap:
            print("Configmap {name} created in namespace: {namespace}".format(name=configmap.metadata.name, namespace=configmap.metadata.namespace))
            #print(configmap)
        else:
            print("Something went wrong creating configmap 'content'")

        # make an 'images' configmap with CSS (or other things to be added later as needed):
        erddapCss = requests.get("https://raw.githubusercontent.com/mwengren/erddap-content/master/{version}/content/erddap/images/erddapStart2.css".format(version=ERDDAP_VERSION)).text
        content = {
            'erddapStart2.css': erddapCss,
        }
        configmap = create_configmap(core_api, "{}-{}".format("images", APPNAME), APPNAME, content)
        if configmap:
            print("Configmap {name} created in namespace: {namespace}".format(name=configmap.metadata.name, namespace=configmap.metadata.namespace))
            #print(configmap)
        else:
            print("Something went wrong creating configmap 'images'")

        '''
        # make a configmap:
        setup = requests.get("https://raw.githubusercontent.com/mwengren/erddap-content/master/{version}/content/erddap/setup.xml".format(version=ERDDAP_VERSION)).text
        configmap = create_configmap(core_api, 'setup.xml', APPNAME, setup)
        if configmap:
            print("Configmap {name} created:".format(name=configmap.metadata.name))
            #print(configmap)
        else:
            print("Something went wrong creating configmap setup.xml")

        datasets = requests.get("https://raw.githubusercontent.com/mwengren/erddap-content/master/{version}/content/erddap/datasets.xml".format(version=ERDDAP_VERSION)).text
        configmap = create_configmap(core_api, 'datasets.xml', APPNAME, datasets)
        if configmap:
            print("Configmap {name} created:".format(name=configmap.metadata.name))
            #print(configmap)
        else:
            print("Something went wrong creating configmap datasets.xml")
        '''

    elif args.action == "update_setup_configmap":
        service_name = "{}-{}-erddap-service".format(RELEASENAME, APPNAME)

        # testing/debug only:
        #service_name = "erddap-service"
        #service_name = "dapperr-dapperr-erddap-service"
        #DOMAINNAME = "erddap.io"

        try:
            api_service = core_api.read_namespaced_service(service_name, APPNAME, pretty=True, exact=True, export=False)
            # debug:
            pprint(api_service)

            #service = json.dumps(api.sanitize_for_serialization(api_service))
            service = api.sanitize_for_serialization(api_service)

            # debug:
            print("\n\n {}".format(service))

            ip = service['spec']['clusterIP']
            print("\nip: {}".format(ip))
            base_url = ip

            # if there's a valid IP address for the LoadBalancer, use it:
            try:
                load_balancer_ip = service['status']['loadBalancer']['ingress'][0]['ip']
                print("load_balancer_ip: {}".format(load_balancer_ip))
                ip_pattern = re.compile("\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}")
                if ip_pattern.match(load_balancer_ip):
                    print("matched!")
                    base_url = load_balancer_ip
            except KeyError as e:
                load_balancer_ip = None

            # if there's a hostname available for the LoadBalancer, use it:
            try:
                load_balancer_hostname = service['status']['load_balancer']['ingress'][0]['hostname']
                #load_balancer_hostname = service['status']['load_balancer']['ingress']
                base_url = load_balancer_hostname
            except KeyError as e:
                load_balancer_hostname = None

            print("load_balancer_ip: {}".format(load_balancer_ip))
            print("load_balancer_hostname: {}".format(load_balancer_hostname))


            # additionally, if there happened to be a DOMAINNAME env var passed, use that above all others:
            if DOMAINNAME is not None:
                base_url = DOMAINNAME
            print ("base_url: {}".format(base_url))

        except ApiException as e:
            sys.exit("Exception when calling CoreV1Api->read_namespaced_service: %s\n" % e)

        try:
            content_configmap = core_api.read_namespaced_config_map("{}-{}".format("content", APPNAME), APPNAME, pretty=True, exact=True, export=False)

            setup = content_configmap.data['setup.xml']
            #pprint(setup)

            #tree = ET.fromstring(content_configmap.data['setup.xml'])
            tree = ET.fromstring(setup)
            #root = tree.getroot()

            elem = tree.find("baseUrl")
            print("baseUrl before: {}".format(elem.text))
            elem.text = "http://{}".format(base_url)
            print("baseUrl after: {}".format(elem.text))

            elem = tree.find("bigParentDirectory")
            print("bigParentDirectory before: {}".format(elem.text))
            elem.text = "/erddapData/"
            print("bigParentDirectory after: {}".format(elem.text))

            # act on the other settings if provided as env vars:
            tree.find("emailEverythingTo").text = os.environ.get("EMAILEVERYTHINGTO") if "EMAILEVERYTHINGTO" in os.environ else ""
            tree.find("emailFromAddress").text = os.environ.get("EMAILFROMADDRESS") if "EMAILEVERYTHINGTO" in os.environ else ""
            tree.find("emailUserName").text = os.environ.get("EMAILUSERNAME") if "EMAILUSERNAME" in os.environ else ""
            tree.find("emailPassword").text = os.environ.get("EMAILPASSWORD") if "EMAILPASSWORD" in os.environ else ""
            tree.find("emailProperties").text = os.environ.get("EMAILPROPERTIES") if "EMAILPROPERTIES" in os.environ else ""
            tree.find("emailSmtpHost").text = os.environ.get("EMAILSMTPHOST") if "EMAILSMTPHOST" in os.environ else ""
            tree.find("emailSmtpPort").text = os.environ.get("EMAILSMTPPORT") if "EMAILSMTPPORT" in os.environ else ""
            tree.find("adminInstitution").text = os.environ.get("ADMININSTITUTION") if "ADMININSTITUTION" in os.environ else ""
            tree.find("adminInstitutionUrl").text = os.environ.get("ADMININSTITUTIONURL") if "ADMININSTITUTIONURL" in os.environ else ""
            tree.find("adminIndividualName").text = os.environ.get("ADMININDIVIDUALNAME") if "ADMININDIVIDUALNAME" in os.environ else ""
            tree.find("adminPosition").text = os.environ.get("ADMINPOSITION") if "ADMINPOSITION" in os.environ else ""
            tree.find("adminPhone").text = os.environ.get("ADMINPHONE") if "ADMINPHONE" in os.environ else ""
            tree.find("adminAddress").text = os.environ.get("ADMINADDRESS") if "ADMINADDRESS" in os.environ else ""
            tree.find("adminCity").text = os.environ.get("ADMINCITY") if "ADMINCITY" in os.environ else ""
            tree.find("adminStateOrProvince").text = os.environ.get("ADMINSTATEORPROVINCE") if "ADMINSTATEORPROVINCE" in os.environ else ""
            tree.find("adminPostalCode").text = os.environ.get("ADMINPOSTALCODE") if "ADMINPOSTALCODE" in os.environ else ""
            tree.find("adminCountry").text = os.environ.get("ADMINCOUNTRY") if "ADMINCOUNTRY" in os.environ else ""
            tree.find("adminEmail").text = os.environ.get("ADMINEMAIL") if "ADMINEMAIL" in os.environ else ""
            tree.find("flagKeyKey").text = os.environ.get("FLAGKEYKEY") if "FLAGKEYKEY" in os.environ else ""

            # tree.find("").text = os.environ.get("") if "" in os.environ else ""

            # debug:
            #print(ET.tostring(tree))

            content_configmap.data['setup.xml'] = ET.tostring(tree, encoding="unicode")

        except ApiException as e:
            sys.exit("Exception when calling CoreV1Api->read_namespaced_config_map: %s\n" % e)

        try:
            api_response = core_api.replace_namespaced_config_map("{}-{}".format("content", APPNAME), APPNAME, content_configmap, pretty=True)
            # debug:
            #pprint(content_configmap)

        except ApiException as e:
            sys.exit("Exception when calling CoreV1Api->replace_namespaced_config_map: %s\n" % e)

    elif args.action == "update_datasets_configmap":
        pass

    # Testing only:
    # Create a deployment object with client-python API. The deployment we
    # created is same as the `nginx-deployment.yaml` in the /examples folder.
    #deployment = create_deployment_object()
    #print(deployment)
    #create_deployment(extensions_v1beta1_api, deployment)
    #update_deployment(extensions_v1beta1_api, deployment)
    #delete_deployment(extensions_v1beta1_api)


def create_configmap(api_instance, name=None, namespace=None, content=None):
    """
    Create a ConfigMap via k8s API.

    Parameters
    ----------
    content : string or dict
        content can be either a string in which case it will be stored as the value for key 'name' or
        content can be a dict, in which case the ConfigMap will have multiple entries dictated by the
        key/value pairs contained in 'content'

    """
    if name is not None:
        # handle multiple file ConfigMap - where 'content' is a dict:
        if isinstance(content, dict):
            configmap = {
                'apiVersion': 'v1',
                'metadata': {
                    'name': name,
                    'namespace': APPNAME,
                    'labels': {
                        'app': 'erddap',
                        'appName': APPNAME
                    }
                }
            }
            configmap['data'] = content

        # handle case where content is a single string:
        else:
            configmap = {
                'apiVersion': 'v1',
                'data': {
                    name: content
                },
                'metadata': {
                    'name': name,
                    'namespace': APPNAME,
                    'labels': {
                        'app': 'erddap',
                        'appName': APPNAME
                    }
                }
            }

        try:
            api_response = api_instance.create_namespaced_config_map(namespace, configmap, include_uninitialized=True, pretty=True)
            #print(api_response)
            return api_response
        except ApiException as e:
            print("Exception when calling CoreV1Api->create_namespaced_config_map: %s\n" % e)
            return None
    else:
        print("Ooops, a name for the ConfigMap was not passed properly, please retry.  Params passed: name={name}, namespace={namespace}".format(name=name, namespace=namespace))
        return None


if __name__ == '__main__':
    main()
