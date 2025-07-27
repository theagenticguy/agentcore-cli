# Environment Commands

!!! note "Work in Progress"
    This page is currently under development.

## Overview

The `env` command group contains all commands related to managing environments, including creation, switching between environments, and environment-specific configuration.

## Commands

### env list

List all environments.

```bash
agentcore-cli env list [--verbose]
```

### env current

Show the current active environment.

```bash
agentcore-cli env current
```

### env create

Create a new environment.

```bash
agentcore-cli env create <name> --region <region> [--set-current]
```

### env use

Switch to a different environment.

```bash
agentcore-cli env use <name>
```

### env delete

Delete an environment.

```bash
agentcore-cli env delete <name> [--force] [--keep-resources]
```

### env vars

Manage environment variables.

```bash
agentcore-cli env vars [--list] [--set KEY=VALUE]
```

## Detailed Documentation

Complete documentation for each command will be added in a future update.
