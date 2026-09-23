# Development Environment Setup

This guide covers setting up your local development environment for the AI-Native DevOps & SRE Platform.

## Prerequisites

### Required Software

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| Python | 3.11 | Services and agents |
| Node.js | 20.19 | Frontend and tooling |
| Docker | 24.0 | Local infrastructure |
| Docker Compose | 2.20 | Service orchestration |
| Git | 2.40 | Version control |

### Optional Tools

- **uv** (recommended): Fast Python package installer
- **make**: Task automation (not available by default on Windows)
- **kubectl**: Kubernetes manifest testing
- **terraform**: Infrastructure validation

## Installation Steps

### 1. Clone Repository

```bash
git clone https://github.com/Kaoserahamed/AI-Native-DevOps-SRE-Platform.git
cd AI-Native-DevOps-SRE-Platform
```

### 2. Install Python Dependencies

**Using uv (recommended):**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh  # Linux/macOS
# OR
pip install uv  # Windows

# Install dependencies
uv sync --frozen --all-extras

# Install pre-commit hooks
uv run pre-commit install
```

**Using pip:**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# OR
.venv\Scripts\activate  # Windows

pip install -r requirements.txt
pre-commit install
```

### 3. Install Node.js Dependencies

```bash
npm ci
```

This installs:
- Repository tooling (ESLint, Prettier)
- Demo frontend dependencies

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and configure:

**Required for local development:**
```bash
DATABASE_URL=postgresql://devops_user:devops_password@localhost:5432/devops_db
REDIS_URL=redis://localhost:6379/0
OTEL_ENDPOINT=http://localhost:4317
LOG_LEVEL=DEBUG
```

**Optional (for AI features):**
```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
```

See [.env.example](../../.env.example) for all available options.

### 5. Start Local Infrastructure

```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- OpenTelemetry Collector (ports 4317, 4318)
- Prometheus (port 9090)
- Grafana (port 3000)
- Loki (port 3100)
- Tempo (port 3200)

**Verify services are running:**
```bash
docker-compose ps
```

### 6. Initialize Database

```bash
# Run migrations
python scripts/run_migrations.py

# Verify schema
docker-compose exec postgres psql -U devops_user -d devops_db -c "\dt"
```

## Running the Application

### Backend API

```bash
cd apps/demo-app/backend
uvicorn app.main:app --reload --port 8000
```

Access at: http://localhost:8000
API docs: http://localhost:8000/docs

### Frontend

```bash
cd apps/demo-app/frontend
npm run dev
```

Access at: http://localhost:3000

### Services

Each service can be run independently:

```bash
# Incident API
cd services/incident_api
uvicorn app:create_app --factory --reload --port 8001

# Approval API
cd services/approval_api
uvicorn app:create_app --factory --reload --port 8002
```

## Verification

### Run Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires Docker services)
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_anomaly_detector.py -v

# With coverage
pytest tests/unit/ --cov=services --cov=packages --cov-report=html
```

### Linting and Formatting

```bash
# Format code
ruff format .

# Check linting
ruff check .

# Type checking
mypy services packages --strict --ignore-missing-imports

# Pre-commit hooks (runs all checks)
pre-commit run --all-files
```

### Build Verification

```bash
# Build containers
docker-compose build demo-api demo-web

# Verify builds
docker images | grep devops
```

## IDE Setup

### VS Code

Recommended extensions:
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "charliermarsh.ruff",
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "redhat.vscode-yaml",
    "ms-azuretools.vscode-docker"
  ]
}
```

Settings (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "ruff",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  }
}
```

### PyCharm

1. File → Settings → Project → Python Interpreter
2. Add interpreter → Existing environment
3. Select `.venv/bin/python`
4. Enable: Settings → Tools → Python Integrated Tools → pytest

## Troubleshooting

### Docker Services Won't Start

```bash
# Check logs
docker-compose logs postgres
docker-compose logs redis

# Restart services
docker-compose down
docker-compose up -d
```

### Database Connection Errors

```bash
# Verify PostgreSQL is running
docker-compose exec postgres pg_isready

# Check connection
docker-compose exec postgres psql -U devops_user -d devops_db
```

### Port Already in Use

```bash
# Find process using port
lsof -i :8000  # Linux/macOS
netstat -ano | findstr :8000  # Windows

# Change port in .env or command line
uvicorn app.main:app --port 8001
```

### Import Errors

```bash
# Reinstall dependencies
uv sync --frozen --all-extras

# Verify installation
uv pip list
```

### Pre-commit Hook Failures

```bash
# Update hooks
pre-commit autoupdate

# Skip hooks temporarily (not recommended)
git commit --no-verify
```

## Development Workflow

1. **Create feature branch:**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes and test:**
   ```bash
   pytest tests/unit/ -v
   ruff format .
   mypy services packages
   ```

3. **Commit with hooks:**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

4. **Push and create PR:**
   ```bash
   git push origin feature/my-feature
   ```

See [18-governance.md](../18-governance.md) for detailed branching strategy.

## Next Steps

- [Testing Guide](../15-testing-strategy.md) - Writing and running tests
- [Git Workflow](../18-governance.md) - Branching and PR process
- [API Documentation](../01-architecture.md) - Using the APIs
- [Architecture](../architecture/system-architecture.md) - Understanding the system

## Getting Help

- **Issues**: Check existing GitHub issues
- **Discussions**: GitHub Discussions for questions
- **Contributing**: See [CONTRIBUTING.md](../../CONTRIBUTING.md)
- **Security**: See [SECURITY.md](../../SECURITY.md)
