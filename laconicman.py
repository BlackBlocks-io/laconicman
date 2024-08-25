import subprocess
import requests
import json
import sys
import fnmatch
from prettytable import PrettyTable

# GraphQL Endpoint
GRAPHQL_ENDPOINT = 'https://laconicd.laconic.com/api'

# GraphQL Query with attribute filters
QUERY_TEMPLATE = '''
query($dnsName: String!, $appUrl: String!) {
  dnsRecords: queryRecords(attributes: [{key: "type", value: {string: "DnsRecord"}}, {key: "name", value: {string: $dnsName}}]) {
    id
    attributes {
      key
      value {
        ...ValueParts
      }
    }
  }
  appDeploymentRecords: queryRecords(attributes: [{key: "type", value: {string: "ApplicationDeploymentRecord"}}, {key: "url", value: {string: $appUrl}}]) {
    id
    attributes {
      key
      value {
        ...ValueParts
      }
    }
  }
}

fragment ValueParts on Value {
  ... on BooleanValue {
    bool: value
  }
  ... on IntValue {
    int: value
  }
  ... on FloatValue {
    float: value
  }
  ... on StringValue {
    string: value
  }
  ... on BytesValue {
    bytes: value
  }
  ... on LinkValue {
    link: value
  }
}
'''

def run_command(command):
    """Executes a shell command and returns the output."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def get_ingresses():
    """Fetches all Ingress resources from the Kubernetes cluster."""
    output = run_command('kubectl get ingresses --all-namespaces -o json')
    ingresses = json.loads(output)
    return ingresses['items']

def query_graphql(dns_name, app_url):
    """Executes a GraphQL query for the given DNS name and application URL."""
    response = requests.post(
        GRAPHQL_ENDPOINT,
        json={'query': QUERY_TEMPLATE, 'variables': {'dnsName': dns_name, 'appUrl': app_url}},
        headers={'Content-Type': 'application/json'}
    )
    if response.status_code == 200:
        return response.json()['data']
    else:
        print(f"GraphQL error: {response.status_code}")
        return None

def fetch_and_cache_results():
    """Fetches all Ingress hosts and performs the GraphQL query. Results are cached."""
    ingresses = get_ingresses()
    results = {}
    total_ingresses = len(ingresses)
    print(f"Total Ingresses to check: {total_ingresses}", end='\n')
    
    for idx, ingress in enumerate(ingresses):
        name = ingress['metadata']['name']
        for rule in ingress.get('spec', {}).get('rules', []):
            if 'host' in rule:
                host = rule['host']
                app_url = f"https://{host}"
                dns_name = host
                data = query_graphql(dns_name, app_url)
                results[host] = {
                    'name': name,
                    'data': data
                }
        # Update progress
        sys.stdout.write(f"\rChecked {idx + 1}/{total_ingresses} ingresses")
        sys.stdout.flush()
    
    print()  # New line after completion
    return results

def display_table(results):
    """Displays all results in a single table."""
    table = PrettyTable()
    table.field_names = ["Ingress Name", "Host", "ApplicationDeploymentRecord", "DnsRecord"]

    for host, result in results.items():
        name = result['name']
        data = result['data']
        app_deployment_record_exists = len(data['appDeploymentRecords']) > 0 if data else False
        dns_record_exists = len(data['dnsRecords']) > 0 if data else False

        app_record_status = 'ok' if app_deployment_record_exists else '-'
        dns_record_status = 'ok' if dns_record_exists else '-'
        table.add_row([name, host, app_record_status, dns_record_status])

    print("\nResults:")
    print(table)

def display_filtered_results(results, missing_deployment=False, missing_dns=False):
    """Displays the Ingress results that match the filter criteria."""
    table = PrettyTable()
    table.field_names = ["Ingress Name", "Host", "ApplicationDeploymentRecord", "DnsRecord"]
    
    for host, result in results.items():
        name = result['name']
        data = result['data']
        app_deployment_record_exists = len(data['appDeploymentRecords']) > 0 if data else False
        dns_record_exists = len(data['dnsRecords']) > 0 if data else False

        if missing_deployment and not app_deployment_record_exists and dns_record_exists:
            app_record_status = '-'
            dns_record_status = 'ok'
            table.add_row([name, host, app_record_status, dns_record_status])
        elif missing_dns and not dns_record_exists and not app_deployment_record_exists:
            app_record_status = '-'
            dns_record_status = '-'
            table.add_row([name, host, app_record_status, dns_record_status])
    
    print("\nFiltered Results:")
    print(table)

def get_related_k8s_resources(ingress_name):
    """Finds the related Kubernetes resources for the given Ingress name."""
    resources = {}

    # Extract the namespace of the Ingress
    namespace_command = f'kubectl get ingress {ingress_name} -o json'
    namespace_output = run_command(namespace_command)
    
    try:
        # Extract the namespace from the JSON output
        namespace = json.loads(namespace_output)['metadata']['namespace']
    except KeyError:
        print(f"No namespace found for Ingress {ingress_name}.")
        return resources
    
    if not namespace:
        print(f"No namespace found for Ingress {ingress_name}.")
        return resources

    # Extract the name prefix from the Ingress name
    name_prefix = ingress_name.split('-ingress')[0]

    # Find Pods, Deployments, ReplicaSets, and Services
    resources['Pods'] = run_command(f'kubectl get pods --namespace {namespace} -o json | jq -r \'.items[] | select(.metadata.name | startswith("{name_prefix}")) | .metadata.name\'')
    resources['Deployments'] = run_command(f'kubectl get deployments --namespace {namespace} -o json | jq -r \'.items[] | select(.metadata.name | startswith("{name_prefix}")) | .metadata.name\'')
    resources['ReplicaSets'] = run_command(f'kubectl get replicasets --namespace {namespace} -o json | jq -r \'.items[] | select(.metadata.name | startswith("{name_prefix}")) | .metadata.name\'')
    resources['Services'] = run_command(f'kubectl get services --namespace {namespace} -o json | jq -r \'.items[] | select(.metadata.name | startswith("{name_prefix}")) | .metadata.name\'')
    
    return resources

def get_ingress_host(ingress_name):
    """Gets the host of the Ingress based on its name."""
    output = run_command(f'kubectl get ingress {ingress_name} -o jsonpath="{{.spec.rules[0].host}}"')
    return output.strip()

def display_related_resources(ingresses):
    """Displays the related Kubernetes resources for all given Ingress names."""
    table = PrettyTable()
    table.field_names = ["Ingress Name", "Host", "Pods", "Deployments", "ReplicaSets", "Services"]

    total_ingresses = len(ingresses)
    for idx, ingress_name in enumerate(ingresses):
        host = get_ingress_host(ingress_name)
        resources = get_related_k8s_resources(ingress_name)
        
        pods = resources.get('Pods', '').strip()
        deployments = resources.get('Deployments', '').strip()
        replicasets = resources.get('ReplicaSets', '').strip()
        services = resources.get('Services', '').strip()
        
        # Fill table with resources
        table.add_row([
            ingress_name,
            host if host else 'No host found',
            pods if pods else 'No Pods found',
            deployments if deployments else 'No Deployments found',
            replicasets if replicasets else 'No ReplicaSets found',
            services if services else 'No Services found'
        ])

        # Show progress
        sys.stdout.write(f"\rProgress: {idx + 1}/{total_ingresses} Ingresses")
        sys.stdout.flush()
    
    print()  # New line after completion
    print("\nResources for all Ingresses:")
    print(table)

def delete_deployments(deployments):
    """Lists and deletes the specified deployments after user confirmation, protecting specific patterns."""
    protected_patterns = [
        'webapp-deployer-api.pwa.*',
        'container-registry.pwa.*',
        'webapp-deployer-ui.pwa.*'
    ]

    deployment_list = deployments.split('\n')
    deployment_list = [d for d in deployment_list if d]  # Remove empty entries

    if not deployment_list:
        print("No deployments found for deletion.")
        return

    # Separate protected and deletable deployments
    protected_deployments = []
    deletable_deployments = []

    for deployment in deployment_list:
        if any(fnmatch.fnmatch(deployment, pattern) for pattern in protected_patterns):
            protected_deployments.append(deployment)
        else:
            deletable_deployments.append(deployment)

    # Print all deployments
    print("\nAll Deployments:")
    for deployment in deployment_list:
        status = "Protected" if deployment in protected_deployments else "Deletable"
        print(f"  {deployment} ({status})")

    if protected_deployments:
        print("\nProtected Deployments that will not be deleted:")
        for deployment in protected_deployments:
            print(f"  {deployment}")

    if deletable_deployments:
        print("\nDeletable Deployments to be deleted:")
        for deployment in deletable_deployments:
            print(f"  {deployment}")
        
        confirm = input("\nDo you really want to delete these deployments? (yes/no): ").strip().lower()
        if confirm == 'yes':
            for deployment in deletable_deployments:
                print(f"Deleting deployment {deployment}...")
                run_command(f'kubectl delete deployment {deployment} --ignore-not-found')
            print("Deployments have been deleted.")
        else:
            print("Deletion aborted.")
    else:
        print("No deletable deployments found.")


def delete_resources(resources):
    """Deletes the specified resources."""
    for resource_type, resource_list in resources.items():
        if resource_list:
            print(f"\nDeleting {resource_type}:")
            for resource in resource_list.split('\n'):
                if resource:
                    print(f"Deleting {resource_type[:-1].lower()} {resource}...")
                    run_command(f'kubectl delete {resource_type[:-1].lower()} {resource} --ignore-not-found')

def display_welcome_message():
    """Displays the welcome ASCII art and program name."""
    ascii_art = '''


                                                                                                                               
                                                                                                                               
                                                                                                                               
                                                                                                                               
                                                                                                                               
                    ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                                                                                                                               
                                                                                                                               
                                                                                                                               
                                                                                                                               
                                                                                                                               
          ↑↑↑↑↑↑↑↑↑                                      ↑↑↑↑↑↑↑↑↑↑                                                            
          ↑       ↑↑ ↑          ↑↑     ↑↑↑↑↑↑↑↑  ↑    ↑↑ ↑↑       ↑↑ ↑       ↑↑↑↑↑↑↑↑↑   ↑↑↑↑↑↑↑↑  ↑    ↑↑  ↑↑↑↑↑↑↑↑           
          ↑↑↑↑↑↑↑↑↑↑ ↑↑        ↑↑↑↑   ↑↑         ↑ ↑↑↑↑  ↑↑↑↑↑↑↑↑↑↑  ↑      ↑↑       ↑↑ ↑↑         ↑ ↑↑↑↑  ↑↑                  
          ↑       ↑↑ ↑↑       ↑↑  ↑↑  ↑↑         ↑↑↑↑    ↑↑      ↑↑↑ ↑      ↑↑        ↑ ↑↑         ↑↑↑↑     ↑↑↑↑↑↑↑↑↑          
          ↑        ↑ ↑↑      ↑↑↑↑↑↑↑↑ ↑↑         ↑   ↑↑  ↑↑       ↑↑ ↑      ↑↑       ↑↑ ↑↑         ↑   ↑↑           ↑          
          ↑↑↑↑↑↑↑↑↑↑ ↑↑↑↑↑↑↑↑↑      ↑↑ ↑↑↑↑↑↑↑↑↑ ↑     ↑ ↑↑↑↑↑↑↑↑↑↑  ↑↑↑↑↑↑↑  ↑↑↑↑↑↑↑    ↑↑↑↑↑↑↑↑↑ ↑     ↑ ↑↑↑↑↑↑↑↑↑↑          
                                                                                                                               
                                                                                                                               
                                                                                                                               
                                                                                                                               
                                                                                                                               
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑                                                                                     ↑                    
                    ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑                    
                                                                                                                               
                                                                                                                               
                                                                                                                               
                                                                                                                               
                                                                                                                               



'''
    print(ascii_art)
    print("Welcome to Laconicman!")

def interactive_shell():
    display_welcome_message()
    cached_results = None
    
    while True:
        print("\nMain Menu:")
        print("1. Show all Ingress hosts")
        print("2. Check all Ingress hosts")
        print("3. Show all where only the DeploymentRecord is missing")
        print("4. Show all where both DNS and DeploymentRecord are missing")
        print("5. Show related Deployments, Pods, Services")
        print("6. Cleanup (!!! Dangerous and Experimental !!!)")
        print("7. Exit")

        try:
            choice = input("\nSelect an option (1-7): ").strip()
            
            if choice == '1':
                ingresses = get_ingresses()
                print("\nIngress Hosts:")
                for ingress in ingresses:
                    name = ingress['metadata']['name']
                    for rule in ingress.get('spec', {}).get('rules', []):
                        if 'host' in rule:
                            print(f"{name} - {rule['host']}")

            elif choice == '2':
                print("\nChecking all Ingress hosts...")
                cached_results = fetch_and_cache_results()
                print("\nCheck completed.")
                display_table(cached_results)
            
            elif choice == '3':
                if cached_results is None:
                    print("Please run option 2 first.")
                else:
                    print("\nShow all where only the DeploymentRecord is missing...")
                    display_filtered_results(cached_results, missing_deployment=True)
            
            elif choice == '4':
                if cached_results is None:
                    print("Please run option 2 first.")
                else:
                    print("\nShow all where both DNS and DeploymentRecord are missing...")
                    display_filtered_results(cached_results, missing_dns=True)
            
            elif choice == '5':
                ingresses = get_ingresses()
                ingress_names = [ingress['metadata']['name'] for ingress in ingresses]
                print("\nShowing related Deployments, Pods, Services for all Ingresses...")
                display_related_resources(ingress_names)
                
            elif choice == '6':
                if cached_results is None:
                    print("Please run option 2 first.")
                else:
                    print("\nCleanup Menu:")
                    print("1. All where both DNS and DeploymentRecord are missing")
                    print("2. All where only DeploymentRecord is missing")

                    cleanup_choice = input("\nSelect an option (1-2): ").strip()
                    
                    if cleanup_choice == '1':
                        filtered_results = {host: result for host, result in cached_results.items()
                                            if not result['data']['appDeploymentRecords'] and not result['data']['dnsRecords']}
                        if filtered_results:
                            display_table(filtered_results)
                            confirm = input("\nDo you really want to delete these resources? (yes/no): ").strip().lower()
                            if confirm == 'yes':
                                for host, result in filtered_results.items():
                                    name = result['name']
                                    resources = get_related_k8s_resources(name)
                                    delete_deployments(resources.get('Deployments', ''))
                                    print(f"Resources for Ingress {name} have been deleted.")
                            else:
                                print("Deletion aborted.")
                        else:
                            print("No resources found for deletion.")
                    
                    elif cleanup_choice == '2':
                        filtered_results = {host: result for host, result in cached_results.items()
                                            if not result['data']['appDeploymentRecords'] and result['data']['dnsRecords']}
                        if filtered_results:
                            display_table(filtered_results)
                            confirm = input("\nDo you really want to delete these resources? (yes/no): ").strip().lower()
                            if confirm == 'yes':
                                for host, result in filtered_results.items():
                                    name = result['name']
                                    resources = get_related_k8s_resources(name)
                                    delete_deployments(resources.get('Deployments', ''))
                                    print(f"Deployments for Ingress {name} have been deleted.")
                            else:
                                print("Deletion aborted.")
                        else:
                            print("No resources found for deletion.")
                    
                    else:
                        print("Invalid choice. Please select 1 or 2.")

            elif choice == '7':
                print("Exiting the shell.")
                break

            else:
                print("Invalid option. Please select a number between 1 and 7.")
        
        except (EOFError, KeyboardInterrupt):
            print("\nExiting the shell.")
            break

if __name__ == "__main__":
    interactive_shell()
