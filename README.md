# CloudFlow

CloudFlow is a file processing solution built with FastAPI, AWS EC2, AWS S3, SQS, and Lambda. It demonstrates how to handle file uploads, process files asynchronously, and store results in the cloud.

# Overview

CloudFlow provides a backend API for uploading files and processing them asynchronously using AWS services. The workflow includes:

1. **File Upload**: Users upload files via a FastAPI endpoint hosted on an EC2 instance.
2. **Cloud Storage**: Files are stored in an S3 bucket.
3. **Message Queue**: An SQS queue is use for queuing the tasks.
4. **File Processing**: AWS Lambda processes the files and saves the results to another S3 bucket.


## Workflow

1. **Upload File**:
   - Send a POST request to the `/upload` endpoint hosted on an EC2 instance with a file.
   - The file is saved to the **Input S3 Bucket**.
   - A message is sent to the **SQS Queue** with file metadata.

2. **Process File**:
   - AWS Lambda is triggered by the SQS message.
   - The Lambda function processes the file (e.g., extracts text, converts format).
   - The processed file is saved to the **Output S3 Bucket**.

3. **Retrieve Processed File**:
   - Users can download the processed file from the **Output S3 Bucket**.

## AWS Services Used

- **EC2**: Hosts the FastAPI backend.
- **S3**: For storing raw and processed files.
- **SQS**: For message queuing and triggering Lambda.
- **Lambda**: For serverless file processing.
- **FastAPI**: For the backend API.

## Getting Started

### Prerequisites

- AWS account with necessary permissions.
- Python 3.10+ and FastAPI installed.
- AWS CLI configured.

### Deployment

**Clone this repository**:
   ```bash
   git clone https://github.com/SWoto/CloudFront.git
   ```

**Run Docker Compose**:
The second command of each block shows how to specify the compose file to be run.
```
docker compose up
docker compose -f docker-compose.yml up
```
or 
```
docker compose up --build
docker compose -f docker-compose.yml up --build
```
to force building the containers.

**Folders and Permissions**

