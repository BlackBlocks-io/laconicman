# Laconicman

**Laconicman** is a command-line utility designed to interact with Kubernetes Ingress resources and manage related Laconic deployments. It helps you identify and clean up resources associated with Ingresses, query GraphQL endpoints for Laconic registry records, and ensure that critical deployments are protected from accidental deletion.

## Features

- **Fetch Ingresses**: Retrieve all Ingress resources from the Kubernetes cluster.
- **GraphQL Query**: Query a GraphQL API to check for related DNS records and application deployment records.
- **Display Results**: View detailed results in a tabular format, showing which Ingresses are missing specific records.
- **Resource Cleanup**: Optionally clean up Kubernetes resources (Deployments) related to Ingresses, with built-in protection for critical deployments.
- **Interactive Shell**: Navigate through an interactive menu to perform various operations.

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/your-username/laconicman.git
   cd laconicman
   ```

2. **Install Dependencies**

    Ensure you have **python3**, **pip**, **jq**, and **kubectl** installed. Then, install the required Python packages:

    ```bash

    pip install -r requirements.txt
    ```

## Usage

1. **Run the Interactive Shell**


    Start the interactive shell by running:

    ```bash

    python laconicman.py
    ```
2. **Main Menu Options**
    - Show all Ingress hosts: Lists all Ingress hosts.
    - Check all Ingress hosts: Queries GraphQL for each Ingress host and displays the results.
    - Show all where only the DeploymentRecord is missing: Filters and displays Ingresses missing only  the Application Deployment Record.
    - Show all where both DNS and DeploymentRecord are missing: Filters and displays Ingresses missing both DNS and Application Deployment Record.
    - Show related Deployments, Pods, Services: Lists related Kubernetes resources for all Ingresses.
    - Cleanup (!!! Dangerous and Experimental !!!): Deletes Deployments related to Ingresses based on specific criteria. Use with caution!
        -Option 1: Deletes all Ingresses where both DNS and Application Deployment Record are missing.
        - Option 2: Deletes all Ingresses where only the Application Deployment Record is missing.
    - Exit: Exits the interactive shell.

3. **Protected Deployments**

    The following patterns are protected from deletion:
    - **webapp-deployer-api.pwa.***
    - **container-registry.pwa.***
    - **webapp-deployer-ui.pwa.***

    Deployments matching these patterns will not be deleted, even when performing cleanup operations.

## Configuration

    **GraphQL Endpoint**: Update the **GRAPHQL_ENDPOINT** variable in **laconicman.py** with the URL of your GraphQL endpoint.

## Example

To check all Ingress hosts and their associated records, run:

```bash

python laconicman.py
```
Select option 2 from the main menu to perform the check and display results.

## Caution

- **Cleanup Operations**: The cleanup feature is experimental and can potentially delete important resources. Make sure to review the resources to be deleted before confirming any deletion.
- **Protected Deployments**: Ensure the patterns for protected deployments are correctly configured to avoid accidental deletion of critical services.

## Screenshots
![image](https://github.com/user-attachments/assets/f0475014-640e-4de1-94ec-691ced56edb6)
![image](https://github.com/user-attachments/assets/ea3bcb2e-17ef-4a01-be93-1a75601c9249)
![image](https://github.com/user-attachments/assets/19462a55-ca1f-4935-9e82-07e41e8600e4)
![image](https://github.com/user-attachments/assets/4767619d-ea1d-4f37-a7d7-1a43c3f64bd8)
![image](https://github.com/user-attachments/assets/51d4c2e8-c8c1-43b3-8942-e890e2d7abf8)
![image](https://github.com/user-attachments/assets/c374cba8-df1b-4ee0-ac60-5914b9e1d28f)


## Contributing

Feel free to contribute by submitting issues or pull requests. For any questions or feedback, please open an issue on this repository.
## License

This project is licensed under the MIT License. See the LICENSE file for details.
