# Configuration Commands

!!! note "Work in Progress"
    This page is currently under development.

## Overview

The `config` command group contains all commands related to managing AgentCore CLI configuration, including viewing, exporting, importing, and synchronizing configuration with AWS Parameter Store.

## Commands

### config show

Show the current configuration.

```bash
agentcore-cli config show [--environment ENV]
```

### config validate

Validate configuration integrity.

```bash
agentcore-cli config validate
```

### config export

Export configuration to a file.

```bash
agentcore-cli config export [--file PATH]
```

### config import

Import configuration from a file.

```bash
agentcore-cli config import <file> [--force]
```

### config set-default-agent

Set the default agent for an environment.

```bash
agentcore-cli config set-default-agent <name> [--environment ENV]
```

### config sync

Manage configuration synchronization with AWS Parameter Store.

```bash
agentcore-cli config sync [enable|disable|status|push|pull]
```

## Detailed Documentation

Complete documentation for each command will be added in a future update.
