# Container Commands

!!! note "Work in Progress"
    This page is currently under development.

## Overview

The `container` command group contains all commands related to Docker container operations, including building, pushing to ECR, and managing container images.

## Commands

### container build

Build a Docker container image.

```bash
agentcore-cli container build <name> [--dockerfile PATH] [--context PATH] [--build-args KEY=VALUE]
```

### container push

Push a container image to Amazon ECR.

```bash
agentcore-cli container push <name> [--tag TAG] [--region REGION] [--create-repo]
```

### container list

List container images in a repository.

```bash
agentcore-cli container list [--repository REPO] [--region REGION]
```

### container pull

Pull a container image from Amazon ECR.

```bash
agentcore-cli container pull <name> [--tag TAG] [--region REGION]
```

### container remove

Remove container images locally and/or from ECR.

```bash
agentcore-cli container remove <name> [--tag TAG] [--local-only] [--force]
```

## Detailed Documentation

Complete documentation for each command will be added in a future update.
