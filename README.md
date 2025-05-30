# CloudFlow

CloudFlow is a file processing solution built with FastAPI, AWS EC2, AWS S3, SQS, and Lambda. It demonstrates how to handle file uploads, process files asynchronously, and store results in the cloud.

Note, this is only a backend implementation and doesn’t have any UI developed as part of this.

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

As instructed in [Mapped Files and Directories](https://www.pgadmin.org/docs/pgadmin4/latest/container_deployment.html#mapped-files-and-directories), database folder needs to have the proper permissions,
```
sudo chown -R 5050:5050 <host_directory>
```

Note: database folder is a shared volume defined in docker-compose.yml for pgadmin.

### Local Environment

Follow these steps to set up your local environment for development.

#### Docker

To begin, use the docker-compose file with the Dockerfile.dev for development and testing (`docker compose -f docker-compose.dev.yml up`). Access the container through VS Code's remote development feature and configure SSH port forwarding for remote connection to an AWS RDS database. This is done using EC2 permissions. For example, execute the following command: `ssh -i .ssh/<my-key>.pem -4 -fNT -L 3307:<my-AWS-PostgreSQL-Endpoint>:5432 ec2-user@<my-EC2-Public-IPv4-DNS>`.
Example:
```bash
ssh -i .ssh/my-key.pem -4 -fNT -L 3307:cf-database-1.acbd12345.region.rds.amazonaws.com:5432 ec2-user@ec2-12-34-56-78.region.compute.amazonaws.com
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
   - **Name**: Choose a base name for all items (e.g., `cf`) and it will automatically rename all the other items.
   - **IPv4 CIDR block**: Leave as default (`10.0.0.0/16`).
   - **Number of Availability Zones**: Set to `1`.
   - **Number of Subnets**: 
     - Public Subnets: `1`
     - Private Subnets: `1`
   - **NAT Gateways**: Select **None**.
   - **VPC Endpoints**: Select **None**.
   - **DNS Options**: Ensure both are checked:
     - **Enable DNS hostname**
     - **Enable DNS resolution**

1. **Create**:
   - Click **Create VPC**. The wizard will automatically generate the required resources with appropriate names based on the VPC name.

---

### Manual VPC Configuration


1. **Create a VPC**:
   - Navigate to the **VPC Dashboard** and select **Create VPC** > **VPC only**.
   - Add a **Name Tag** (e.g., `cf-vpc`).
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

<details>
<summary>Code for User Data in EC2</summary>

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
</details>

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
         - If you're using MacOS, note that private relay might disturb this process if you're filtering with "My IP", given that safari is going to 'use' a different IP from VSCode. An alternative is to set the 'MyIP' through another browser, like firefox, instead of safari. 
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


## SQS - Creating Queues

1. Navigate to Amazon SQS > Queues.
1. Click Create queue.
1. Keep all default parameters unchanged.
1. Set the queue name to `cf-email-confirmation`.
1. Click Create queue.

Repeat for queue `cf-preprocessing-queue`.

## SES - Email Configuration
To set up SES without purchasing a domain, you can register your own email as both the sender and recipient.

1. Open Amazon SES (Simple Email Service).
1. Navigate to Configuration > Identities.
1. Click Create Identity.
1. Select Email address and enter an email address that you own.
1. Verify your email address by clicking the confirmation link in the email you receive.

_Optional: If you need to send emails to unverified addresses, request production access for SES._


## IAM Role - Creating the Required Permissions
An IAM role is needed to grant permissions to the Lambda function.

1. Open IAM (Identity and Access Management).
1. Go to Access Management > Roles.
1. Click Create Role.
1. Under AWS Service, select Lambda as the use case.
1. Attach the following permission policies:
   - `AmazonSESFullAccess`
   - `AWSLambdaSQSQueueExecutionRole`
1. Name the role `lambda-sqs-ses-confirmation-email`.
1. Click Create Role.


## Lambda Function - `lambda-sqs-ses-confirmation-email`

### Creating 

1. Open AWS Lambda.
1. Click Create Function.
1. Choose Author from Scratch.
1. Set the function name to lambda-sqs-email.
1. Select Python 3.13 as the runtime.
1. In the Permissions section, change the default execution role:
   - Choose Use an existing role.
   - Select the previously created role: `lambda-sqs-ses-confirmation-email`.
1. Click Create function.

### Configuring 

1. Open the newly created Lambda function.
1. In the Function overview, click Add Trigger.
1. Select SQS as the trigger type.
1. Choose the `cf-email-confirmation queue`.
1. Click Add.

#### Environment Variables 

1. Add the following environment variables:
   - `QUEUE_URL`: Set this to the SQS queue URL.
   - `SENDER_EMAIL`: Set this to the verified email address in SES.

#### Code Implementation 

<details>
<summary>Lambda Python code</summary>

```python
import json
import boto3
import os
from botocore.exceptions import ClientError

#Initialize AWS clients
sqs = boto3.client('sqs')
ses = boto3.client('ses')

def lambda_handler(event, context):
    for record in event['Records']:
        message_body = json.loads(record['body'])

        sender_email = os.environ.get('SENDER_EMAIL')
        if not sender_email:
            return {
                'statusCode': 400,
                'body': json.dumps('Sender email not configured in environment variables')
            }

        client_email = message_body.get("email")
        client_nickname = message_body.get("nickname")
        confirmation_url = message_body.get("confirmation_url")
        if not all([client_email, client_nickname, confirmation_url]):
            return {
                'statusCode': 400,
                'body': json.dumps('Missing required fields in the msg_body')
            }
        
        #Get queue URL from environment variable
        queue_url = os.environ.get('QUEUE_URL')
        if not queue_url:
            return {
                'statusCode': 400,
                'body': json.dumps('Queue URL not configured in environment variables')
            }
        
        #Send confirmation email
        try:
            # for tests efect, we are going to use only the same email
            response = ses.send_email(
                Source=sender_email, #'no-reply@' + os.environ['DOMAIN'],
                Destination={
                    'ToAddresses': [
                        sender_email,
                    ]
                },
                Message={
                    'Subject': {
                            'Data': 'CloudFlow - Subscription Confirmation',
                            'Charset': 'UTF-8',
                    },
                    'Body': {
                        'Text': {
                            'Data': (
                                f"Hi {client_nickname}!\nYou have successfully signed up to the CloudFlow (CF)."
                                " Please confirm your email by clicking on the"
                                f" following link: {confirmation_url}. \n"
                                "Note: This link is valid only for 30 minutes."
                            ),
                            'Charset': 'UTF-8',
                        },
                        'Html':{
                            'Data':(
                                f"""<html>
                                    <body>
                                        <p>Hi {client_nickname}!</p>
                                        <p>You have successfully signed up to the CloudFlow (CF).</p>
                                        <p>Please confirm your email by clicking on the following link: <a href="{confirmation_url}">Confirm Email</a></p>
                                        <p>Note: This link is valid only for <b>30</b> minutes.</p>
                                    </body>
                                </html>"""
                            ),
                            'Charset': 'UTF-8',
                        },
                    }
                }
            )
            print("Email sent successfully:", response)
        except ClientError as e:
            print(e)
            return {
                'statusCode': 500,
                'body': json.dumps('Error sending email')
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps('Subscription successful')
        }
```
</details>

## Lambda Function - `lambda-sqs-fileprocessing`

A new Lambda function named **`lambda-sqs-fileprocessing`** was created to handle file status updates from messages received via SQS and persist metadata changes to an RDS PostgreSQL database.

### Trigger

- **SQS Queue**: `cf-preprocessing-queue`  
  The function is triggered whenever a new message arrives in this queue.

### Database Integration

- This Lambda connects to an **RDS PostgreSQL** database named `cf-database`.
- Connection credentials and database info are injected via **environment variables**.

### Environment Variables

Values are loaded dynamically and can be stored in a `.env` file locally:

| Variable    | Description                   |
|-------------|-------------------------------|
| DB_HOST     | Host of the RDS database      |
| DB_NAME     | Name of the database          |
| DB_USER     | Database username             |
| DB_PASSWORD | Database password             |
| DB_PORT     | (Optional) Database port (default: 5432) |

---

### IAM Role and Permissions

A custom execution role was attached to the Lambda function named **`lambda-sqs-s3-fileprocessing`** with the following policies:

#### Managed Policy
- `AWSLambdaSQSQueueExecutionRole` — allows processing SQS events.

#### Custom Policy: `S3CloudFronteDevReadWrite`

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject"
            ],
            "Resource": "arn:aws:s3:::cloudfront-dev-sa-east-1/*"
        }
    ]
}
```

---

### Creating the `psycopg2` Layer for AWS Lambda

To enable PostgreSQL support using `psycopg2`, a Lambda layer is required.

#### Set Up Your Environment

```bash
mkdir -p psycopg2-layer/python
cd psycopg2-layer/python
```

#### Install `psycopg2-binary`

**For `x86_64` architecture:**

```bash
pip3 install --platform manylinux2014_x86_64 --target . --python-version 3.13 --only-binary=:all: psycopg2-binary
```

**For `arm64` architecture:**

```bash
pip3 install --platform manylinux2014_aarch64 --target . --python-version 3.13 --only-binary=:all: psycopg2-binary
```

#### Package the Layer

```bash
cd ..
zip -r psycopg2-layer.zip python
```

#### Upload to AWS Lambda

1. Open the **AWS Lambda Console**  
1. Click **Layers** > **Create layer**  
1. Name the layer (e.g., `psycopg2-layer`)  
1. Upload `psycopg2-layer.zip`  
1. Set **runtime** to Python 3.12  
1. Select the correct **architecture**  
1. Click **Create**  

#### Attach Layer to Lambda

1. Open the `lambda-sqs-fileprocessing` function  
1. Go to the **Layers** section  
1. Click **Add a layer**  
1. Choose **Custom layers**  
1. Select the created `psycopg2-layer`  
1. Click **Add**

---

### Code Implementation 

<details>
<summary>Lambda Python code</summary>

```python
import json
import boto3
import os
from botocore.exceptions import ClientError
from typing import Optional, Tuple

# Layer
import psycopg2

sqs = boto3.client('sqs')
s3 = boto3.client('s3')

def update_db_status(file_id: str):
    try:
        conn = psycopg2.connect(
            host=os.environ['DB_HOST'],
            dbname=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASSWORD'],
            port=os.environ.get('DB_PORT', 5432)
        )
        cur = conn.cursor()

        cur.execute("SELECT id FROM files_status WHERE name = %s;", ('processed',))
        result = cur.fetchone()
        if not result:
            raise Exception("Status 'processed' not found in files_status table.")
        status_id = result[0]

        cur.execute("SELECT id FROM files_status_history WHERE file_id = %s AND status_id = %s;", (file_id, status_id))
        history_exists = cur.fetchone()

        if not history_exists:
            cur.execute("""
                INSERT INTO files_status_history (id, file_id, status_id, created_on, modified_on)
                VALUES (gen_random_uuid(), %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
            """, (file_id, status_id))
            print(f"Inserted new status history for file_id={file_id}")

        conn.commit()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def extract_s3_key(full_s3_uri: str) -> Tuple[Optional[str], str, str, str]:
    if full_s3_uri.startswith("s3://"):
        parts = full_s3_uri[5:].split("/", 1)
        bucket_name, file_key = parts[0], parts[1]
    else:
        file_key = full_s3_uri
        bucket_name = None

    parts = file_key.split("/")
    file_id, file_name = parts[-2], parts[-1]
    return bucket_name, file_key, file_id, file_name

def lambda_handler(event, context):
    for record in event['Records']:
        message_body = json.loads(record['body'])

        s3_path = message_body.get("s3_path")
        file_type = message_body.get("file_type")
        filename = message_body.get("filename")

        if not all([s3_path, file_type, filename]):
            message = 'Missing required fields in the msg_body'
            print(message)
            return {'statusCode': 400, 'body': json.dumps(message)}

        bucket, key, file_id, file_name = extract_s3_key(s3_path)

        """ # Optional metadata update (currently commented)
        try:
            head_response = s3.head_object(Bucket=bucket, Key=key)
            original_metadata = head_response.get("Metadata", {})

            updated_metadata = original_metadata.copy()
            updated_metadata["filetype"] = file_type
            updated_metadata["processed"] = "true"

            s3.copy_object(
                Bucket=bucket,
                CopySource={'Bucket': bucket, 'Key': key},
                Key=key,
                Metadata=updated_metadata,
                MetadataDirective='REPLACE',
                ContentType=head_response.get("ContentType", "application/octet-stream")
            )

            print(f"Metadata updated for {key} in bucket {bucket}")
        except ClientError as e:
            print(f'Error updating metadata for object {key} in bucket {bucket}: {e}')
            raise e
        """

        try:
            update_db_status(file_id)
            message = f'DB updated for file {key}'
            print(message)
            return {'statusCode': 200, 'body': json.dumps(message)}
        except Exception as e:
            print(f'Error updating DB for {key}: {e}')
            raise e
```
</details>