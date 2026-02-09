"""Import tools from Watsonx Orchestrate and save them to the tools/ directory.

The orchestrate environment must be activated before running this script.

Usage:
    python scripts/import_tools_from_orchestrate.py --env wxo_test --verbose
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

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


def run_orchestrate_tools_list() -> list[dict[str, Any]] | dict[str, Any] | None:
    """Run the orchestrate tools list command and return parsed JSON."""
    logger.info("Fetching list of tools from Watsonx Orchestrate...")
    try:
        result = subprocess.run(
            ["orchestrate", "tools", "list", "-v"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if result.returncode != 0:
            logger.error(
                "Failed to list tools (return code: %d)\nSTDERR: %s\nSTDOUT: %s",
                result.returncode,
                result.stderr,
                result.stdout,
            )
            return None
        logger.info("Successfully retrieved tools list")
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        logger.error("Timeout while listing tools (exceeded 60 seconds)")
        return None
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON response: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected error while listing tools: %s", e, exc_info=True)
        return None


def export_and_extract_tool(tool_name: str, project_root: Path, max_retries: int = 3) -> bool:
    """Export a tool as a zip and extract all files into the tools/ folder.

    Args:
        tool_name: Name of the tool to export.
        project_root: Root directory of the project.
        max_retries: Maximum number of retry attempts for timeouts.

    Returns:
        True if successful, False otherwise.
    """
    tools_dir = project_root / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    zip_path = tools_dir / f"{tool_name}.zip"

    logger.info("Starting export for tool: %s", tool_name)

    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                logger.info("Retry attempt %d/%d for tool: %s", attempt, max_retries, tool_name)
                time.sleep(3 * attempt)

            result = subprocess.run(
                [
                    "orchestrate",
                    "tools",
                    "export",
                    "-n",
                    tool_name,
                    "-o",
                    str(zip_path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=180,
            )

            if result.returncode != 0:
                logger.error(
                    "Failed to export tool %s (return code: %d)\nSTDERR: %s\nSTDOUT: %s",
                    tool_name,
                    result.returncode,
                    result.stderr,
                    result.stdout,
                )
                return False

            logger.info("Successfully exported tool %s", tool_name)
            break

        except subprocess.TimeoutExpired:
            if attempt < max_retries:
                logger.warning(
                    "Timeout while exporting tool %s (exceeded 180 seconds). Retrying...",
                    tool_name,
                )
                continue
            else:
                logger.error(
                    "Timeout while exporting tool %s after %d attempts",
                    tool_name,
                    max_retries,
                )
                return False
        except Exception as e:
            logger.error("Unexpected error while exporting tool %s: %s", tool_name, e, exc_info=True)
            return False

    # Extract zip
    extract_path = tools_dir / tool_name
    if extract_path.exists():
        logger.debug("Removing existing tool directory: %s", extract_path)
        shutil.rmtree(extract_path)
    extract_path.mkdir(parents=True, exist_ok=True)

    try:
        logger.info("Extracting tool %s to %s", tool_name, extract_path)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)
        logger.info("Successfully extracted %s to %s", tool_name, extract_path)
        return True
    except zipfile.BadZipFile:
        logger.exception("Invalid zip file for tool %s", tool_name)
        return False
    except OSError as e:
        logger.exception("File system error while extracting tool %s: %s", tool_name, e)
        return False
    except Exception as e:
        logger.exception("Unexpected error while extracting tool %s: %s", tool_name, e)
        return False
    finally:
        if zip_path.exists():
            zip_path.unlink(missing_ok=True)
            logger.debug("Cleaned up temporary zip file: %s", zip_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import tools from Watsonx Orchestrate",
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
    logger.info("Starting tool import process from Watsonx Orchestrate")
    logger.info("Max retry attempts: %d", args.retries)
    logger.info("=" * 60)

    # Activate target environment if specified
    if args.env:
        api_key = args.api_key or os.environ.get("WXO_API_KEY")
        activate_environment(args.env, api_key)

    project_root = Path(__file__).parent.parent.resolve()
    logger.info("Project root: %s", project_root)

    tools_list = run_orchestrate_tools_list()
    if not tools_list:
        logger.error("Failed to retrieve tools list. Exiting.")
        sys.exit(1)

    # Handle if the output is a list or a dict with a 'tools' key
    tools_to_process = (
        tools_list if isinstance(tools_list, list) else tools_list.get("tools", [])
    )

    # Filter out MCP tools (they cannot be exported, only imported from MCP server)
    exportable_tools = []
    mcp_tools = []
    for tool in tools_to_process:
        binding = tool.get("binding", {})
        if "mcp" in binding:
            mcp_tools.append(tool.get("name", "unknown"))
        else:
            exportable_tools.append(tool)

    logger.info("Found %d total tool(s)", len(tools_to_process))
    logger.info("Found %d exportable tool(s) (excluding %d MCP tools)", len(exportable_tools), len(mcp_tools))
    if mcp_tools:
        logger.info("Skipping MCP tools: %s", ", ".join(mcp_tools))

    success_count = 0
    failed_tools = []

    for idx, tool in enumerate(exportable_tools, 1):
        tool_name = tool.get("name")
        if not tool_name:
            logger.warning("Skipping tool at index %d (no name found)", idx)
            continue

        logger.info("Processing tool %d/%d: %s", idx, len(exportable_tools), tool_name)
        try:
            success = export_and_extract_tool(tool_name, project_root, args.retries)
            if success:
                success_count += 1
            else:
                failed_tools.append(tool_name)
        except Exception as e:
            logger.error("Failed to process tool %s: %s", tool_name, e, exc_info=True)
            failed_tools.append(tool_name)

    logger.info("=" * 60)
    logger.info("Import process completed")
    logger.info("Successfully imported: %d/%d exportable tools", success_count, len(exportable_tools))
    if failed_tools:
        logger.warning("Failed tools (%d): %s", len(failed_tools), ", ".join(failed_tools))
    logger.info("=" * 60)

    if failed_tools:
        sys.exit(1)
