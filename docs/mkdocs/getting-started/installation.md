# Installation

This guide will help you install and set up the AgentCore CLI on your system.

## Prerequisites

Before installing the AgentCore CLI, ensure you have:

- **Python 3.11+** installed on your system
- **Docker** installed and running (for building and managing container images)
- **AWS CLI** configured with appropriate permissions
- Access to **Amazon Bedrock AgentCore Runtime** (Preview)

## Installation Options

=== "From PyPI (Recommended)"

    ```bash
    # Install using pip
    pip install agentcore-cli

    # Or using uv (recommended)
    uv pip install agentcore-cli
    ```

=== "From Source"

    ```bash
    # Clone the repository
    git clone https://github.com/theagenticguy/agentcore-cli.git
    cd agentcore-cli

    # Install dependencies using uv (recommended)
    uv sync

    # Or install using pip
    pip install -e .
    ```

## Verifying Installation

After installation, verify that the AgentCore CLI is working correctly:

```bash
agentcore-cli --version
```

You should see the version number and a welcome banner.

## AWS Credentials

The AgentCore CLI requires valid AWS credentials to function. You can set these up in several ways:

=== "AWS CLI Configuration"

    ```bash
    aws configure
    ```

    You'll be prompted to enter:

    - AWS Access Key ID
    - AWS Secret Access Key
    - Default region name
    - Default output format (optional)

=== "Environment Variables"

    ```bash
    export AWS_ACCESS_KEY_ID=your_access_key_id
    export AWS_SECRET_ACCESS_KEY=your_secret_access_key
    export AWS_DEFAULT_REGION=us-west-2
    ```

=== "AWS SSO"

    If your organization uses AWS Single Sign-On:

    ```bash
    aws sso login --profile your-sso-profile
    export AWS_PROFILE=your-sso-profile
    ```

=== "IAM Roles"

    If you're running on an EC2 instance or ECS container, you can use IAM roles attached to your compute resource.

## Required AWS Permissions

The AgentCore CLI requires the following AWS permissions:

- **Bedrock AgentCore**: For runtime management
- **ECR**: For repository and image management
- **IAM**: For role creation and management
- **CloudFormation**: For stack management
- **Cognito**: For user pool management
- **Parameter Store**: For configuration sync
- **CloudWatch Logs**: For monitoring

Here's a sample IAM policy with the minimum required permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:*",
        "bedrock-agentcore-control:*",
        "ecr:*",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "iam:PassRole",
        "iam:GetRole",
        "iam:DeleteRole",
        "iam:DetachRolePolicy",
        "cloudformation:*",
        "cognito-idp:*",
        "cognito-identity:*",
        "ssm:GetParameter",
        "ssm:PutParameter",
        "ssm:DeleteParameter",
        "ssm:DescribeParameters",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

!!! warning
    This is a sample policy with broad permissions. In production, you should follow the principle of least privilege and restrict permissions to only what's necessary.

## Next Steps

Once you've installed the AgentCore CLI, you're ready to:

1. Run the [initialization wizard](quick-start.md#initialization) to set up your project
2. [Deploy your first agent](first-agent.md)

If you encounter any issues during installation, see our [troubleshooting guide](/troubleshooting/common-issues.md).
