"""Configuration models for AgentCore Platform CLI.

This module defines the configuration models used to manage environments and settings.

Model Hierarchy Alignment with AWS Bedrock AgentCore:

1. Environment-First Design:
   - Each environment owns its agent runtimes and exists in a specific AWS region
   - Aligns with AWS reality where runtimes are region-specific resources
   - No cross-region runtime sharing (follows AWS patterns)

2. ECR Integration:
   - Global ECR repositories can be shared across environments
   - Each AgentRuntimeVersion references a specific ECR repository + image tag
   - Full container URIs are constructed dynamically from repository + tag

3. Versioning Model:
   - AgentRuntimes contain immutable versions (V1, V2, etc.)
   - Each update creates a new version with complete configuration
   - DEFAULT endpoint automatically points to latest version (AWS behavior)

4. Validation:
   - Cross-reference validation ensures ECR repository references exist
   - Region consistency validation for runtime placement
   - Environment isolation with proper resource ownership

This design eliminates the complexity of global runtimes with environment mappings
and creates a clean, maintainable structure that scales across multiple environments.
"""

from .base import BaseAgentCoreModel
from .resources import CognitoConfig
from datetime import datetime
from pydantic import ConfigDict, Field, model_validator


class SyncConfig(BaseAgentCoreModel):
    """Configuration for cloud sync behavior."""

    cloud_config_enabled: bool = Field(default=False, description="Whether cloud config is enabled")
    auto_sync_enabled: bool = Field(default=True, description="Whether auto-sync is enabled")
    parameter_store_prefix: str = Field(default="/agentcore", description="Parameter Store prefix")
    last_full_sync: datetime | None = Field(default=None, description="Last full sync timestamp")
    sync_interval_minutes: int = Field(default=60, description="Sync interval in minutes when auto-sync is enabled")


class EnvironmentConfig(BaseAgentCoreModel):
    """Configuration for a specific environment (dev, staging, prod).

    Each environment owns its agent runtimes and exists in a specific AWS region.
    This design aligns with AWS AgentCore where runtimes are region-specific resources.
    """

    name: str = Field(description="Environment name (e.g., 'dev', 'staging', 'prod')")
    region: str = Field(description="AWS region for this environment and all its agent runtimes")

    # Agent runtimes owned by this environment
    agent_runtimes: dict[str, "AgentRuntime"] = Field(
        default_factory=dict, description="Agent runtimes deployed in this environment, keyed by runtime name"
    )

    # Default agent for this environment
    default_agent_runtime: str | None = Field(
        default=None, description="Default agent runtime name to use for operations (must exist in agent_runtimes)"
    )

    # Environment-specific settings
    environment_variables: dict[str, str] = Field(
        default_factory=dict, description="Default environment variables for all runtimes in this environment"
    )

    # Auth configuration for this environment
    cognito: CognitoConfig | None = Field(default=None, description="Cognito configuration for this environment")

    # Metadata
    created_at: datetime | None = Field(default=None, description="When this environment was created")
    updated_at: datetime | None = Field(default=None, description="When this environment was last updated")

    @model_validator(mode="after")
    def set_creation_time(cls, model):
        """Set creation time if not set."""
        if model.created_at is None:
            model.created_at = datetime.now()
        return model

    @model_validator(mode="after")
    def validate_default_agent(cls, model):
        """Validate that default_agent_runtime exists in agent_runtimes."""
        if model.default_agent_runtime:
            if model.default_agent_runtime not in model.agent_runtimes:
                available_runtimes = list(model.agent_runtimes.keys())
                raise ValueError(
                    f"default_agent_runtime '{model.default_agent_runtime}' does not exist in agent_runtimes. "
                    f"Available runtimes: {available_runtimes}"
                )
        return model

    @model_validator(mode="after")
    def validate_runtime_regions(cls, model):
        """Ensure all agent runtimes in this environment match the environment's region."""
        for runtime_name, runtime in model.agent_runtimes.items():
            if hasattr(runtime, "region") and runtime.region != model.region:
                raise ValueError(
                    f"Agent runtime '{runtime_name}' is in region '{runtime.region}' "
                    f"but environment '{model.name}' is in region '{model.region}'. "
                    f"All runtimes in an environment must be in the same region."
                )
        return model

    def get_agent_endpoint(self, agent_runtime_name: str, endpoint_name: str | None = None) -> tuple[str, str] | None:
        """Get the agent runtime and endpoint for invocation.

        Args:
            agent_runtime_name: Name of the agent runtime
            endpoint_name: Specific endpoint name, or None to use DEFAULT

        Returns:
            Tuple of (runtime_name, endpoint_name) or None if not found
        """
        if agent_runtime_name not in self.agent_runtimes:
            return None

        runtime = self.agent_runtimes[agent_runtime_name]
        target_endpoint = endpoint_name or "DEFAULT"

        if target_endpoint not in runtime.endpoints:
            return None

        return (agent_runtime_name, target_endpoint)


