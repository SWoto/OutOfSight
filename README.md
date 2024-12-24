# OutOfSight

OutOfSight is a solution designed to encrypt and decrypt PDF files.

## Overview

OutOfSight provides a web-based platform where authenticated users can:

- Encrypt and securely back up their PDF files using user-specific encryption keys.
- Download encrypted files or decrypt them directly before downloading.

## Features

- **Encryption**: Protect sensitive PDF files with user-specific encryption keys.
- **Decryption**: Retrieve files in their original form when needed.
- **Backup**: Securely back up encrypted files to the cloud.
- **Web Interface**: A user-friendly platform for managing file encryption and backups.

## Cloud Integration

This solution integrates with AWS Cloud Services to ensure secure storage and seamless file management. 

- **Amazon S3**: For encrypted file storage and retrieval.
- **Amazon EC2**: To host the FastAPI backend.
- **Amazon RDS**: To manage user data and authentication details.

## Contributing

Follow these steps to set up your local environment for development.

#### [Create a virtual environment in the terminal](https://code.visualstudio.com/docs/python/environments#_create-a-virtual-environment-in-the-terminal)
```shell
# You may need to run `sudo apt-get install python3-venv` first on Debian-based OSs
python3 -m venv .venv
```
After creating the virtual environment ensure that it is used for running commands on the terminal.

#### Installing dependencies
```shell
pip install -r requirements.txt
```

## Running
```shell
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --log-level debug --workers 3 --reload
```

# AWS Setup

## VPC

You can use the AWS VPC creation wizard ("VPC and more") for a streamlined setup, or you can configure the VPC manually for better control and understanding. Below are instructions for both approaches.

---

### Using the "VPC and more" Wizard

1. **Navigate to the VPC Dashboard**:
   - Select **VPC and more** under the creation options.

1. **Configuration**:
   - **Name**: Choose a base name for all items (e.g., `oos`) and it will automatically rename all the other items.
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
   - Add a **Name Tag** (e.g., `oos-vpc`).
   - Choose **IPv4 CIDR manual input** and set the **IPv4 CIDR block** to `10.0.0.0/16`.
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
       - Name: `oos-public-subnet`
       - IPv4 CIDR block: `10.0.1.0/24`
     - **Private Subnet**:
       - Name: `oos-private-subnet`
       - IPv4 CIDR block: `10.0.2.0/24`

---

#### Route Tables

1. **Rename the Default Route Table**:
   - Rename the route table created with the VPC to `oos-public-route-table`.

1. **Create a Private Route Table**:
   - Create a new route table and name it `oos-private-route-table`.

1. **Assign Subnets**:
   - By default, both subnets are associated with the route table created during the VPC creation. Update the configurations to assign **explicit** route tables to each subnet
   - Edit the **Subnet Associations** for each route table:
     - Assign `oos-public-route-table` to the **public subnet**.
     - Assign `oos-private-route-table` to the **private subnet**.

---

#### Internet Gateway

1. **Create an Internet Gateway**:
   - Navigate to the **Internet Gateways** section and create a new Internet Gateway.
   - Attach the Internet Gateway to the `oos-vpc`.

1. **Enable Internet Access for the Public Subnet**:
   - Edit the `oos-public-route-table` and add the following route:
     - **Destination**: `0.0.0.0/0`
     - **Target**: The created Internet Gateway.

---

## EC2 Setup

Follow these steps to create and configure an EC2 instance for the backend of OutOfSight.

---

### Launch an EC2 Instance

1. **Navigate to the EC2 Dashboard**:
   - Go to the **EC2 Dashboard** in the AWS Management Console.
   - Click **Launch Instance**.

1. **Configure Instance Details**:
   - **Name**: Enter `oos-ec2-backend` as the instance name.
   - **AMI (Amazon Machine Image)**: Select **Amazon Linux 2 AMI (HVM)**.
   - **Instance Type**: Choose `t2.micro` (free-tier eligible).

1. **Key Pair**:
   - Under **Key pair (login)**, select **Create new key pair**:
     - **Key pair name**: Enter `oos-key-pair`.
     - **Key pair type**: Select `RSA` (default).
     - **Private key file format**: Choose `.pem` (for SSH access).
   - Click **Create key pair** and download the `.pem` file.
   - Move the `.pem` file to your `.ssh` directory (e.g., `~/.ssh/oos-key-pair.pem`) and secure it with the following command:
     ```bash
     chmod 0400 ~/.ssh/oos-key-pair.pem
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
         - If you're using MacOS, note that private relay might disturb this proccess if you're filtering with "My IP".
     - **Custom ICMP - IPv4, Echo Request**: To enable ping to the EC2, select anywhere IPv4 or from your IP only.
   - Save the updated rules.

1. **Connect to the Instance**:
   - Change permission
   - Use the `.pem` file from the key pair to SSH into the instance:
     ```bash
     ssh -i "oos-key-pair.pem" ec2-user@<instance-public-ip>
     ```
   - Replace `<instance-public-ip>` with the public IP address of your EC2 instance.

1. **Install Required Software**:
   After running the user data script, basic programs should already be installed. After installing docker and giving permissions to ec2-user, **it is recommended to reboot the EC2 instance**.

---