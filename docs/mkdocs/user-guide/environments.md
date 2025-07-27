# Environment Management

!!! note "Work in Progress"
    This page is currently under development.

## Overview

Environment management is a core feature of AgentCore CLI that allows you to create, manage, and switch between isolated environments such as development, staging, and production.

## Environment Concepts

- **Environment**: A logical grouping of AWS resources and configurations
- **Environment Isolation**: Complete separation of resources between environments
- **Regional Deployment**: Each environment can be deployed to a different AWS region
- **Environment Variables**: Environment-specific configuration values
- **Default Agent**: Each environment can have a default agent runtime

## Creating Environments

Create new environments using the `env create` command:

```bash
agentcore-cli env create prod --region us-east-1 --set-current
```

## Switching Between Environments

Switch the active environment with the `env use` command:

```bash
agentcore-cli env use dev
```

## Environment Variables

Manage environment-specific variables:

```bash
# Set environment variables
agentcore-cli env vars --set DEBUG=true --set API_URL=https://api.dev.example.com

# List environment variables
agentcore-cli env vars --list
```

## Environment-Specific Resources

When creating resources, you can specify the target environment:

```bash
# Create agent in a specific environment
agentcore-cli agent create my-bot --environment prod

# List resources in a specific environment
agentcore-cli resources iam list --environment staging
```

## Environment Deletion

Delete environments that are no longer needed:

```bash
agentcore-cli env delete old-env --force
```

## Best Practices

Guidelines for working with environments will be added in a future update.

## Detailed Documentation

Complete documentation will be added in a future update.
