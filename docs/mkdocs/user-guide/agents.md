# Agent Lifecycle Management

!!! note "Work in Progress"
    This page is currently under development.

## Overview

Agent lifecycle management is a fundamental aspect of AgentCore CLI that covers the creation, versioning, deployment, invocation, and deletion of agent runtimes.

## Agent Concepts

- **Agent Runtime**: A containerized AI application deployed on Amazon Bedrock AgentCore Runtime
- **Versions**: Immutable snapshots of an agent at a specific point in time
- **Endpoints**: Named pointers to specific versions (e.g., DEFAULT, production, staging)
- **Invocation**: Sending requests to an agent through an endpoint
- **Lifecycle**: The complete process from creation to deletion

## Agent Creation

Create a new agent using the `agent create` command:

```bash
agentcore-cli agent create my-bot --dockerfile ./Dockerfile
```

## Agent Versioning

AgentCore CLI uses an immutable versioning system where every update creates a new version:

```bash
# Update an agent, creating a new version
agentcore-cli agent update my-bot --image-tag v2.0.0
```

## Endpoint Management

Endpoints can point to any version, enabling safe rollbacks and blue-green deployments:

```bash
# Update a specific endpoint to point to a version
agentcore-cli agent update my-bot --endpoint production --image-tag stable-v1
```

## Agent Invocation

Invoke an agent with a prompt or payload:

```bash
# Invoke with a text prompt
agentcore-cli agent invoke my-bot --prompt "Hello, agent!"

# Invoke with a custom payload
agentcore-cli agent invoke my-bot --payload '{"query": "Hello", "max_tokens": 100}'
```

## Agent Status and Listing

View the status of agents and list deployed agents:

```bash
# Show status of a specific agent
agentcore-cli agent status my-bot

# List all agents
agentcore-cli agent list
```

## Agent Deletion

Delete agents that are no longer needed:

```bash
agentcore-cli agent delete my-bot --force
```

## Best Practices

Guidelines for agent lifecycle management will be added in a future update.

## Detailed Documentation

Complete documentation will be added in a future update.
