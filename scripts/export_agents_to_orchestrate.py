"""Push local native agent YAML definitions to Watsonx Orchestrate.

The script iterates over agent YAML files in the agents/ directory and imports
them into the active (or specified) Orchestrate environment.
Optionally deploys the agents from draft to live state.

Usage:
    python scripts/export_agents_to_orchestrate.py --env wxo_test
    python scripts/export_agents_to_orchestrate.py --env wxo_prod --deploy
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def activate_environment(env_name: str, api_key: str | None = None) -> None:
    """Activate a WXO environment before running CLI commands."""
    cmd = ["orchestrate", "env", "activate", env_name]
    if api_key:
        cmd.extend(["--api-key", api_key])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to activate env '{env_name}': {result.stderr}"
        )
    logger.info("Activated environment: %s", env_name)


def deploy_agent(agent_name: str) -> bool:
    """Deploy an agent from draft to live state."""
    logger.info("Deploying agent %s to live...", agent_name)
    try:
        result = subprocess.run(
            ["orchestrate", "agents", "deploy", "--name", agent_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("Successfully deployed %s to live", agent_name)
            return True
        else:
            logger.error(
                "Failed to deploy %s (return code: %d)\nSTDERR: %s\nSTDOUT: %s",
                agent_name,
                result.returncode,
                result.stderr,
                result.stdout,
            )
            return False
    except Exception as e:
        logger.error("Error deploying %s: %s", agent_name, e, exc_info=True)
        return False


def import_agent_file(agent_file: Path, do_deploy: bool = False) -> bool:
    """Import an agent file using orchestrate agents import.

    Args:
        agent_file: Path to the agent YAML file.
        do_deploy: If True, deploy the agent to live after import.

    Returns:
        True if successful, False otherwise.
    """
    logger.info("Importing agent from file: %s", agent_file)
    try:
        result = subprocess.run(
            ["orchestrate", "agents", "import", "-f", str(agent_file)],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("Successfully imported %s", agent_file.name)
            if do_deploy:
                agent_name = agent_file.stem
                if not deploy_agent(agent_name):
                    return False
            return True
        else:
            logger.error(
                "Failed to import %s (return code: %d)\nSTDERR: %s\nSTDOUT: %s",
                agent_file.name,
                result.returncode,
                result.stderr,
                result.stdout,
            )
            return False
    except subprocess.TimeoutExpired:
        logger.error("Timeout while importing %s (exceeded 120 seconds)", agent_file.name)
        return False
    except Exception as e:
        logger.error("Unexpected error while importing %s: %s", agent_file.name, e, exc_info=True)
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export native agents to Watsonx Orchestrate",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )
    parser.add_argument(
        "--env",
        type=str,
        default=None,
        help="Name of the WXO environment to activate before import",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for non-interactive environment activation (falls back to WXO_API_KEY env var)",
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Deploy agents to live state after importing (draft → live)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("=" * 60)
    logger.info("Starting agent export process to Watsonx Orchestrate")
    logger.info("=" * 60)

    # Activate target environment if specified
    if args.env:
        api_key = args.api_key or os.environ.get("WXO_API_KEY")
        activate_environment(args.env, api_key)

    agents_folder = (Path(__file__).parent.parent / "agents").resolve()
    logger.info("Scanning agents folder: %s", agents_folder)

    if not agents_folder.exists():
        logger.error("Agents folder not found: %s", agents_folder)
        sys.exit(1)

    success_count = 0
    failed_agents = []
    total_count = 0

    for agent_folder in agents_folder.iterdir():
        if not agent_folder.is_dir() or agent_folder.name.startswith(("__", ".")):
            continue

        agents_type_path = agent_folder / "agents"
        if not agents_type_path.exists():
            logger.warning("Skipping %s: no 'agents' subfolder found", agent_folder.name)
            continue

        for agent_type_folder in agents_type_path.iterdir():
            if agent_type_folder.name != "native":
                logger.debug("Skipping non-native agent type: %s", agent_type_folder.name)
                continue

            for agent_file in agent_type_folder.glob("*.yaml"):
                total_count += 1
                logger.info("Processing agent file %d: %s", total_count, agent_file.name)

                try:
                    success = import_agent_file(agent_file, do_deploy=args.deploy)
                    if success:
                        success_count += 1
                    else:
                        failed_agents.append(agent_file.name)
                except Exception as e:
                    logger.error("Failed to process %s: %s", agent_file.name, e, exc_info=True)
                    failed_agents.append(agent_file.name)

    logger.info("=" * 60)
    logger.info("Export process completed")
    logger.info("Successfully exported: %d/%d agents", success_count, total_count)
    if failed_agents:
        logger.warning("Failed agents (%d): %s", len(failed_agents), ", ".join(failed_agents))
    logger.info("=" * 60)

    if failed_agents:
        sys.exit(1)
