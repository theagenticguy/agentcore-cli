"""Configuration synchronization service for AgentCore Platform CLI.

This module handles synchronizing configuration between local files and cloud storage
using AWS Parameter Store. It leverages Pydantic's serialization/deserialization
for robust data handling aligned with our environment-first model structure.
"""

from datetime import datetime, timedelta
from boto3.session import Session
from loguru import logger
from typing import Any
from deepdiff import DeepDiff

from agentcore_cli.models.config import AgentCoreConfig
from agentcore_cli.models.responses import CloudSyncResult, SyncStatus


class ConfigSyncService:
    """Service for synchronizing configuration between local and cloud.

    Uses Pydantic models for robust serialization/deserialization and
    supports our environment-first architecture where each environment
    owns its agent runtimes.
    """

    def __init__(self, region: str, session: Session | None = None, config: AgentCoreConfig | None = None):
        """Initialize the config sync service.

        Args:
            region: AWS region for configuration storage.
            session: Boto3 session to use. If None, creates a new session.
            config: AgentCoreConfig to use.
        """
        self.region = region
        self.session = session or Session(region_name=region)
        self.config = config
        self.ssm_client = self.session.client("ssm", region_name=region)

    @property
    def parameter_store_prefix(self) -> str:
        """Get the parameter store prefix to use for cloud configuration."""
        if self.config and self.config.global_resources.sync_config:
            return self.config.global_resources.sync_config.parameter_store_prefix
        return "/agentcore"

    @property
    def sync_enabled(self) -> bool:
        """Check if cloud sync is enabled."""
        if self.config and self.config.global_resources.sync_config:
            return self.config.global_resources.sync_config.cloud_config_enabled
        return False

    @property
    def auto_sync_enabled(self) -> bool:
        """Check if auto-sync is enabled."""
        if self.config and self.config.global_resources.sync_config:
            return self.config.global_resources.sync_config.auto_sync_enabled
        return False

    @property
    def should_auto_sync(self) -> bool:
        """Check if the configuration should be automatically synced."""
        if not self.sync_enabled or not self.auto_sync_enabled:
            return False

        if not self.config or not self.config.global_resources.sync_config:
            return False

        last_sync = self.config.global_resources.sync_config.last_full_sync
        if not last_sync:
            return True

        now = datetime.now()
        interval_minutes = self.config.global_resources.sync_config.sync_interval_minutes
        interval = timedelta(minutes=interval_minutes)
        return (now - last_sync) > interval

    def _serialize_config_for_cloud(self, config: AgentCoreConfig) -> dict[str, str]:
        """Serialize configuration to flat parameter store format.

        Uses Pydantic's model_dump for robust serialization.

        Args:
            config: Configuration to serialize.

        Returns:
            Flat dictionary of parameter paths to JSON string values.
        """
        params: dict[str, str] = {}

        # Serialize metadata
        params[f"{self.parameter_store_prefix}/meta/current_environment"] = config.current_environment
        params[f"{self.parameter_store_prefix}/meta/last_updated"] = datetime.now().isoformat()

        # Serialize global resources using Pydantic serialization
        global_data = config.global_resources.model_dump(mode="json")

        # Sync config
        for key, value in global_data["sync_config"].items():
            params[f"{self.parameter_store_prefix}/global/sync/{key}"] = str(value)

        # ECR repositories
        for repo_name, repo_data in global_data["ecr_repositories"].items():
            for key, value in repo_data.items():
                if key == "available_tags" and isinstance(value, list):
                    # Handle set serialization
                    params[f"{self.parameter_store_prefix}/global/ecr/{repo_name}/{key}"] = ",".join(value)
                else:
                    params[f"{self.parameter_store_prefix}/global/ecr/{repo_name}/{key}"] = str(value)

        # IAM roles
        for role_name, role_data in global_data["iam_roles"].items():
            for key, value in role_data.items():
                params[f"{self.parameter_store_prefix}/global/iam/{role_name}/{key}"] = str(value)

        # Serialize environments using Pydantic serialization
        for env_name, env_config in config.environments.items():
            env_data = env_config.model_dump(mode="json")

            # Basic environment properties
            for key in ["name", "region", "created_at", "updated_at", "default_agent_runtime"]:
                if key in env_data and env_data[key] is not None:
                    params[f"{self.parameter_store_prefix}/{env_name}/{key}"] = str(env_data[key])

            # Environment variables
            for key, value in env_data.get("environment_variables", {}).items():
                params[f"{self.parameter_store_prefix}/{env_name}/env_vars/{key}"] = str(value)

            # Agent runtimes in this environment
            for agent_name, agent_data in env_data.get("agent_runtimes", {}).items():
                for key, value in agent_data.items():
                    if value is not None:
                        params[f"{self.parameter_store_prefix}/{env_name}/agents/{agent_name}/{key}"] = str(value)

        return params

    def push_config_to_cloud(self, config: AgentCoreConfig) -> CloudSyncResult:
        """Push the local configuration to the cloud using Pydantic serialization."""
        if not self.sync_enabled:
            return CloudSyncResult(
                success=False,
                message="Cloud sync is not enabled",
                environment=config.current_environment,
                synced_items={},
                errors=["Cloud sync is not enabled. Enable it first with 'config sync --enable'."],
            )

        try:
            # Serialize using Pydantic
            params = self._serialize_config_for_cloud(config)

            # Track sync stats
            synced_items: dict[str, int] = {}
            errors: list[str] = []

            # Push each parameter
            for param_name, param_value in params.items():
                try:
                    self.ssm_client.put_parameter(Name=param_name, Value=param_value, Type="String", Overwrite=True)

                    # Track the type for stats
                    param_parts = param_name.split("/")
                    if len(param_parts) >= 3:
                        param_type = param_parts[2]  # e.g., 'global', 'dev', 'meta'
                        synced_items[param_type] = synced_items.get(param_type, 0) + 1

                except Exception as e:
                    errors.append(f"Failed to push parameter {param_name}: {str(e)}")
                    logger.error(f"Failed to push parameter {param_name}: {str(e)}")

            # Update the last sync time
            config.global_resources.sync_config.last_full_sync = datetime.now()

            return CloudSyncResult(
                success=len(errors) == 0,
                message="Configuration pushed to cloud successfully"
                if len(errors) == 0
                else f"Configuration push completed with {len(errors)} errors",
                environment=config.current_environment,
                synced_items=synced_items,
                errors=errors,
            )

        except Exception as e:
            logger.error(f"Failed to push configuration to cloud: {str(e)}")
            return CloudSyncResult(
                success=False,
                message=f"Failed to push configuration to cloud: {str(e)}",
                environment=config.current_environment,
                synced_items={},
                errors=[str(e)],
            )

    def pull_config_from_cloud(self, environment: str | None = None) -> tuple[bool, AgentCoreConfig | None, list[str]]:
        """Pull configuration from the cloud and reconstruct using Pydantic models."""
        if not self.sync_enabled:
            return False, None, ["Cloud sync is not enabled"]

        try:
            # Get all parameters under the prefix
            params = {}
            errors = []
            next_token = None

            while True:
                try:
                    if next_token:
                        response = self.ssm_client.get_parameters_by_path(
                            Path=self.parameter_store_prefix, Recursive=True, NextToken=next_token
                        )
                    else:
                        response = self.ssm_client.get_parameters_by_path(
                            Path=self.parameter_store_prefix, Recursive=True
                        )

                    # Collect parameters
                    for param in response.get("Parameters", []):
                        name = param.get("Name")
                        value = param.get("Value")
                        if name and value:
                            params[name] = value

                    next_token = response.get("NextToken")
                    if not next_token:
                        break

                except Exception as e:
                    errors.append(f"Failed to fetch parameters: {str(e)}")
                    logger.error(f"Failed to fetch parameters: {str(e)}")
                    break

            # Reconstruct configuration using our new structure
            config_data = self._reconstruct_config_from_params(params)

            # Use Pydantic to validate and create the config
            config = AgentCoreConfig.model_validate(config_data)

            return True, config, errors

        except Exception as e:
            logger.error(f"Failed to pull configuration from cloud: {str(e)}")
            return False, None, [str(e)]

    def _reconstruct_config_from_params(self, params: dict[str, str]) -> dict[str, Any]:
        """Reconstruct configuration structure from flat parameter store format."""
        config_data = {
            "current_environment": "dev",  # Default
            "environments": {},
            "global_resources": {
                "ecr_repositories": {},
                "iam_roles": {},
                "sync_config": {
                    "cloud_config_enabled": True,
                    "auto_sync_enabled": True,
                    "parameter_store_prefix": self.parameter_store_prefix,
                    "sync_interval_minutes": 60,
                },
            },
        }

        # Process each parameter
        for param_name, param_value in params.items():
            # Remove prefix and split path
            relative_path = param_name.replace(self.parameter_store_prefix + "/", "")
            parts: list[str] = list(relative_path.split("/"))  # type: ignore[assignment]

            if len(parts) < 2:
                continue

            category: str = parts[0]

            if category == "meta":
                # Handle metadata
                if parts[1] == "current_environment":  # type: ignore[index]
                    config_data["current_environment"] = param_value

            elif category == "global":
                # Handle global resources
                if len(parts) >= 3:
                    resource_type = parts[1]  # type: ignore[index]  # sync, ecr, iam

                    if resource_type == "sync" and len(parts) >= 3:
                        key = parts[2]  # type: ignore[index]
                        if key in ["cloud_config_enabled", "auto_sync_enabled"]:
                            config_data["global_resources"]["sync_config"][key] = param_value.lower() == "true"
                        elif key == "sync_interval_minutes":
                            config_data["global_resources"]["sync_config"][key] = int(param_value)
                        else:
                            config_data["global_resources"]["sync_config"][key] = param_value

                    elif resource_type == "ecr" and len(parts) >= 4:
                        repo_name = parts[2]  # type: ignore[index]
                        key = parts[3]  # type: ignore[index]

                        if repo_name not in config_data["global_resources"]["ecr_repositories"]:
                            config_data["global_resources"]["ecr_repositories"][repo_name] = {}

                        if key == "available_tags":
                            # Handle comma-separated tags
                            config_data["global_resources"]["ecr_repositories"][repo_name][key] = (
                                param_value.split(",") if param_value else []
                            )
                        elif key in ["image_scanning_config"]:
                            config_data["global_resources"]["ecr_repositories"][repo_name][key] = (
                                param_value.lower() == "true"
                            )
                        else:
                            config_data["global_resources"]["ecr_repositories"][repo_name][key] = param_value

                    elif resource_type == "iam" and len(parts) >= 4:
                        role_name = parts[2]  # type: ignore[index]
                        key = parts[3]  # type: ignore[index]

                        if role_name not in config_data["global_resources"]["iam_roles"]:
                            config_data["global_resources"]["iam_roles"][role_name] = {}

                        config_data["global_resources"]["iam_roles"][role_name][key] = param_value

            else:
                # Handle environment-specific data
                env_name = category

                if env_name not in config_data["environments"]:
                    config_data["environments"][env_name] = {
                        "name": env_name,
                        "region": "us-east-1",  # Default
                        "agent_runtimes": {},
                        "environment_variables": {},
                    }

                if len(parts) == 2:
                    # Direct environment property
                    key = parts[1]  # type: ignore[index]
                    config_data["environments"][env_name][key] = param_value

                elif len(parts) >= 3:
                    subcategory = parts[1]  # type: ignore[index]

                    if subcategory == "env_vars" and len(parts) >= 3:
                        var_name = parts[2]  # type: ignore[index]
                        config_data["environments"][env_name]["environment_variables"][var_name] = param_value

                    elif subcategory == "agents" and len(parts) >= 4:
                        agent_name = parts[2]  # type: ignore[index]
                        key = parts[3]  # type: ignore[index]

                        if agent_name not in config_data["environments"][env_name]["agent_runtimes"]:
                            config_data["environments"][env_name]["agent_runtimes"][agent_name] = {}

                        config_data["environments"][env_name]["agent_runtimes"][agent_name][key] = param_value

        return config_data

    def check_sync_status(self, config: AgentCoreConfig, environment: str | None = None) -> SyncStatus:
        """Check the sync status between local and cloud configuration."""
        env = environment or config.current_environment

        if not self.sync_enabled:
            return SyncStatus(
                environment=env,
                cloud_config_enabled=False,
                auto_sync_enabled=self.auto_sync_enabled,
                last_sync=config.global_resources.sync_config.last_full_sync,
                in_sync=False,
            )

        # Pull cloud configuration for comparison
        success, cloud_config, errors = self.pull_config_from_cloud(env)

        if not success or cloud_config is None:
            return SyncStatus(
                environment=env,
                cloud_config_enabled=True,
                auto_sync_enabled=self.auto_sync_enabled,
                last_sync=config.global_resources.sync_config.last_full_sync,
                in_sync=False,
                drift_details={"errors": {"pull": errors}},
            )

        # Check for drift using Pydantic comparison
        drift_details = self._detect_drift_with_pydantic(config, cloud_config, env)
        in_sync = all(len(category_drifts) == 0 for category_drifts in drift_details.values())

        return SyncStatus(
            environment=env,
            cloud_config_enabled=True,
            auto_sync_enabled=self.auto_sync_enabled,
            last_sync=config.global_resources.sync_config.last_full_sync,
            in_sync=in_sync,
            drift_details=drift_details if not in_sync else None,
        )

    def _detect_drift_with_pydantic(
        self, local_config: AgentCoreConfig, cloud_config: AgentCoreConfig, environment: str
    ) -> dict[str, dict[str, list[str]]]:
        """Detect drift between configurations using DeepDiff for granular analysis."""
        # Get serialized data for comparison
        local_data = local_config.model_dump(mode="json")
        cloud_data = cloud_config.model_dump(mode="json")

        # Use DeepDiff for comprehensive comparison
        diff = DeepDiff(
            local_data,
            cloud_data,
            ignore_order=True,
            exclude_paths=[
                # Ignore metadata that changes automatically
                "root['global_resources']['sync_config']['last_full_sync']",
                "root['environments']['*']['updated_at']",
                "root['environments']['*']['agent_runtimes']['*']['updated_at']",
                "root['global_resources']['ecr_repositories']['*']['last_sync']",
                "root['global_resources']['ecr_repositories']['*']['last_push']",
                "root['global_resources']['iam_roles']['*']['last_sync']",
            ],
            ignore_numeric_type_changes=True,  # Handle "60" vs 60
            ignore_string_case=True,  # Handle "true" vs "True"
        )

        # Convert DeepDiff results to structured drift information
        return self._format_drift_results(diff, environment)

    def _format_drift_results(self, diff: DeepDiff, environment: str) -> dict[str, dict[str, list[str]]]:
        """Convert DeepDiff results to structured drift information."""
        drift: dict[str, dict[str, list[str]]] = {
            "environments": {"local_only": [], "cloud_only": [], "different": []},
            "agent_runtimes": {"local_only": [], "cloud_only": [], "different": []},
            "global_resources": {"local_only": [], "cloud_only": [], "different": []},
            "detailed_changes": {"values_changed": [], "items_added": [], "items_removed": []},
        }

        # Process value changes
        if "values_changed" in diff:
            for path, change in diff["values_changed"].items():
                formatted_change = self._format_value_change(path, change, environment)
                if formatted_change:
                    category, details = formatted_change
                    drift[category]["different"].append(details)
                    drift["detailed_changes"]["values_changed"].append(details)

        # Process additions
        if "dictionary_item_added" in diff:
            for path in diff["dictionary_item_added"]:
                path_str = str(path)  # Ensure path is treated as string
                formatted_addition = self._format_item_addition(path_str, environment)
                if formatted_addition:
                    category, details = formatted_addition
                    drift[category]["cloud_only"].append(details)
                    drift["detailed_changes"]["items_added"].append(details)

        # Process removals
        if "dictionary_item_removed" in diff:
            for path in diff["dictionary_item_removed"]:
                path_str = str(path)  # Ensure path is treated as string
                formatted_removal = self._format_item_removal(path_str, environment)
                if formatted_removal:
                    category, details = formatted_removal
                    drift[category]["local_only"].append(details)
                    drift["detailed_changes"]["items_removed"].append(details)

        # Remove empty categories for cleaner output
        return {k: v for k, v in drift.items() if self._has_changes(v)}

    def _format_value_change(self, path: str, change: dict, target_env: str) -> tuple[str, str] | None:
        """Format a value change into readable description."""
        # Parse the path to understand what changed
        path_clean = path.replace("root['", "").replace("']", "").replace("']['", ".")

        old_value = change.get("old_value", "N/A")
        new_value = change.get("new_value", "N/A")

        # Categorize by path structure
        if path_clean.startswith("environments."):
            env_parts: list[str] = path_clean.split(".")
            if len(env_parts) >= 2:
                env_name = env_parts[1]
                if env_name == target_env or target_env == "all":
                    if "agent_runtimes" in path_clean and len(env_parts) >= 4:
                        agent_name = env_parts[3]
                        field = ".".join(env_parts[4:]) if len(env_parts) > 4 else "config"
                        return ("agent_runtimes", f"{env_name}:{agent_name}:{field} ({old_value} → {new_value})")
                    else:
                        field = ".".join(env_parts[2:]) if len(env_parts) > 2 else "config"
                        return ("environments", f"{env_name}:{field} ({old_value} → {new_value})")

        elif path_clean.startswith("global_resources."):
            global_parts: list[str] = path_clean.split(".")
            if len(global_parts) >= 2:
                resource_type = global_parts[1]
                if resource_type in ["ecr_repositories", "iam_roles"] and len(global_parts) >= 3:
                    resource_name = global_parts[2]
                    field = ".".join(global_parts[3:]) if len(global_parts) > 3 else "config"
                    return ("global_resources", f"{resource_type}.{resource_name}:{field} ({old_value} → {new_value})")
                else:
                    field = ".".join(global_parts[1:])
                    return ("global_resources", f"{field} ({old_value} → {new_value})")

        return None

    def _format_item_addition(self, path: str, target_env: str) -> tuple[str, str] | None:
        """Format an item addition into readable description."""
        path_clean = path.replace("root['", "").replace("']", "").replace("']['", ".")

        if path_clean.startswith("environments."):
            env_parts: list[str] = path_clean.split(".")
            if len(env_parts) >= 2:
                env_name = env_parts[1]
                if env_name == target_env or target_env == "all":
                    if "agent_runtimes" in path_clean and len(env_parts) >= 4:
                        agent_name = env_parts[3]
                        return ("agent_runtimes", f"{env_name}:{agent_name} (added in cloud)")
                    else:
                        return ("environments", f"{env_name} (added in cloud)")

        elif path_clean.startswith("global_resources."):
            global_parts: list[str] = path_clean.split(".")
            if len(global_parts) >= 3:
                resource_type = global_parts[1]
                resource_name = global_parts[2]
                return ("global_resources", f"{resource_type}.{resource_name} (added in cloud)")

        return None

    def _format_item_removal(self, path: str, target_env: str) -> tuple[str, str] | None:
        """Format an item removal into readable description."""
        path_clean = path.replace("root['", "").replace("']", "").replace("']['", ".")

        if path_clean.startswith("environments."):
            env_parts: list[str] = path_clean.split(".")
            if len(env_parts) >= 2:
                env_name = env_parts[1]
                if env_name == target_env or target_env == "all":
                    if "agent_runtimes" in path_clean and len(env_parts) >= 4:
                        agent_name = env_parts[3]
                        return ("agent_runtimes", f"{env_name}:{agent_name} (removed from cloud)")
                    else:
                        return ("environments", f"{env_name} (removed from cloud)")

        elif path_clean.startswith("global_resources."):
            global_parts: list[str] = path_clean.split(".")
            if len(global_parts) >= 3:
                resource_type = global_parts[1]
                resource_name = global_parts[2]
                return ("global_resources", f"{resource_type}.{resource_name} (removed from cloud)")

        return None

    def _has_changes(self, category_drift: dict) -> bool:
        """Check if a drift category has any changes."""
        if isinstance(category_drift, dict):
            return any(len(v) > 0 if isinstance(v, list) else self._has_changes(v) for v in category_drift.values())
        elif isinstance(category_drift, list):
            return len(category_drift) > 0
        return False

    def get_drift_summary(self, drift_details: dict) -> str:
        """Generate a human-readable summary of drift details."""
        if not drift_details or not any(self._has_changes(v) for v in drift_details.values()):
            return "✅ No drift detected - local and cloud configurations are in sync"

        summary_lines = ["🔄 Configuration drift detected:"]

        # Environment changes
        env_drift = drift_details.get("environments", {})
        if self._has_changes(env_drift):
            summary_lines.append("\n📁 Environment Changes:")
            for change_type, changes in env_drift.items():
                if changes:
                    type_label = {"local_only": "Local only", "cloud_only": "Cloud only", "different": "Modified"}
                    summary_lines.append(f"  • {type_label.get(change_type, change_type)}:")
                    for change in changes[:5]:  # Limit to first 5
                        summary_lines.append(f"    - {change}")
                    if len(changes) > 5:
                        summary_lines.append(f"    ... and {len(changes) - 5} more")

        # Agent runtime changes
        runtime_drift = drift_details.get("agent_runtimes", {})
        if self._has_changes(runtime_drift):
            summary_lines.append("\n🤖 Agent Runtime Changes:")
            for change_type, changes in runtime_drift.items():
                if changes:
                    type_label = {"local_only": "Local only", "cloud_only": "Cloud only", "different": "Modified"}
                    summary_lines.append(f"  • {type_label.get(change_type, change_type)}:")
                    for change in changes[:5]:
                        summary_lines.append(f"    - {change}")
                    if len(changes) > 5:
                        summary_lines.append(f"    ... and {len(changes) - 5} more")

        # Global resource changes
        global_drift = drift_details.get("global_resources", {})
        if self._has_changes(global_drift):
            summary_lines.append("\n🌍 Global Resource Changes:")
            for change_type, changes in global_drift.items():
                if changes:
                    type_label = {"local_only": "Local only", "cloud_only": "Cloud only", "different": "Modified"}
                    summary_lines.append(f"  • {type_label.get(change_type, change_type)}:")
                    for change in changes[:3]:
                        summary_lines.append(f"    - {change}")
                    if len(changes) > 3:
                        summary_lines.append(f"    ... and {len(changes) - 3} more")

        return "\n".join(summary_lines)

    def enable_cloud_sync(self, config: AgentCoreConfig, enable: bool = True) -> bool:
        """Enable or disable cloud configuration sync."""
        try:
            # Update sync config
            config.global_resources.sync_config.cloud_config_enabled = enable

            # If enabling, push the configuration to the cloud
            if enable:
                result = self.push_config_to_cloud(config)
                return result.success

            return True

        except Exception as e:
            logger.error(f"Failed to {'enable' if enable else 'disable'} cloud sync: {str(e)}")
            return False

    def enable_auto_sync(self, config: AgentCoreConfig, enable: bool = True) -> bool:
        """Enable or disable automatic configuration sync."""
        try:
            # Update sync config
            config.global_resources.sync_config.auto_sync_enabled = enable

            # Push the updated configuration to the cloud if cloud sync is enabled
            if config.global_resources.sync_config.cloud_config_enabled:
                param_name = f"{self.parameter_store_prefix}/global/sync/auto_sync_enabled"
                self.ssm_client.put_parameter(Name=param_name, Value=str(enable).lower(), Type="String", Overwrite=True)

            return True

        except Exception as e:
            logger.error(f"Failed to {'enable' if enable else 'disable'} auto-sync: {str(e)}")
            return False

    def check_and_auto_sync(self, config: AgentCoreConfig) -> bool:
        """Check if auto-sync is enabled and sync if needed."""
        if not self.should_auto_sync:
            return True

        try:
            result = self.push_config_to_cloud(config)
            return result.success

        except Exception as e:
            logger.error(f"Failed to auto-sync configuration: {str(e)}")
            return False
