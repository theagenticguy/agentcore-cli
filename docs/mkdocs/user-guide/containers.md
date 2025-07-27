# Container Operations

!!! note "Work in Progress"
    This page is currently under development.

## Overview

Container operations in AgentCore CLI allow you to build, push, pull, and manage Docker containers that run your AI agents.

## Container Concepts

- **Docker Integration**: Built-in support for Docker operations
- **ECR Integration**: Automatic Amazon ECR repository management
- **Image Tags**: Versioning system for container images
- **Build Arguments**: Custom variables passed during Docker build
- **Container Registry**: Central storage for container images

## Building Containers

Build a container image from a Dockerfile:

```bash
agentcore-cli container build my-bot \
  --dockerfile ./Dockerfile \
  --context ./src \
  --build-args API_KEY=secret123
```

## Pushing to ECR

Push a container image to Amazon ECR:

```bash
agentcore-cli container push my-bot \
  --tag v1.0.0 \
  --region us-west-2 \
  --create-repo
```

## Listing Images

List container images in a repository:

```bash
agentcore-cli container list --repository my-bot
```

## Pulling Images

Pull a container image from ECR:

```bash
agentcore-cli container pull my-bot --tag v1.0.0
```

## Removing Images

Remove container images locally and/or from ECR:

```bash
agentcore-cli container remove my-bot --tag v1.0.0 --local-only
```

## Container Architecture

AgentCore CLI uses a container architecture that:

- Provides consistent execution environments
- Enables easy deployment and scaling
- Supports any AI framework or library
- Integrates with AWS Bedrock AgentCore Runtime

## Best Practices

Guidelines for container operations will be added in a future update.

## Detailed Documentation

Complete documentation will be added in a future update.
