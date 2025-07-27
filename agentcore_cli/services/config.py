"""Configuration management for AgentCore Platform CLI.

This module provides a centralized configuration management system for the AgentCore
Platform CLI, including local file storage and cloud synchronization.
"""

import json
import os
from datetime import datetime
from typing import Any
from loguru import logger

from agentcore_cli.models.config import AgentCoreConfig, EnvironmentConfig, SyncConfig
from agentcore_cli.models.resources import CognitoConfig, ECRRepository, IAMRoleConfig
from agentcore_cli.models.runtime import AgentRuntime
from agentcore_cli.models.responses import CloudSyncResult, SyncStatus


class ConfigManager:
    """Centralized configuration manager for AgentCore Platform CLI.

    This class is responsible for loading, saving, and managing the configuration
    for the AgentCore Platform CLI. It provides a clean interface for accessing
    and modifying configuration settings.

    The configuration is stored in a local JSON file and can be synchronized with
    AWS Parameter Store when cloud sync is enabled.

    Attributes:
        config (AgentCoreConfig): The current configuration.
        config_dir (str): Directory where configuration is stored.
        config_file (str): Path to the configuration file.
    """

    def __init__(self) -> None:
        """Initialize the configuration manager."""
        self.config = AgentCoreConfig()
        self.config_dir = os.path.join(os.getcwd(), ".agentcore")
        self.config_file = os.path.join(self.config_dir, "config.json")
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from local file.

        If the file doesn't exist or can't be parsed, a default configuration
        is used.
        """
        try:
            # Create config directory if it doesn't exist
            os.makedirs(self.config_dir, exist_ok=True)

            # Check if config file exists
            if not os.path.exists(self.config_file):
                logger.debug(f"Configuration file not found at {self.config_file}")
                self._create_default_config()
                self.save_config()
                return

            # Load the config file
            with open(self.config_file, "r") as f:
                config_data = json.load(f)

            # Parse the config data
            self.config = AgentCoreConfig.model_validate(config_data)
            self.config.config_path = self.config_file

            logger.debug(f"Configuration loaded from {self.config_file}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse configuration file: {str(e)}")
            self._create_default_config()
            self.save_config()
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            self._create_default_config()

    def _create_default_config(self) -> None:
        """Create a default configuration."""
        # Create default environment
        default_env = EnvironmentConfig(name="dev", region="us-west-2")
        # Set creation timestamp manually since it's in the validator
        default_env.created_at = datetime.now()

        # Create default global resources
        from agentcore_cli.models.config import GlobalResourceConfig

        global_resources = GlobalResourceConfig()

        # Create default config with minimal parameters
        self.config = AgentCoreConfig()

        # Set properties after creation
        self.config.current_environment = "dev"
        self.config.environments = {"dev": default_env}
        self.config.global_resources = global_resources
        self.config.config_path = self.config_file

        logger.debug("Created default configuration")

    def save_config(self) -> bool:
        """Save current configuration to file."""
        try:
            # Ensure the config directory exists
            os.makedirs(self.config_dir, exist_ok=True)

            # Convert to dict and save
            config_dict = self.config.model_dump(mode="json")

            # Remove config_path to avoid circular references
            if "config_path" in config_dict:
                del config_dict["config_path"]

            with open(self.config_file, "w") as f:
                json.dump(config_dict, f, indent=2, default=str)

            logger.debug(f"Configuration saved to {self.config_file}")

            # Perform auto-sync if enabled
            if (
                self.config.global_resources.sync_config
                and self.config.global_resources.sync_config.cloud_config_enabled
            ):
                self.sync_with_cloud(auto=True)

            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")
            return False

    def sync_with_cloud(self, auto: bool = False) -> CloudSyncResult:
        """Sync configuration with AWS Parameter Store.

        Args:
            auto: Whether this is an automatic sync.

        Returns:
            CloudSyncResult: Result of the sync operation.
        """
        from agentcore_cli.services.config_sync import ConfigSyncService

        # Only sync if cloud sync is enabled
        if not self.config.global_resources.sync_config.cloud_config_enabled:
            return CloudSyncResult(
                success=False,
                message="Cloud sync is not enabled",
                environment=self.config.current_environment,
                synced_items={},
                errors=["Cloud sync is not enabled. Enable it first with 'config sync --enable'."],
            )

        # Only auto-sync if auto-sync is enabled
        if auto and (not self.config.global_resources.sync_config.auto_sync_enabled):
            return CloudSyncResult(
                success=True,
                message="Auto-sync is disabled",
                environment=self.config.current_environment,
                synced_items={},
                errors=[],
            )

        # Get current environment region
        region = self.get_region()

        # Create sync service
        sync_service = ConfigSyncService(region=region, config=self.config)

        # Check if we should auto-sync
        if auto and not sync_service.should_auto_sync:
            return CloudSyncResult(
                success=True,
                message="Automatic sync not needed",
                environment=self.config.current_environment,
                synced_items={},
                errors=[],
            )

        # Push config to cloud
        return sync_service.push_config_to_cloud(self.config)

    def pull_from_cloud(self) -> bool:
        """Pull configuration from AWS Parameter Store.

        Returns:
            bool: True if successful, False otherwise.
        """
        from agentcore_cli.services.config_sync import ConfigSyncService

        # Only sync if cloud sync is enabled
        if (
            not self.config.global_resources.sync_config
            or not self.config.global_resources.sync_config.cloud_config_enabled
        ):
            logger.error("Cloud sync is not enabled")
            return False

        # Get current environment region
        region = self.get_region()

        # Create sync service
        sync_service = ConfigSyncService(region=region, config=self.config)

        # Pull config from cloud
        success, config_dict, errors = sync_service.pull_config_from_cloud()

        if not success:
            logger.error(f"Failed to pull configuration from cloud: {errors}")
            return False

        try:
            # Update config with cloud data
            self.config = AgentCoreConfig.model_validate(config_dict)
            self.config.config_path = self.config_file

            # Save the updated config
            self.save_config()

            return True
        except Exception as e:
            logger.error(f"Failed to update configuration with cloud data: {str(e)}")
            return False

    def get_cloud_sync_status(self, environment: str | None = None) -> SyncStatus:
        """Get the sync status between local and cloud configuration.

        Args:
            environment: Optional environment to check. If None, checks current environment.

        Returns:
            SyncStatus: Sync status between local and cloud.
        """
        from agentcore_cli.services.config_sync import ConfigSyncService

        env = environment or self.config.current_environment
        region = self.get_environment(env).region

        sync_service = ConfigSyncService(region=region, config=self.config)
        return sync_service.check_sync_status(self.config, env)

    def enable_cloud_sync(self, enable: bool = True) -> bool:
        """Enable or disable cloud configuration sync.

        Args:
            enable: Whether to enable or disable cloud sync.

        Returns:
            bool: True if successful, False otherwise.
        """
        from agentcore_cli.services.config_sync import ConfigSyncService

        region = self.get_region()
        sync_service = ConfigSyncService(region=region, config=self.config)

        result = sync_service.enable_cloud_sync(self.config, enable)

        if result:
            self.save_config()

        return result

    def enable_auto_sync(self, enable: bool = True) -> bool:
        """Enable or disable automatic configuration sync.

        Args:
            enable: Whether to enable or disable auto-sync.

        Returns:
            bool: True if successful, False otherwise.
        """
        from agentcore_cli.services.config_sync import ConfigSyncService

        region = self.get_region()
        sync_service = ConfigSyncService(region=region, config=self.config)

        result = sync_service.enable_auto_sync(self.config, enable)

        if result:
            self.save_config()

        return result

    def set_sync_interval(self, minutes: int) -> bool:
        """Set the sync interval for auto-sync.

        Args:
            minutes: Sync interval in minutes.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            if not self.config.global_resources.sync_config:
                self.config.global_resources.sync_config = SyncConfig()

            self.config.global_resources.sync_config.sync_interval_minutes = minutes
            self.save_config()

            return True
        except Exception as e:
            logger.error(f"Failed to set sync interval: {str(e)}")
            return False

    def get_region(self, environment: str | None = None) -> str:
        """Get the AWS region for an environment.

        Args:
            environment: Optional environment name. If None, uses current environment.

        Returns:
            str: AWS region.
        """
        env_name = environment or self.config.current_environment

        if env_name in self.config.environments:
            return self.config.environments[env_name].region
        else:
            # Default to us-west-2
            return "us-west-2"

    @property
    def current_environment(self) -> str:
        """Get the current environment name.

        Returns:
            str: Current environment name.
        """
        return self.config.current_environment

    def set_current_environment(self, env_name: str) -> bool:
        """Set the current environment.

        Args:
            env_name: Environment name.

        Returns:
            bool: True if successful, False otherwise.
        """
        # Check if environment exists
        if env_name not in self.config.environments:
            logger.error(f"Environment '{env_name}' does not exist")
            return False

        # Set current environment
        self.config.current_environment = env_name
        self.save_config()

        logger.debug(f"Current environment set to '{env_name}'")
        return True

    def get_environment(self, name: str | None = None) -> EnvironmentConfig:
        """Get an environment configuration.

        Args:
            name: Optional environment name. If None, uses current environment.

        Returns:
            EnvironmentConfig: Environment configuration.

        Raises:
            KeyError: If the environment does not exist.
        """
        env_name = name or self.config.current_environment

        if env_name not in self.config.environments:
            raise KeyError(f"Environment '{env_name}' does not exist")

        return self.config.environments[env_name]

    def add_environment(self, name: str, region: str) -> bool:
        """Add a new environment.

        Args:
            name: Environment name.
            region: AWS region.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Check if environment already exists
            if name in self.config.environments:
                logger.error(f"Environment '{name}' already exists")
                return False

            # Create environment
            env = EnvironmentConfig(name=name, region=region, created_at=datetime.now())

            # Add to config
            self.config.environments[name] = env

            # Save config
            self.save_config()

            logger.info(f"Environment '{name}' added")
            return True
        except Exception as e:
            logger.error(f"Failed to add environment: {str(e)}")
            return False

    def update_environment(self, name: str, **kwargs: Any) -> bool:
        """Update an environment.

        Args:
            name: Environment name.
            **kwargs: Environment properties to update.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Check if environment exists
            if name not in self.config.environments:
                logger.error(f"Environment '{name}' does not exist")
                return False

            # Get environment
            env = self.config.environments[name]

            # Update properties
            for key, value in kwargs.items():
                if hasattr(env, key):
                    setattr(env, key, value)

            # Update timestamp
            env.updated_at = datetime.now()

            # Save config
            self.save_config()

            logger.info(f"Environment '{name}' updated")
            return True
        except Exception as e:
            logger.error(f"Failed to update environment: {str(e)}")
            return False

    def delete_environment(self, name: str) -> bool:
        """Delete an environment.

        Args:
            name: Environment name.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Check if environment exists
            if name not in self.config.environments:
                logger.error(f"Environment '{name}' does not exist")
                return False

            # Check if it's the current environment
            if name == self.config.current_environment:
                logger.error(f"Cannot delete current environment '{name}'")
                return False

            # Delete environment
            del self.config.environments[name]

            # Save config
            self.save_config()

            logger.info(f"Environment '{name}' deleted")
            return True
        except Exception as e:
            logger.error(f"Failed to delete environment: {str(e)}")
            return False

    def get_agent_runtime(self, name: str, environment: str | None = None) -> AgentRuntime | None:
        """Get an agent runtime by name from the specified or current environment.

        Args:
            name: Agent runtime name.
            environment: Environment name. If None, uses current environment.

        Returns:
            Optional[AgentRuntime]: Agent runtime if found, None otherwise.
        """
        env_name = environment or self.config.current_environment
        try:
            env = self.get_environment(env_name)
            return env.agent_runtimes.get(name)
        except KeyError:
            logger.error(f"Environment '{env_name}' does not exist")
            return None

    def add_agent_runtime(self, name: str, runtime_config: AgentRuntime, environment: str | None = None) -> bool:
        """Add an agent runtime to the specified or current environment.

        Args:
            name: Agent runtime name.
            runtime_config: Agent runtime configuration.
            environment: Environment name. If None, uses current environment.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            env_name = environment or self.config.current_environment
            env = self.get_environment(env_name)

            # Ensure the runtime has the correct region
            runtime_config.region = env.region

            # Set or update the agent runtime in the environment
            env.agent_runtimes[name] = runtime_config

            # Update environment timestamp
            env.updated_at = datetime.now()

            # Save config
            self.save_config()

            logger.info(f"Agent runtime '{name}' added to environment '{env_name}'")
            return True
        except KeyError:
            logger.error(f"Environment '{env_name}' does not exist")
            return False
        except Exception as e:
            logger.error(f"Failed to add agent runtime: {str(e)}")
            return False

    def update_agent_runtime(self, name: str, environment: str | None = None, **kwargs: Any) -> bool:
        """Update an agent runtime in the specified or current environment.

        Args:
            name: Agent runtime name.
            environment: Environment name. If None, uses current environment.
            **kwargs: Runtime properties to update.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            env_name = environment or self.config.current_environment
            env = self.get_environment(env_name)

            # Check if agent runtime exists in this environment
            if name not in env.agent_runtimes:
                logger.error(f"Agent runtime '{name}' does not exist in environment '{env_name}'")
                return False

            # Get agent runtime
            runtime = env.agent_runtimes[name]

            # Update properties
            for key, value in kwargs.items():
                if hasattr(runtime, key):
                    setattr(runtime, key, value)

            # Update timestamp
            runtime.updated_at = datetime.now()
            env.updated_at = datetime.now()

            # Save config
            self.save_config()

            logger.info(f"Agent runtime '{name}' updated in environment '{env_name}'")
            return True
        except KeyError:
            logger.error(f"Environment '{env_name}' does not exist")
            return False
        except Exception as e:
            logger.error(f"Failed to update agent runtime: {str(e)}")
            return False

    def delete_agent_runtime(self, name: str, environment: str | None = None) -> bool:
        """Delete an agent runtime from the specified or current environment.

        Args:
            name: Agent runtime name.
            environment: Environment name. If None, uses current environment.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            env_name = environment or self.config.current_environment
            env = self.get_environment(env_name)

            # Check if agent runtime exists in this environment
            if name not in env.agent_runtimes:
                logger.error(f"Agent runtime '{name}' does not exist in environment '{env_name}'")
                return False

            # Delete agent runtime
            del env.agent_runtimes[name]

            # Update environment timestamp
            env.updated_at = datetime.now()

            # Save config
            self.save_config()

            logger.info(f"Agent runtime '{name}' deleted from environment '{env_name}'")
            return True
        except KeyError:
            logger.error(f"Environment '{env_name}' does not exist")
            return False
        except Exception as e:
            logger.error(f"Failed to delete agent runtime: {str(e)}")
            return False

    def add_ecr_repository(self, name: str, repo_config: ECRRepository) -> bool:
        """Add an ECR repository to global resources.

        Args:
            name: Repository name.
            repo_config: Repository configuration.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Set or update the ECR repository in global resources
            self.config.global_resources.ecr_repositories[name] = repo_config

            # Save config
            self.save_config()

            logger.info(f"ECR repository '{name}' added to global resources")
            return True
        except Exception as e:
            logger.error(f"Failed to add ECR repository: {str(e)}")
            return False

    def add_iam_role(self, name: str, role_config: IAMRoleConfig) -> bool:
        """Add an IAM role to global resources.

        Args:
            name: Role name.
            role_config: Role configuration.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Set or update the IAM role in global resources
            self.config.global_resources.iam_roles[name] = role_config

            # Save config
            self.save_config()

            logger.info(f"IAM role '{name}' added to global resources")
            return True
        except Exception as e:
            logger.error(f"Failed to add IAM role: {str(e)}")
            return False

    def add_cognito_config(self, env_name: str, cognito_config: CognitoConfig) -> bool:
        """Add a Cognito configuration to an environment.

        Args:
            env_name: Environment name.
            cognito_config: Cognito configuration.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Check if environment exists
            if env_name not in self.config.environments:
                logger.error(f"Environment '{env_name}' does not exist")
                return False

            # Get environment
            env = self.config.environments[env_name]

            # Set Cognito config
            env.cognito = cognito_config

            # Update timestamp
            env.updated_at = datetime.now()

            # Save config
            self.save_config()

            logger.info(f"Cognito configuration added to environment '{env_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to add Cognito configuration: {str(e)}")
            return False

    def set_default_agent_runtime(self, env_name: str, agent_name: str) -> bool:
        """Set the default agent runtime for an environment.

        Args:
            env_name: Environment name.
            agent_name: Agent runtime name.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Check if environment exists
            if env_name not in self.config.environments:
                logger.error(f"Environment '{env_name}' does not exist")
                return False

            # Get environment
            env = self.config.environments[env_name]

            # Check if agent runtime exists in this environment
            if agent_name not in env.agent_runtimes:
                logger.error(f"Agent runtime '{agent_name}' does not exist in environment '{env_name}'")
                return False

            # Set default agent runtime
            env.default_agent_runtime = agent_name

            # Update timestamp
            env.updated_at = datetime.now()

            # Save config
            self.save_config()

            logger.info(f"Default agent runtime set to '{agent_name}' in environment '{env_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to set default agent runtime: {str(e)}")
            return False

    def export_config(self, file_path: str) -> bool:
        """Export configuration to a file.

        Args:
            file_path: Path to export the configuration to.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Convert to dict
            config_dict = self.config.model_dump(mode="json")

            # Remove config_path to avoid circular references
            if "config_path" in config_dict:
                del config_dict["config_path"]

            # Write to file
            with open(file_path, "w") as f:
                json.dump(config_dict, f, indent=2, default=str)

            logger.info(f"Configuration exported to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export configuration: {str(e)}")
            return False

    def import_config(self, file_path: str) -> bool:
        """Import configuration from a file.

        Args:
            file_path: Path to import the configuration from.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Read file
            with open(file_path, "r") as f:
                config_data = json.load(f)

            # Parse config
            new_config = AgentCoreConfig.model_validate(config_data)

            # Keep the config path
            new_config.config_path = self.config_file

            # Update config
            self.config = new_config

            # Save config
            self.save_config()

            logger.info(f"Configuration imported from {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to import configuration: {str(e)}")
            return False


# Create singleton instance
config_manager = ConfigManager()
