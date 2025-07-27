# Resources Commands

!!! note "Work in Progress"
    This page is currently under development.

## Overview

The `resources` command group contains all commands related to managing AWS resources, including ECR repositories, IAM roles, and Cognito user pools.

## Commands

### resources ecr

Manage ECR repositories.

```bash
# Create a repository
agentcore-cli resources ecr create <name> [--image-scanning] [--region REGION]

# List repositories
agentcore-cli resources ecr list [--region REGION] [--environment ENV]

# Delete a repository
agentcore-cli resources ecr delete <name> [--region REGION] [--force]
```

### resources iam

Manage IAM roles.

```bash
# Create a role
agentcore-cli resources iam create <agent-name> [--region REGION] [--role-prefix PREFIX] [--environment ENV]

# List roles
agentcore-cli resources iam list [--environment ENV]

# Delete a role
agentcore-cli resources iam delete <agent-name> [--environment ENV] [--force]
```

### resources cognito

Manage Cognito resources.

```bash
# Create Cognito resources
agentcore-cli resources cognito create <agent-name> [--allow-signup] [--environment ENV]

# List Cognito resources
agentcore-cli resources cognito list [--environment ENV]
```

## Detailed Documentation

Complete documentation for each command will be added in a future update.
