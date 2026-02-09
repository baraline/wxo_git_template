# watsonx Orchestrate — Git-Managed Agents & Tools

> **This is a GitHub template repository.** Click **"Use this template"** to create your own copy.

A ready-to-use project structure for managing [IBM watsonx Orchestrate](https://www.ibm.com/products/watsonx-orchestrate) agents, tools, and knowledge bases as code — with version control, automated testing, and CI/CD deployments.

ADK documentation: <https://developer.watson-orchestrate.ibm.com/>

---

## Why Git-driven?

| Pain point (UI-only) | Git-based solution |
|---|---|
| "Who changed the prompt last Friday?" | `git log --oneline agents/` |
| Simultaneous edits overwrite each other | Branches + pull-request reviews |
| Rolling back means manual re-typing | `git revert` + re-import |
| Promoting multiple agents to production | Release tag triggers automated deploy |

You get **versioning, collaboration, code review, automated testing, and deterministic deployments** — the same safety nets every other piece of software gets from Git.

---

## Prerequisites

- **Python 3.12** (tools run on Python 3.12 in Orchestrate)
- **IBM watsonx Orchestrate account** — [free 30-day trial](https://www.ibm.com/account/reg/us-en/signup?formid=urx-52753)
- **Git** and a GitHub account

---

## Quick start

```bash
# 1. Clone your copy of this template
git clone https://github.com/baraline/wxo_git_template.git
cd wxo_git_template

# 2. Create and activate a virtual environment
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. (Optional) Install dev dependencies for linting & testing
pip install -e ".[dev]"

# 6. Register your Orchestrate environments
orchestrate env add \
  -n wxo_test \
  -u https://api.<region>.watson-orchestrate.cloud.ibm.com/instances/<test-instance-id> \
  --type ibm_iam

orchestrate env add \
  -n wxo_prod \
  -u https://api.<region>.watson-orchestrate.cloud.ibm.com/instances/<prod-instance-id> \
  --type ibm_iam

# 7. Activate an environment (you'll be prompted for your API key)
orchestrate env activate wxo_test

# 8. Set up pre-commit hooks
pip install pre-commit
pre-commit install
```

---

## Repository structure

```
.
├── .github/workflows/              # CI/CD pipelines
│   ├── test-tools.yml              # Run tool tests on PR / push
│   ├── pre-commit.yml              # Lint checks on PR / push
│   ├── deploy-draft.yml            # Deploy to test env on push to main
│   └── deploy-live.yml             # Deploy to prod on GitHub release
├── agents/                         # One folder per agent
│   └── <agent_name>/
│       └── agents/native/
│           └── <agent_name>.yaml   # Agent specification
├── tools/                          # One folder per tool
│   └── <tool_name>/
│       ├── <tool_name>.py          # @tool-decorated Python function
│       ├── requirements.txt        # Tool-specific dependencies
│       ├── __init__.py
│       └── tests/
│           ├── __init__.py
│           └── test_<tool_name>.py
├── scripts/                        # CLI wrappers for import / export
│   ├── import_agents_from_orchestrate.py
│   ├── export_agents_to_orchestrate.py
│   ├── import_tools_from_orchestrate.py
│   └── export_tools_to_orchestrate.py
├── pyproject.toml                  # Project config (pytest, ruff)
├── conftest.py                     # Shared pytest fixtures
├── requirements.txt                # Pinned base dependencies
├── .pre-commit-config.yaml         # Ruff linting on commit
├── CONTRIBUTING.md                 # Guide for adding agents & tools
└── .gitignore
```

### Key conventions

- **`agents/<name>/agents/native/<name>.yaml`** — mirrors the folder layout produced by `orchestrate agents export`, so import/export scripts work with zero configuration.
- **`tools/<name>/`** — one directory per tool. The Python file has the **same name** as the directory. Each tool ships its own `requirements.txt`.
- **`scripts/`** — automation helpers that wrap the ADK CLI. All support `--env`, `--api-key`, and `--verbose` flags.

---

## Scripts

### Pull from Orchestrate → Git

```bash
# Import all agents from the test environment
python scripts/import_agents_from_orchestrate.py --env wxo_test --verbose

# Import all tools
python scripts/import_tools_from_orchestrate.py --env wxo_test --verbose
```

### Push from Git → Orchestrate

```bash
# Push agents to test (draft only)
python scripts/export_agents_to_orchestrate.py --env wxo_test

# Push agents to production AND deploy to live
python scripts/export_agents_to_orchestrate.py --env wxo_prod --deploy

# Push tools
python scripts/export_tools_to_orchestrate.py --env wxo_prod
```

For CI / non-interactive usage:

```bash
python scripts/export_agents_to_orchestrate.py \
  --env wxo_prod --api-key "$WXO_API_KEY" --deploy
```

---

## Adding a new agent

1. Create the folder structure:
   ```
   agents/My_New_Agent/agents/native/My_New_Agent.yaml
   ```
2. Write the agent YAML (see [agents/My_Example_Agent](agents/My_Example_Agent/agents/native/My_Example_Agent.yaml) for a reference).
3. Push to Orchestrate:
   ```bash
   python scripts/export_agents_to_orchestrate.py --env wxo_test
   ```

> **Tip:** You can also import an existing agent from Orchestrate with the import script, edit the YAML locally, and push it back.

---

## Adding a new tool

1. Create the tool directory:
   ```
   tools/my_new_tool/
   ├── my_new_tool.py
   ├── requirements.txt
   ├── __init__.py
   └── tests/
       ├── __init__.py
       └── test_my_new_tool.py
   ```
2. Decorate your function with `@tool()` from `ibm_watsonx_orchestrate.agent_builder.tools`.
3. List dependencies in `requirements.txt` (pin exact versions).
4. Write tests — they run automatically in CI.
5. Push:
   ```bash
   python scripts/export_tools_to_orchestrate.py --env wxo_test
   ```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines and the example tool in [tools/hello_world](tools/hello_world/).

---

## Running tests locally

```bash
# Run all tool tests
pytest tools/ -v

# Run tests for a specific tool
pytest tools/hello_world/tests/ -v
```

---

## CI/CD

| Trigger | Workflow | Action |
|---|---|---|
| PR / push to `main` (changes in `tools/`) | `test-tools.yml` | Run `pytest` on all tool tests |
| PR / push to `main` | `pre-commit.yml` | Run ruff linting & formatting checks |
| Push to `main` (changes in `agents/` or `tools/`) | `deploy-draft.yml` | Deploy to test environment (draft) |
| GitHub release published | `deploy-live.yml` | Deploy to production and promote to live |

### Required GitHub configuration

#### Secrets

| Name | Description |
|---|---|
| `WXO_TEST_API_KEY` | IBM IAM API key for test instance |
| `WXO_PROD_API_KEY` | IBM IAM API key for production instance |

#### Variables

| Name | Description |
|---|---|
| `WXO_TEST_URL` | Service URL for test instance (e.g. `https://api.us-south.watson-orchestrate.cloud.ibm.com/instances/abc-123`) |
| `WXO_PROD_URL` | Service URL for production instance |

#### Environments

Create two GitHub environments: **`wxo-test`** and **`wxo-production`**, and attach the corresponding secrets/variables to each.

---

## Security

| Secret | Where to store | **Never do** |
|---|---|---|
| IBM IAM API key | CI/CD secret variables (`WXO_API_KEY`) | Hard-code in scripts |
| `.env` with API keys | Local machine only, listed in `.gitignore` | Push to remote |

The ADK stores session state locally in:
- `~/.config/orchestrate/config.yaml` — environment list
- `~/.cache/orchestrate/credentials.yaml` — cached JWT

**Both are local to your machine and should never be shared or committed.**

---

## License

[MIT](LICENSE)
