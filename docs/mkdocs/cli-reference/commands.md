# CLI Commands Reference

This document provides a comprehensive reference for all AgentCore CLI commands, their options, and usage examples.

## Command Structure

AgentCore CLI follows a consistent command structure:

```bash
agentcore-cli [global-options] <command-group> <command> [options] [arguments]
```

- **Global Options**: Apply to all commands (e.g., `--verbose`, `--config`)
- **Command Group**: Logical grouping of related commands (e.g., `agent`, `env`)
- **Command**: Specific action to perform (e.g., `create`, `list`)
- **Options**: Command-specific flags and settings (e.g., `--dockerfile`, `--region`)
- **Arguments**: Required inputs for the command (e.g., agent name)

## Global Options

<div class="option-table" markdown>
| Option | Description |
| ------ | ----------- |
| `--version` | Show version and exit |
| `--config PATH` | Path to config file (default: `.agentcore/config.json`) |
| `--verbose`, `-v` | Enable verbose logging |
| `--quiet`, `-q` | Suppress non-error output |
| `--help`, `-h` | Show help message and exit |
</div>

## Command Groups

AgentCore CLI organizes commands into logical groups:

<div class="grid cards" markdown>

- <i data-feather="zap" style="color: var(--md-primary-fg-color);"></i> [**init**](init.md)

    Initialize and set up your AgentCore project.

- <i data-feather="package" style="color: var(--md-primary-fg-color);"></i> [**agent**](agent.md)

    Create, update, invoke, and manage agent runtimes.

- <i data-feather="layers" style="color: var(--md-primary-fg-color);"></i> [**env**](env.md)

    Manage environments (dev, staging, prod).

- <i data-feather="box" style="color: var(--md-primary-fg-color);"></i> [**container**](container.md)

    Build, push, and manage Docker containers.

- <i data-feather="settings" style="color: var(--md-primary-fg-color);"></i> [**config**](config.md)

    Configure and synchronize your AgentCore setup.

- <i data-feather="server" style="color: var(--md-primary-fg-color);"></i> [**resources**](resources.md)

    Manage AWS resources (ECR, IAM, Cognito).

</div>

## Quick Command Reference

Below is a quick reference for commonly used commands:

### Initialization

```bash
# Interactive setup wizard
agentcore-cli init

# Non-interactive setup
agentcore-cli init --no-interactive --region us-west-2 --environment dev
```

### Agent Management

```bash
# Create a new agent
agentcore-cli agent create my-bot --dockerfile ./Dockerfile

# Update an existing agent
agentcore-cli agent update my-bot --image-tag v2

# Invoke an agent
agentcore-cli agent invoke my-bot --prompt "Hello!"

# List all agents in current environment
agentcore-cli agent list

# Show agent status
agentcore-cli agent status my-bot

# Delete an agent
agentcore-cli agent delete my-bot
```

### Environment Management

```bash
# Create environment
agentcore-cli env create prod --region us-east-1

# Switch to environment
agentcore-cli env use prod

# List environments
agentcore-cli env list

# Show current environment
agentcore-cli env current

# Delete environment
agentcore-cli env delete old-env --force
```

### Container Operations

```bash
# Build container
agentcore-cli container build my-bot --dockerfile ./Dockerfile

# Push to ECR
agentcore-cli container push my-bot --tag v1.0.0

# List images
agentcore-cli container list --repository my-bot

# Pull image
agentcore-cli container pull my-bot --tag v1.0.0

# Remove container image
agentcore-cli container remove my-bot --local-only
```

### Configuration Management

```bash
# Show current configuration
agentcore-cli config show

# Export configuration
agentcore-cli config export --file backup.json

# Import configuration
agentcore-cli config import backup.json

# Enable cloud sync
agentcore-cli config sync enable --auto

# Check sync status
agentcore-cli config sync status
```

### Resource Management

```bash
# ECR Resources
agentcore-cli resources ecr create my-repo
agentcore-cli resources ecr list
agentcore-cli resources ecr delete old-repo --force

# IAM Resources
agentcore-cli resources iam create my-agent
agentcore-cli resources iam list

# Cognito Resources
agentcore-cli resources cognito create my-agent
agentcore-cli resources cognito list
```

## Getting Help

For detailed help on any command, use the `--help` flag:

```bash
# General help
agentcore-cli --help

# Command group help
agentcore-cli agent --help

# Specific command help
agentcore-cli agent create --help
```

## Next Steps

For detailed information about specific command groups, visit their individual pages:

- [init Command](init.md)
- [agent Commands](agent.md)
- [env Commands](env.md)
- [container Commands](container.md)
- [config Commands](config.md)
- [resources Commands](resources.md)
