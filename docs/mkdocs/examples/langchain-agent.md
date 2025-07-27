# LangChain Agent Example

!!! note "Work in Progress"
    This page is currently under development.

## Overview

This example demonstrates how to deploy a LangChain agent using AgentCore CLI. LangChain is a popular framework for building applications with large language models (LLMs).

## Prerequisites

Before starting this example, ensure you have:

- Completed the [installation](../getting-started/installation.md) steps
- Initialized your project using `agentcore-cli init`
- Basic understanding of LangChain

## Project Structure

Create the following files:

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY app.py .

# Run the agent
CMD ["python", "app.py"]
```

### requirements.txt

```text
langchain>=0.0.267
langchain-community>=0.0.10
langchain-core>=0.1.4
boto3>=1.28.0
fastapi>=0.104.1
uvicorn>=0.24.0
pydantic>=2.4.2
```

### app.py

```python
# Example LangChain agent code will be added in a future update
```

## Step 1: Build and Deploy

Deploy your LangChain agent:

```bash
agentcore-cli agent create langchain-agent --dockerfile ./Dockerfile
```

## Step 2: Invoke the Agent

Invoke your deployed agent:

```bash
agentcore-cli agent invoke langchain-agent --prompt "What is the capital of France?"
```

## LangChain Agent Features

The LangChain agent in this example includes:

- **Chain of Thought Reasoning**: Solving problems step-by-step
- **Tool Usage**: Accessing external tools when needed
- **Memory**: Maintaining conversation context
- **Structured Output**: Returning consistent response formats

## Advanced Configuration

Advanced LangChain configuration options will be added in a future update.

## Best Practices

Guidelines for deploying LangChain agents will be added in a future update.

## Additional Resources

- [LangChain Documentation](https://python.langchain.com/docs/get_started/introduction)
- [Agent Customization Tutorial](../tutorials/agent-customization.md)
