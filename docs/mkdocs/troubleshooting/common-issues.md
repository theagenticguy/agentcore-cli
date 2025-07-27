# Common Issues and Solutions

!!! note "Work in Progress"
    This page is currently under development.

## Overview

This guide addresses common issues you might encounter when using AgentCore CLI and provides solutions to help you resolve them quickly.

## AWS Credentials

### Issue: Invalid AWS Credentials

**Symptoms:**
- Error message: "❌ AWS credentials not found or invalid"
- Commands fail with authentication errors

**Solutions:**

1. Verify your credentials are set up:
   ```bash
   aws sts get-caller-identity
   ```

2. Configure AWS CLI:
   ```bash
   aws configure
   ```

3. Set environment variables:
   ```bash
   export AWS_ACCESS_KEY_ID=your_access_key_id
   export AWS_SECRET_ACCESS_KEY=your_secret_access_key
   export AWS_DEFAULT_REGION=us-west-2
   ```

### Issue: Insufficient Permissions

**Symptoms:**
- Error message: "AccessDenied" or "User is not authorized"
- Operations fail despite valid credentials

**Solutions:**

1. Review the [required AWS permissions](../getting-started/installation.md#required-aws-permissions)
2. Ensure your IAM user or role has the necessary permissions
3. Use the `--verbose` flag to see detailed error messages

## Docker Issues

### Issue: Docker Not Running

**Symptoms:**
- Error message: "Cannot connect to the Docker daemon"
- Container operations fail

**Solutions:**

1. Start Docker service:
   ```bash
   # Linux
   sudo systemctl start docker

   # macOS/Windows
   # Start Docker Desktop application
   ```

2. Verify Docker is running:
   ```bash
   docker ps
   ```

### Issue: Docker Build Errors

**Symptoms:**
- Error during container build process
- Build fails with specific error messages

**Solutions:**

1. Check your Dockerfile syntax
2. Ensure all referenced files exist
3. Try building manually to see detailed errors:
   ```bash
   docker build -t test-image -f Dockerfile .
   ```

## Configuration Issues

### Issue: Configuration File Not Found

**Symptoms:**
- Error message: "Configuration file not found"
- Commands fail with configuration-related errors

**Solutions:**

1. Run initialization:
   ```bash
   agentcore-cli init
   ```

2. Specify custom config path:
   ```bash
   agentcore-cli --config /path/to/config.json <command>
   ```

### Issue: Configuration Drift

**Symptoms:**
- Error message: "Configuration drift detected"
- Local and cloud configurations are out of sync

**Solutions:**

1. Check sync status:
   ```bash
   agentcore-cli config sync status
   ```

2. Push local changes to cloud:
   ```bash
   agentcore-cli config sync push
   ```

3. Pull cloud changes to local:
   ```bash
   agentcore-cli config sync pull
   ```

## Deployment Issues

### Issue: Agent Deployment Fails

**Symptoms:**
- Error during agent creation or update
- Agent status shows error state

**Solutions:**

1. Check AWS service quotas
2. Verify IAM permissions
3. Check CloudFormation stack events:
   ```bash
   aws cloudformation describe-stack-events --stack-name <stack-name>
   ```

### Issue: Agent Invocation Fails

**Symptoms:**
- Error when invoking an agent
- Timeouts or connection errors

**Solutions:**

1. Check agent status:
   ```bash
   agentcore-cli agent status <agent-name>
   ```

2. Verify agent is deployed correctly
3. Check agent logs in CloudWatch

## General Troubleshooting

### Using Verbose Mode

For detailed error information, use the verbose flag:

```bash
agentcore-cli --verbose <command>
```

### Checking Logs

View logs in CloudWatch for runtime issues:

```bash
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/agentcore
```

### Getting Help

If you continue to encounter issues:

1. Check the [GitHub repository](https://github.com/theagenticguy/agentcore-cli/issues) for known issues
2. Submit a detailed bug report including:
   - Command being run
   - Error message
   - Environment information
   - Steps to reproduce