class GlobalResourceConfig(BaseAgentCoreModel):
    """Global resources shared across environments."""

    # ECR repositories (can be shared across environments)
    ecr_repositories: dict[str, "ECRRepository"] = Field(default_factory=dict, description="ECR repositories by name")

    # IAM roles (can be shared across environments)
    iam_roles: dict[str, "IAMRoleConfig"] = Field(default_factory=dict, description="IAM roles by name")

    # Sync configuration
    sync_config: SyncConfig = Field(default_factory=SyncConfig, description="Sync configuration")


class AgentCoreConfig(BaseAgentCoreModel):
    """Root configuration for AgentCore CLI.

    This configuration uses an environment-first approach where each environment
    owns its agent runtimes. This design aligns with AWS AgentCore where:
    - Runtimes exist in specific regions
    - Environments represent deployment targets (dev/staging/prod)
    - Each environment can have different versions and endpoints
    """

    # Environment management
    current_environment: str = Field(default="dev", description="Currently active environment")
    environments: dict[str, EnvironmentConfig] = Field(
        default_factory=dict, description="Environment configurations by name"
    )

    # Global resources (shared across environments)
    global_resources: GlobalResourceConfig = Field(
        default_factory=GlobalResourceConfig, description="Resources shared across environments"
    )

    # File path for configuration
    config_path: str | None = Field(default=None, description="Path to the configuration file")

    model_config = ConfigDict(extra="allow", json_encoders={datetime: lambda v: v.isoformat() if v else None})

    @model_validator(mode="after")
    def ensure_current_environment_exists(cls, model):
        """Ensure the current environment exists."""
        if model.current_environment not in model.environments:
            # Create default environment
            model.environments[model.current_environment] = EnvironmentConfig(
                name=model.current_environment,
                region="us-east-1",  # Default region
                created_at=datetime.now(),
            )
        return model

    @model_validator(mode="after")
    def validate_ecr_repository_references(cls, model):
        """Validate that all ECR repository references exist in global_resources.ecr_repositories."""
        available_repos = set(model.global_resources.ecr_repositories.keys())

        for env_name, env_config in model.environments.items():
            for runtime_name, runtime in env_config.agent_runtimes.items():
                # Validate primary ECR repository
                if runtime.primary_ecr_repository not in available_repos:
                    raise ValueError(
                        f"Runtime '{runtime_name}' in environment '{env_name}' references "
                        f"ECR repository '{runtime.primary_ecr_repository}' which does not exist "
                        f"in global_resources.ecr_repositories. Available repositories: {sorted(available_repos)}"
                    )

                # Validate ECR repository references in all versions
                for version_id, version in runtime.versions.items():
                    if version.ecr_repository_name not in available_repos:
                        raise ValueError(
                            f"Version '{version_id}' of runtime '{runtime_name}' in environment '{env_name}' "
                            f"references ECR repository '{version.ecr_repository_name}' which does not exist "
                            f"in global_resources.ecr_repositories. Available repositories: {sorted(available_repos)}"
                        )

        return model

    def get_current_env(self) -> EnvironmentConfig:
        """Get the currently active environment configuration."""
        return self.environments[self.current_environment]

    def get_agent_runtime(self, agent_name: str, environment: str | None = None) -> "AgentRuntime | None":
        """Get an agent runtime from the specified or current environment.

        Args:
            agent_name: Name of the agent runtime
            environment: Environment name, or None for current environment

        Returns:
            AgentRuntime instance or None if not found
        """
        env_name = environment or self.current_environment
        if env_name not in self.environments:
            return None

        env_config = self.environments[env_name]
        return env_config.agent_runtimes.get(agent_name)

    def list_all_agent_runtimes(self) -> dict[str, list[str]]:
        """List all agent runtimes across all environments.

        Returns:
            Dict mapping environment names to lists of agent runtime names
        """
        return {env_name: list(env_config.agent_runtimes.keys()) for env_name, env_config in self.environments.items()}

    def get_ecr_repository(self, repository_name: str) -> "ECRRepository | None":
        """Get an ECR repository by name.

        Args:
            repository_name: Name of the ECR repository

        Returns:
            ECRRepository instance or None if not found
        """
        return self.global_resources.ecr_repositories.get(repository_name)

    def get_runtime_version_container_uri(
        self, agent_name: str, version_id: str, environment: str | None = None
    ) -> str | None:
        """Get the full container URI for a specific runtime version.

        Args:
            agent_name: Name of the agent runtime
            version_id: Version identifier
            environment: Environment name, or None for current environment

        Returns:
            Full container URI or None if not found
        """
        runtime = self.get_agent_runtime(agent_name, environment)
        if not runtime or version_id not in runtime.versions:
            return None

        version = runtime.versions[version_id]
        ecr_repo = self.get_ecr_repository(version.ecr_repository_name)
        if not ecr_repo:
            return None

        return version.get_container_uri(ecr_repo)


# Forward references
from .runtime import AgentRuntime  # noqa
from .resources import ECRRepository, IAMRoleConfig  # noqa
