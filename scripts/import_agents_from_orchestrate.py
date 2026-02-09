"""Import native agents from Watsonx Orchestrate and save them as YAML files.

The orchestrate environment must be activated before running this script.

Usage:
    python scripts/import_agents_from_orchestrate.py --env wxo_test --verbose
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

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


def run_orchestrate_agents_list():
    """Run the orchestrate agents list command and return parsed JSON."""
    logger.info("Fetching list of native agents from Watsonx Orchestrate...")
    try:
        result = subprocess.run(
            ["orchestrate", "agents", "list", "--kind", "native", "-v"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.error(
                "Failed to list agents (return code: %d)\nSTDERR: %s\nSTDOUT: %s",
                result.returncode,
                result.stderr,
                result.stdout,
            )
            return None
        logger.info("Successfully retrieved agents list")
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        logger.error("Timeout while listing agents (exceeded 60 seconds)")
        return None
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON response: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected error while listing agents: %s", e, exc_info=True)
        return None


def export_and_extract_agent(
    agent_name: str,
    project_root: Path,
    max_retries: int = 3,
    agent_data: dict = None,
):
    """Export an agent YAML without dependencies to the agents/ folder.

    Args:
        agent_name: Name of the agent to export.
        project_root: Root directory of the project.
        max_retries: Maximum number of retry attempts for timeouts.
        agent_data: Full agent data from agents list (used to add LLM config).
    """
    logger.info("Starting export for agent: %s", agent_name)

    agents_dir = project_root / "agents" / agent_name / "agents" / "native"
    agents_dir.mkdir(parents=True, exist_ok=True)
    output_path = agents_dir / f"{agent_name}.yaml"

    command = [
        "orchestrate",
        "agents",
        "export",
        "-n",
        agent_name,
        "-k",
        "native",
        "-o",
        str(output_path),
        "--agent-only",
    ]

    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                logger.info("Retry attempt %d/%d for agent: %s", attempt, max_retries, agent_name)
                time.sleep(5 * attempt)

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                logger.error(
                    "Failed to export agent %s (return code: %d)\nSTDERR: %s\nSTDOUT: %s",
                    agent_name,
                    result.returncode,
                    result.stderr,
                    result.stdout,
                )
                return False
            logger.info("Successfully exported agent %s to %s", agent_name, output_path)
            break
        except subprocess.TimeoutExpired:
            if attempt < max_retries:
                logger.warning(
                    "Timeout while exporting agent %s (exceeded 300 seconds). Retrying...",
                    agent_name,
                )
                continue
            else:
                logger.error(
                    "Timeout while exporting agent %s after %d attempts",
                    agent_name,
                    max_retries,
                )
                return False
        except Exception as e:
            logger.error("Unexpected error while exporting agent %s: %s", agent_name, e, exc_info=True)
            return False

    # Enrich YAML with LLM config from agent data if available
    if agent_data and output_path.exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                yaml_content = yaml.safe_load(f)

            llm_config = agent_data.get("llm_config", {})
            if llm_config and "llm_config" not in yaml_content:
                filtered_config = {k: v for k, v in llm_config.items() if v is not None}
                if filtered_config:
                    yaml_content["llm_config"] = filtered_config
                    with open(output_path, "w", encoding="utf-8") as f:
                        yaml.dump(
                            yaml_content,
                            f,
                            default_flow_style=False,
                            allow_unicode=True,
                            sort_keys=False,
                        )
                    logger.info("Added LLM config to %s", agent_name)
        except Exception as e:
            logger.warning("Could not add LLM config to %s: %s", agent_name, e)

    logger.info("Agent %s YAML saved to %s", agent_name, output_path)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import native agents from Watsonx Orchestrate (agent-only mode)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/import_agents_from_orchestrate.py --env wxo_test --verbose
  python scripts/import_agents_from_orchestrate.py --retries 5
        """,
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Maximum number of retry attempts for timeouts (default: 3)",
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
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("=" * 60)
    logger.info("Starting agent import process from Watsonx Orchestrate")
    logger.info("Max retry attempts: %d", args.retries)
    logger.info("=" * 60)

    # Activate target environment if specified
    if args.env:
        api_key = args.api_key or os.environ.get("WXO_API_KEY")
        activate_environment(args.env, api_key)

    project_root = Path(__file__).parent.parent.resolve()
    logger.info("Project root: %s", project_root)

    data = run_orchestrate_agents_list()
    if not data:
        logger.error("Failed to retrieve agents list. Exiting.")
        sys.exit(1)

    native_agents = data.get("native", [])
    logger.info("Found %d total native agent(s)", len(native_agents))

    # Filter to only live agents (not hidden)
    live_agents = [agent for agent in native_agents if not agent.get("hidden", False)]
    logger.info("Found %d live agent(s) to import (excluding hidden agents)", len(live_agents))

    if len(native_agents) > len(live_agents):
        hidden_count = len(native_agents) - len(live_agents)
        logger.info("Skipping %d hidden agent(s)", hidden_count)

    success_count = 0
    failed_agents = []

    for idx, agent in enumerate(live_agents, 1):
        agent_name = agent.get("name")
        if not agent_name:
            logger.warning("Skipping agent at index %d (no name found)", idx)
            continue

        logger.info("Processing agent %d/%d: %s", idx, len(live_agents), agent_name)
        try:
            success = export_and_extract_agent(
                agent_name, project_root, args.retries, agent_data=agent
            )
            if success:
                success_count += 1
            else:
                failed_agents.append(agent_name)
        except Exception as e:
            logger.error("Failed to process agent %s: %s", agent_name, e, exc_info=True)
            failed_agents.append(agent_name)

    logger.info("=" * 60)
    logger.info("Import process completed")
    logger.info("Successfully imported: %d/%d live agents", success_count, len(live_agents))
    if failed_agents:
        logger.warning("Failed agents (%d): %s", len(failed_agents), ", ".join(failed_agents))
    logger.info("=" * 60)

    if failed_agents:
        sys.exit(1)
