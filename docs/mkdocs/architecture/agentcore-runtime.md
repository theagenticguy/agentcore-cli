# AgentCore Runtime

!!! note "Work in Progress"
    This page is currently under development.

## Overview

Amazon Bedrock AgentCore Runtime is a managed service that enables running containerized AI agents with extended execution times, enhanced payloads, and isolated environments.

## Key Features

### Extended Execution

- **Long-Running Sessions**: Up to 8 hours of execution time
- **Complex Reasoning**: Support for multi-step, sophisticated reasoning chains
- **Multi-Agent Collaboration**: Communication between agent instances
- **Stateful Processing**: Maintain context across multiple invocations

### Enhanced Payloads

- **Large Content Support**: Up to 100MB payload size
- **Multi-Modal Input**: Support for text, images, audio, and video
- **Structured Data**: JSON, XML, and binary data handling
- **File Processing**: Document analysis and processing capabilities

### Session Isolation

- **Dedicated microVMs**: Isolated execution environment for each agent
- **Resource Allocation**: Configurable CPU and memory resources
- **Filesystem Isolation**: Separate disk storage per session
- **Network Controls**: Configurable network access policies

## Framework Compatibility

AgentCore Runtime works with popular agent frameworks:

- **LangGraph**: Directed graphs for complex reasoning flows
- **CrewAI**: Multi-agent collaborative frameworks
- **Strands Agents**: Structured reasoning agents
- **Custom Implementations**: Any containerized agent system

## Built-in Services

- **Authentication**: Integration with identity providers
- **Observability**: Tracing, logging, and metrics
- **Tool Access**: Browser automation, code interpretation
- **Memory Management**: Short and long-term memory systems

## Deployment Model

Details on how AgentCore CLI deploys agents to Amazon Bedrock AgentCore Runtime will be added in a future update.

## Best Practices

Recommended patterns for designing and implementing agents for AgentCore Runtime will be covered in a future update.
