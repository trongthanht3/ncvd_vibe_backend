# Hakathon Backend

FastAPI backend với kiến trúc 3 lớp, tích hợp Keycloak OAuth2, PostgreSQL, và Milvus vector database.

## Kiến trúc

- **Presentation Layer** (`src/api/`): FastAPI routers, schemas, dependencies
- **Application Layer** (`src/application/`): Business logic, services, authentication
- **Data Layer** (`src/data/`): ORM models, repositories, migrations

## Tech Stack

- **Framework**: FastAPI + Uvicorn
- **Authentication**: Keycloak OAuth2/OIDC (Docker)
- **Database**: PostgreSQL + SQLAlchemy 2.x (async)
- **Vector DB**: Milvus Standalone
- **Testing**: pytest + httpx
- **Code Quality**: ruff + black + mypy + pre-commit

## Cấu trúc thư mục

```
src/
├── api/               # Presentation layer
│   ├── routers/       # FastAPI route handlers
│   ├── deps/          # Dependency injection
│   └── schemas/       # Pydantic models
├── application/       # Application layer
│   ├── services/      # Business logic
│   ├── auth/          # Authentication logic
│   └── use_cases/     # Use case implementations
├── data/              # Data layer
│   ├── models/        # SQLAlchemy models
│   ├── repositories/  # Data access repositories
│   └── migrations/    # Alembic migrations
├── integrations/      # External integrations
│   ├── keycloak/      # Keycloak OIDC client
│   └── milvus/        # Milvus vector client
└── core/              # Core utilities
    ├── config.py      # Settings configuration
    ├── logging.py     # Structured logging
    ├── security.py    # Security utilities
    ├── cors.py        # CORS configuration
    └── errors.py      # Error handling
```

## Cài đặt

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git

### Setup Development Environment

1. **Clone repository**

   ```bash
   git clone <repository-url>
   cd hakathon/backend
   ```

2. **Install dependencies**

   ```bash
   # Windows PowerShell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -e ".[dev]"

   # Linux/macOS
   python -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   ```

3. **Setup pre-commit hooks**

   ```bash
   pre-commit install
   ```

4. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env với các giá trị phù hợp
   ```

5. **Start infrastructure services**

   ```bash
   # Windows PowerShell
   .\scripts\dev-up.ps1

   # Linux/macOS
   ./scripts/dev-up.sh
   ```

6. **Run migrations**

   ```bash
   # Windows PowerShell
   .\scripts\migrate.ps1

   # Linux/macOS
   ./scripts/migrate.sh
   ```

7. **Start development server**
   ```bash
   uvicorn src.main:app --reload --port 8000
   ```

## Development Commands

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Format code
black src tests
ruff check src tests --fix

# Type checking
mypy src

# Lint
ruff check src tests
```

## Docker Services

- **PostgreSQL**: `localhost:5432`
- **Keycloak**: `localhost:8070`
- **Milvus**: `localhost:19530`
- **FastAPI**: `localhost:8000`

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Security Features

- ✅ OAuth2/OIDC authentication via Keycloak
- ✅ JWT token validation with JWKS
- ✅ Role-based access control (RBAC)
- ✅ IDOR protection at application layer
- ✅ SQL injection prevention via ORM
- ✅ CORS configuration
- ✅ Structured logging with correlation IDs
- ✅ Input validation via Pydantic

## Testing

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit

# Run integration tests only
pytest tests/integration

# Run with coverage
pytest --cov=src --cov-report=html
```

## Contributing

1. Follow worker criteria từ plan.md
2. Mọi function phải có docstring đầy đủ
3. Chạy pre-commit hooks trước khi commit
4. Viết tests cho code mới
5. Self-review theo checklist trong plan.md
