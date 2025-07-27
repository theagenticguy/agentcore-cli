# Initialization Command

!!! note "Work in Progress"
    This page is currently under development.

## Overview

The `init` command sets up your AgentCore CLI project with the necessary configuration and initial environment. It creates the configuration file and optionally sets up AWS resources.

## Usage

```bash
agentcore-cli init [options]
```

## Options

<div class="option-table" markdown>
| Option | Description |
| ------ | ----------- |
| `--no-interactive` | Run in non-interactive mode |
| `--region REGION` | AWS region to use (default: `us-west-2`) |
| `--environment ENV` | Initial environment name (default: `dev`) |
| `--config-file PATH` | Custom config file path |
| `--skip-aws-check` | Skip AWS credential validation |
| `--force` | Overwrite existing configuration |
</div>

## Interactive Mode

By default, the `init` command runs in interactive mode, guiding you through the setup process with a series of prompts:

1. AWS region selection
2. Environment name
3. AWS credential validation
4. Configuration file creation

## Non-Interactive Mode

You can also run the command in non-interactive mode, which is useful for automated scripts:

```bash
agentcore-cli init --no-interactive --region us-west-2 --environment dev
```

## Configuration File

The `init` command creates a configuration file at `.agentcore/config.json` (or a custom path if specified). This file contains:

- Current environment
- Environment configurations
- AWS resources
- Sync settings

## Detailed Documentation

Complete documentation will be added in a future update.
