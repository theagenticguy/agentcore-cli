# Deploy Your First Agent

!!! note "Work in Progress"
    This page is currently under development.

## Overview

This guide walks you through the process of deploying your first agent using AgentCore CLI. You'll learn how to create a simple agent, configure it, and deploy it to Amazon Bedrock AgentCore Runtime.

## Prerequisites

Before starting, ensure you have:

- Completed the [installation](installation.md) steps
- Initialized your project using `agentcore-cli init`
- Docker installed and running

## Step 1: Create a Simple Agent

Let's start by creating a basic agent that responds to prompts. Create the following files:

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

### app.py

```python
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

def handle_request(event, context):
    """Handle incoming requests to the agent."""
    # Parse the event
    body = json.loads(event.get('body', '{}'))
    prompt = body.get('prompt', 'Hello!')

    # Process the prompt (customize this for your agent)
    response = f"You said: {prompt}\nThis is my first AgentCore agent!"

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({
            "response": response
        })
    }

class AgentHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        event = json.loads(post_data.decode('utf-8'))

        # Call the handler
        result = handle_request(event, {})

        # Send response
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode('utf-8'))

if __name__ == "__main__":
    # Start server
    port = int(os.environ.get('PORT', 8080))
    httpd = HTTPServer(('0.0.0.0', port), AgentHandler)
    print(f"Starting agent on port {port}...")
    httpd.serve_forever()
```

### requirements.txt

```text
# No external dependencies for this simple example
```

## Step 2: Deploy the Agent

Now that you have created the agent files, deploy it using AgentCore CLI:

```bash
agentcore-cli agent create first-agent --dockerfile ./Dockerfile
```

This command will:

1. Build your Docker image
2. Create an ECR repository if it doesn't exist
3. Push the image to ECR
4. Create an IAM role with necessary permissions
5. Deploy the agent runtime on Bedrock AgentCore

## Step 3: Test the Agent

Test your deployed agent by invoking it:

```bash
agentcore-cli agent invoke first-agent --prompt "Hello, AgentCore!"
```

You should see a response similar to:

```
🤖 Agent Response:
You said: Hello, AgentCore!
This is my first AgentCore agent!
```

## Step 4: Check Agent Status

Check the status of your agent:

```bash
agentcore-cli agent status first-agent
```

This will show you:

- The agent's current version
- Available endpoints
- Deployment status
- Resource usage

## Next Steps

Now that you've deployed your first agent, you can:

- [Customize your agent with more advanced functionality](../tutorials/agent-customization.md)
- [Learn about agent lifecycle management](../user-guide/agents.md)
- [Set up multiple environments](../user-guide/environments.md)
- [Implement more sophisticated agents](../examples/langchain-agent.md)

## Troubleshooting

If you encounter issues:

- Ensure Docker is running and properly configured
- Verify your AWS credentials are valid
- Check that you have the necessary permissions
- See the [troubleshooting guide](../troubleshooting/common-issues.md) for more help
