"""Export tools to Watsonx Orchestrate.

The script iterates over folders in the tools/ directory and imports them into
Orchestrate. The orchestrate environment must be activated before running this script.

Usage:
    python scripts/export_tools_to_orchestrate.py --env wxo_prod
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


def import_tool(tool_dir: Path) -> bool:
    """Import a tool folder using orchestrate tools import.

    Returns:
        True if successful, False otherwise.
    """
    tool_name = tool_dir.name
    # Convention: python file has the same name as the directory
    tool_file = tool_dir / f"{tool_name}.py"
    requirements_file = tool_dir / "requirements.txt"

    if not tool_file.exists():
        logger.warning("Skipping %s: %s does not exist.", tool_dir.name, tool_file.name)
        return False

    cmd = [
        "orchestrate",
        "tools",
        "import",
        "-k",
        "python",
        "-f",
        str(tool_file),
        "-p",
        str(tool_dir),
    ]

    if requirements_file.exists():
        cmd.extend(["-r", str(requirements_file)])
    else:
        logger.error(
            "Skipping %s: requirements.txt is missing and is required.",
            tool_name,
        )
        return False

    logger.info("Importing tool: %s from %s", tool_name, tool_file)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

        if result.returncode == 0:
            logger.info("Successfully imported %s", tool_name)
            return True
        else:
            logger.error(
                "Failed to import %s (return code: %d)\nSTDERR: %s\nSTDOUT: %s",
                tool_name,
                result.returncode,
                result.stderr,
                result.stdout,
            )
            return False
    except subprocess.TimeoutExpired:
        logger.error("Timeout while importing %s (exceeded 120 seconds)", tool_name)
        return False
    except Exception as e:
        logger.error("Unexpected error while importing %s: %s", tool_name, e, exc_info=True)
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export tools to Watsonx Orchestrate",
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
    logger.info("Starting tool export process to Watsonx Orchestrate")
    logger.info("=" * 60)

    # Activate target environment if specified
    if args.env:
        api_key = args.api_key or os.environ.get("WXO_API_KEY")
        activate_environment(args.env, api_key)

    project_root = Path(__file__).parent.parent.resolve()
    tools_folder = project_root / "tools"
    logger.info("Tools folder: %s", tools_folder)

    if not tools_folder.exists():
        logger.error("Tools folder not found: %s", tools_folder)
        sys.exit(1)

    success_count = 0
    failed_tools = []
    total_count = 0

    for tool_directory in tools_folder.iterdir():
        if (
            tool_directory.is_dir()
            and not tool_directory.name.startswith("__")
            and not tool_directory.name.startswith(".")
        ):
            total_count += 1
            logger.info("Processing tool %d: %s", total_count, tool_directory.name)

            try:
                success = import_tool(tool_directory)
                if success:
                    success_count += 1
                else:
                    failed_tools.append(tool_directory.name)
            except Exception as e:
                logger.error(
                    "Failed to process tool %s: %s",
                    tool_directory.name,
                    e,
                    exc_info=True,
                )
                failed_tools.append(tool_directory.name)

    logger.info("=" * 60)
    logger.info("Export process completed")
    logger.info("Successfully exported: %d/%d tools", success_count, total_count)
    if failed_tools:
        logger.warning("Failed tools (%d): %s", len(failed_tools), ", ".join(failed_tools))
    logger.info("=" * 60)

    if failed_tools:
        sys.exit(1)
