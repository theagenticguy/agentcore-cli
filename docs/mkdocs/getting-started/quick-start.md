# Quick Start Guide

This guide will get you up and running with AgentCore CLI in just a few minutes. Follow these steps to set up your environment and deploy your first agent.

## Prerequisites

Before starting, ensure you have:

- [Installed AgentCore CLI](installation.md)
- AWS credentials configured
- Docker installed and running

## Step 1: Initialize Your Project

Start by initializing your AgentCore CLI project:

=== "Interactive Setup (Recommended)"

    Run the initialization wizard with:

    ```bash
    agentcore-cli init
    ```

    The interactive wizard will guide you through:

    - AWS region selection
    - Environment setup
    - Confirmation of required AWS resources

=== "Non-Interactive Setup"

    For automated or script-based setup:

    ```bash
    agentcore-cli init --no-interactive \
      --region us-west-2 \
      --environment dev
    ```

Once initialization is complete, you'll have:

- A default environment (`dev`) configured
- AWS region set
- Basic configuration file created at `.agentcore/config.json`

## Step 2: Deploy Your First Agent

Now let's deploy a simple agent. Create a minimal Dockerfile or use our example:

```dockerfile title="Dockerfile"
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

Create a simple Python agent:

```python title="app.py"
import os
import json

def handle_request(event, context):
    # Parse the event
    body = json.loads(event.get('body', '{}'))
    prompt = body.get('prompt', 'Hello!')

    # Simple echo agent
    response = f"You said: {prompt}"

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({
            "response": response
        })
    }

if __name__ == "__main__":
    # AWS Bedrock AgentCore Runtime will invoke handle_request
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

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

    # Start server
    port = int(os.environ.get('PORT', 8080))
    httpd = HTTPServer(('0.0.0.0', port), AgentHandler)
    print(f"Starting server on port {port}...")
    httpd.serve_forever()
```

And a requirements file:

```text title="requirements.txt"
# No external dependencies for this simple example
```

Now deploy your agent:

```bash
agentcore-cli agent create echo-agent --dockerfile ./Dockerfile
```

This single command will:

1. Build your Docker image
2. Create an ECR repository if it doesn't exist
3. Push the image to ECR
4. Create an IAM role with necessary permissions
5. Deploy the agent runtime on Bedrock AgentCore
6. Configure a default endpoint

## Step 3: Test Your Agent

Test your deployed agent with:

```bash
agentcore-cli agent invoke echo-agent --prompt "Hello from AgentCore!"
```

You should see a response similar to:

```
🤖 Agent Response:
You said: Hello from AgentCore!
```

## Step 4: Check Agent Status

View the status of your deployed agent:

```bash
agentcore-cli agent status echo-agent
```

This will show:
- Current runtime version
- Available endpoints
- Deployment status
- Container image details

## Next Steps

You've successfully deployed your first agent! Here's what to explore next:

- [Deploy your first agent](first-agent.md) - A more detailed tutorial
- [Environment management](../user-guide/environments.md) - Learn about dev/staging/prod separation
- [Agent lifecycle](../user-guide/agents.md) - Creating, updating, and managing agents
- [Container operations](../user-guide/containers.md) - Docker and ECR management

## Common Issues

If you encounter any problems:

- Ensure Docker is running (`docker ps`)
- Verify AWS credentials are valid (`aws sts get-caller-identity`)
- Check that you have required permissions for Bedrock AgentCore and ECR
- See our [troubleshooting guide](../troubleshooting/common-issues.md) for more help