As instructed in [Mapped Files and Directories](https://www.pgadmin.org/docs/pgadmin4/latest/container_deployment.html#mapped-files-and-directories), database folder needs to have the propper permissions,
```
sudo chown -R 5050:5050 <host_directory>
```

Note: database folder is a shared volume defined in docker-compose.yml for pgadmin.

### Local Enviroment

Follow these steps to set up your local environment for development.

#### Docker

To begin, use the docker-compose file with the Dockerfile.dev for development and testing (`docker compose -f docker-compose.dev.yml up`). Access the container through VS Code's remote development feature and configure SSH port forwarding for remote connection to an AWS RDS database. This is done using EC2 permissions. For example, execute the following command: `ssh -i .ssh/<my-key>.pem -4 -fNT -L 3307:<my-AWS-PostgreSQL-Endpoint>:5432 ec2-user@<my-EC2-Public-IPv4-DNS>`.
Example:
```bash
ssh -i .ssh/my-key.pem -4 -fNT -L 3307:cf-database-1.acbd12345.region.rds.amazonaws.com:543
2 ec2-user@ec2-12-34-56-78.region.compute.amazonaws.com
```

Once the SSH tunnel is set up, modify the `.env` file parameters to point to the local forwarded port:
```makefile
POSTGRES_PORT=3307
POSTGRES_HOST=host.docker.internal
```

This approach ensures changes made to the code inside the container are synchronized with the host environment. While it’s possible to clone the repository inside the container, this would require cloning it twice—once on the host to access Docker files and once inside to run the application. Using the described method avoids this duplication.

#### Running the Application

After setting up the container, ensure the terminal is using the virtual environment configured in `Dockerfile.dev`. Then, start the application using the following command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug --workers 3 --reload
```

# AWS Setup

## VPC

You can use the AWS VPC creation wizard ("VPC and more") for a streamlined setup, or you can configure the VPC manually for better control and understanding. Below are instructions for both approaches.

---

### Using the "VPC and more" Wizard

1. **Navigate to the VPC Dashboard**:
   - Select **VPC and more** under the creation options.

1. **Configuration**:
   - **Name**: Chcfe a base name for all items (e.g., `cf`) and it will automatically rename all the other items.
   - **IPv4 CIDR block**: Leave as default (`10.0.0.0/16`).
   - **Number of Availability Zones**: Set to `1`.
   - **Number of Subnets**: 
     - Public Subnets: `1`
     - Private Subnets: `1`
   - **NAT Gateways**: Select **None**.
   - **VPC Endpoints**: Select **None**.
   - **DNS Options**: Ensure both are checked:
     - **Enable DNS hostnames**
     - **Enable DNS resolution**

1. **Create**:
   - Click **Create VPC**. The wizard will automatically generate the required resources with appropriate names based on the VPC name.

---

### Manual VPC Configuration


1. **Create a VPC**:
   - Navigate to the **VPC Dashboard** and select **Create VPC** > **VPC only**.
   - Add a **Name Tag** (e.g., `cf-vpc`).
   - Chcfe **IPv4 CIDR manual input** and set the **IPv4 CIDR block** to `10.0.0.0/16`.
   - Select **No IPv6 CIDR block**.
   - Leave **Tenancy** as **Default**.
   - Click **Create VPC**.

1. **Enable DNS Hostnames**:
   - After creation, edit the VPC settings and enable the option **Enable DNS Hostnames**.

---

#### Subnets

1. **Create Subnets**:
   - Go to the **Subnets** section and create the following:
     - **Public Subnet**:
       - Name: `cf-public-subnet`
       - IPv4 CIDR block: `10.0.1.0/24`
     - **Private Subnet**:
       - Name: `cf-private-subnet`
       - IPv4 CIDR block: `10.0.2.0/24`

---

#### Route Tables

1. **Rename the Default Route Table**:
   - Rename the route table created with the VPC to `cf-public-route-table`.

1. **Create a Private Route Table**:
   - Create a new route table and name it `cf-private-route-table`.

1. **Assign Subnets**:
   - By default, both subnets are associated with the route table created during the VPC creation. Update the configurations to assign **explicit** route tables to each subnet
   - Edit the **Subnet Associations** for each route table:
     - Assign `cf-public-route-table` to the **public subnet**.
     - Assign `cf-private-route-table` to the **private subnet**.

---

#### Internet Gateway

1. **Create an Internet Gateway**:
   - Navigate to the **Internet Gateways** section and create a new Internet Gateway.
   - Attach the Internet Gateway to the `cf-vpc`.

1. **Enable Internet Access for the Public Subnet**:
   - Edit the `cf-public-route-table` and add the following route:
     - **Destination**: `0.0.0.0/0`
     - **Target**: The created Internet Gateway.

---

## EC2 Setup

Follow these steps to create and configure an EC2 instance for the backend of CloudFront.

---

### Launch an EC2 Instance

1. **Navigate to the EC2 Dashboard**:
   - Go to the **EC2 Dashboard** in the AWS Management Console.
   - Click **Launch Instance**.

1. **Configure Instance Details**:
   - **Name**: Enter `cf-ec2-backend` as the instance name.
   - **AMI (Amazon Machine Image)**: Select **Amazon Linux 2 AMI (HVM)**.
   - **Instance Type**: Choose `t2.micro` (free-tier eligible).

1. **Key Pair**:
   - Under **Key pair (login)**, select **Create new key pair**:
     - **Key pair name**: Enter `cf-key-pair`.
     - **Key pair type**: Select `RSA` (default).
     - **Private key file format**: Choose `.pem` (for SSH access).
   - Click **Create key pair** and download the `.pem` file.
   - Move the `.pem` file to your `.ssh` directory (e.g., `~/.ssh/cf-key-pair.pem`) and secure it with the following command:
     ```bash
     chmod 0400 ~/.ssh/cf-key-pair.pem
     ```
     > This ensures the file is not readable by others, avoiding SSH error "unprotected private key file."

1. **Network Settings**:
   - Under **Network settings**, select **Edit**.
   - Choose an **Existing Security Group**:
     - Use the one associated with your VPC, starting with `vpc-`.
   - **Note**: We will repurpose this security group in later steps.

1. **User Data**
This script will be use to pre install docker and git when the instance is launched.

For logs after installation, access it using SSH and run `sudo cat /var/log/cloud-init-output.log`.

```shell
#!/bin/bash
# Update system packages
echo "Starting user data script"
yum update -y

# Check if Git is installed
if ! command -v git &> /dev/null; then
    echo "Git not found. Installing Git..."
    yum install git -y
else
    echo "Git is already installed."
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Installing Docker..."
    amazon-linux-extras install docker -y
    systemctl start docker
    systemctl enable docker
    usermod -aG docker ec2-user
    echo "Docker installed and configured."
else
    echo "Docker is already installed."
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose not found. Installing the latest version of Docker Compose..."
    # Install for all users
    DOCKER_CONFIG=/usr/local/lib/docker
    # Install for current user
    # DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
    mkdir -p $DOCKER_CONFIG/cli-plugins
    curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m) -o $DOCKER_CONFIG/cli-plugins/docker-compose
    chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose
    docker compose version
else
    echo "Docker Compose is already installed."
fi

# Confirm the setup is complete
echo "Setup complete. Git, Docker and Docker Compose are ready to use."
```
**NOTE:** check the information at "Install Required Software".

1. **Other Settings**:
   - Leave the default settings for **Storage** and other options unless specific customizations are needed.

1. **Launch**:
   - Click **Launch Instance** to create the EC2 instance.

---

### Post-Launch Configuration

1. **Security Group Configuration**:
   - Navigate to the **Security Groups** section in the EC2 Dashboard.
   - Select the security group associated with your instance.
   - Modify the **Inbound Rules** to allow the necessary traffic:
     - **HTTP (Port 80)**: For your IP only or open if needed.
     - **SSH (Port 22)**: For administrative access (from your IP only).
         - If you're using MacOS, note that private relay might disturb this proccess if you're filtering with "My IP", given that safari is going to 'use' a different IP from VSCode. An alternativa is to set the 'MyIP' through another browswer, like firefox, instead of safari. 
     - **Custom ICMP - IPv4, Echo Request**: To enable ping to the EC2, select anywhere IPv4 or from your IP only.
   - Save the updated rules.

1. **Connect to the Instance**:
   - Change permission
   - Use the `.pem` file from the key pair to SSH into the instance:
     ```bash
     ssh -i "cf-key-pair.pem" ec2-user@<instance-public-ip>
     ```
   - Replace `<instance-public-ip>` with the public IP address of your EC2 instance.

1. **Install Required Software**:
   After running the user data script, basic programs should already be installed. After installing docker and giving permissions to ec2-user, **it is recommended to reboot the EC2 instance**.

---