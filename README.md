# Agentic Analytics and Business Intelligence Copilot

A safe, human-approved analytics application that converts business questions into SQL, validates the generated query, asks for approval, runs it against PostgreSQL, and presents the results as business insights and charts.

The project uses FastAPI, Streamlit, LangGraph, PostgreSQL, SQLAlchemy, SQLGlot, Plotly, and OpenAI.

Current version: **v0.2.0**

## Project overview

The Agentic BI Copilot allows a user to:

1. Ask a business question in plain English.
2. Review the agent's analysis plan.
3. Inspect the generated SQL.
4. Check which database tables will be used.
5. Review the SQL safety validation.
6. Approve or reject query execution.
7. View the business answer, findings, chart, and underlying data.
8. Reopen previous analyses from history.
9. Retry an earlier analysis.
10. Export completed results as JSON or CSV.

The application accepts free-form business questions. The example questions shown in the interface are suggestions and do not restrict what the user can ask.

## Main features

### Natural-language analytics

Users can enter business questions such as:

- Compare revenue across regions for the last six complete months.
- Show the top products by revenue.
- Compare regional revenue with monthly targets.
- Analyze revenue by customer segment.
- Identify unusual monthly changes.
- Rank products, regions, or categories.

The language model creates a structured analysis plan and generates PostgreSQL SQL based on the available schema and business rules.

### Multi-question support

The project includes a catalog of 12 example analytics questions covering different types of analysis.

These examples help users understand the available dataset, but users can still enter their own questions.

Supported analysis patterns include:

- Time-series analysis
- Rankings
- Regional comparisons
- Product performance
- Customer-segment analysis
- Target comparisons
- Trend analysis
- Grouped comparisons
- Summary tables

### SQL safety validation

Generated SQL must pass several checks before it can be executed.

The validator checks that:

- The input contains one SQL statement.
- The query is a read-only `SELECT` statement.
- Data-changing operations are not present.
- Dangerous functions are not used.
- Only approved schemas and tables are referenced.
- A valid row limit is present.
- The maximum result-row limit is respected.

Queries that fail validation are never shown for approval and are not executed.

### Human approval

Even safe SQL is not executed automatically.

Before execution, the user can inspect:

- The interpreted business question
- The analysis plan
- Assumptions made by the agent
- The SQL explanation
- Referenced tables
- Safety checks
- The complete generated SQL

The user must explicitly choose **Approve and execute** before the database query runs.

If the user rejects the SQL, no query is executed. Optional feedback can be provided with the rejection.

### Read-only database access

Analytics queries run through a dedicated PostgreSQL role named `bi_reader`.

This role has:

- Read-only transactions enabled
- No permission to create or modify tables
- Access only to approved analytics tables
- A five-second statement timeout
- A maximum application result limit

The application also starts every analytics query inside a read-only transaction.

This provides protection at both the application and database levels.

### Grounded result analysis

After a query runs, the result rows are sent to a structured analysis step.

The analysis is grounded in the actual query result and returns:

- A short business answer
- Key findings
- Summary metrics
- A recommended chart type
- Chart column selections
- Follow-up questions

The model is instructed to analyze only the returned data and not invent missing values.

### Automatic visualizations

The application can generate:

- Line charts
- Bar charts
- Grouped bar charts
- Tables

If the requested chart columns are unavailable, the application safely falls back to a table.

The original deterministic regional-revenue chart is also preserved, including unusual-decline markers.

### PostgreSQL-backed workflow persistence

LangGraph workflow checkpoints are stored in PostgreSQL.

This means an analysis waiting for approval can survive:

- API restarts
- Application restarts
- Temporary backend interruptions
- Process termination

A paused workflow can later continue using the same thread ID.

Checkpoint data is stored in the separate `agent_state` schema.

### Isolated persistence account

Workflow state uses a dedicated PostgreSQL account named `bi_agent`.

The `bi_agent` account:

- Owns the `agent_state` schema
- Can store LangGraph checkpoints
- Can store analysis-history records
- Cannot read the retail analytics tables in the `public` schema

This keeps analytics data access separate from workflow-state access.

### Analysis history

The application saves an analysis-history record for each agent run.

History records include:

- Thread ID
- Question
- Current status
- Original thread ID for retries
- Approval information
- Completed result
- Error information
- Creation time
- Last update time

Possible statuses are:

- `awaiting_approval`
- `completed`
- `rejected`
- `failed`

The Streamlit interface allows users to browse and reopen previous runs.

### Retry support

Completed, rejected, or failed runs can be retried.

A retry:

- Creates a new thread
- Reuses the original business question
- Preserves a link to the source thread
- Runs the complete planning and validation workflow again
- Requires human approval again

Runs that are already waiting for approval cannot be retried. They should be reopened and approved or rejected instead.

### Result exports

Completed analyses can be downloaded as:

- JSON
- CSV

The JSON export contains the structured analysis result.

The CSV export contains the underlying query-result rows.

Unfinished, rejected, or failed runs cannot be exported as completed results.

## Application workflow

```text
Business question
       |
       v
Restricted schema discovery
       |
       v
Structured analysis plan
       |
       v
SQL generation
       |
       v
SQL safety validation
       |
       v
Human approval or rejection
       |
       v
Read-only SQL execution
       |
       v
Grounded result analysis
       |
       v
Chart generation
       |
       v
Answer, findings, data, history, and exports
```

## Technology stack

### Backend

- Python 3.11
- FastAPI
- Pydantic
- Uvicorn
- HTTPX

### Agent workflow

- LangGraph
- LangChain OpenAI
- OpenAI structured output
- PostgreSQL LangGraph checkpointer
- LangSmith integration

### Database

- PostgreSQL 16
- SQLAlchemy
- Psycopg
- Psycopg connection pool
- SQLGlot

### User interface

- Streamlit
- Pandas
- Plotly

### Development tools

- uv
- Ruff
- Pytest
- Pytest Coverage
- Docker Compose
- Faker

## Project structure

```text
agentic-bi-copilot/
├── scripts/
│   ├── init_database.sql
│   ├── init_agent_state.sql
│   ├── run_agent_demo.py
│   └── seed_database.py
├── src/
│   └── agentic_bi_copilot/
│       ├── agent/
│       │   ├── graph.py
│       │   ├── nodes.py
│       │   ├── persistence.py
│       │   └── state.py
│       ├── api/
│       │   ├── main.py
│       │   └── routes.py
│       ├── database/
│       │   ├── connection.py
│       │   ├── models.py
│       │   ├── query_service.py
│       │   └── schema_service.py
│       ├── security/
│       │   └── sql_validator.py
│       ├── services/
│       │   ├── analysis.py
│       │   ├── charts.py
│       │   ├── exports.py
│       │   ├── llm.py
│       │   ├── manual_pipeline.py
│       │   ├── question_catalog.py
│       │   └── run_history.py
│       ├── config.py
│       └── schemas.py
├── tests/
│   ├── evaluation/
│   ├── integration/
│   └── unit/
├── ui/
│   └── streamlit_app.py
├── .env.example
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
└── README.md
```

## Synthetic retail dataset

The project includes a deterministic synthetic retail dataset.

The seed script recreates these six tables:

| Table | Purpose | Seeded rows |
|---|---|---:|
| `regions` | Sales regions | 4 |
| `customers` | Customers and business segments | 1,000 |
| `products` | Products, categories, and prices | 100 |
| `orders` | Completed and cancelled orders | 5,125 |
| `order_items` | Products included in orders | 12,752 |
| `monthly_targets` | Monthly revenue targets by region | 96 |

The dataset ends on `2026-07-31`.

Because the seed process is deterministic, the same input data is created every time the database is reseeded.

## Requirements

Install the following before starting:

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop
- An OpenAI API key

## Local setup

### 1. Clone the repository

```bash
git clone https://github.com/jainatishya53-hub/agentic-bi-copilot.git
cd agentic-bi-copilot
```

### 2. Install Python dependencies

```bash
uv sync
```

### 3. Create the environment file

```bash
cp .env.example .env
```

Open `.env` and provide your OpenAI configuration:

```env
OPENAI_API_KEY=your-openai-api-key
MODEL_NAME=your-supported-model-name
```

Do not place a real API key inside `.env.example`.

The `.env` file is ignored by Git and should remain local.

### 4. Start PostgreSQL

Make sure Docker Desktop is running, and then run:

```bash
docker compose up -d postgres
```

Check the database status:

```bash
docker compose ps
```

The PostgreSQL service should report a healthy status.

### 5. Initialize an existing database volume

Docker automatically runs the initialization SQL files when it creates a new PostgreSQL volume.

If your database volume existed before PostgreSQL persistence was added, run:

```bash
docker compose exec -T postgres \
  psql -U bi_admin -d bi_copilot \
  < scripts/init_agent_state.sql
```

This creates:

- The `bi_agent` role
- The `agent_state` schema
- The permissions required for workflow persistence

Running this script again is safe because it is designed to support existing local environments.

### 6. Seed the retail dataset

```bash
uv run python scripts/seed_database.py
```

Expected output:

```text
Recreating the six synthetic retail tables...
Seed completed successfully:
  regions: 4
  customers: 1000
  products: 100
  orders: 5125
  order_items: 12752
  monthly_targets: 96
```

## Running the application

The application uses three local processes.

### Terminal 1: PostgreSQL

```bash
docker compose up -d postgres
```

### Terminal 2: FastAPI backend

```bash
uv run uvicorn agentic_bi_copilot.api.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --reload
```

The API is available at:

```text
http://127.0.0.1:8000
```

Interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

### Terminal 3: Streamlit interface

```bash
uv run streamlit run ui/streamlit_app.py
```

The user interface is normally available at:

```text
http://localhost:8501
```

## Using the application

### Start a new analysis

1. Open the Streamlit application.
2. Choose an example question or enter your own question.
3. Select the button to begin the analysis.
4. Wait for the planning and SQL-generation steps.

### Review generated SQL

Before execution, review:

- The analysis plan
- Assumptions
- Referenced tables
- SQL explanation
- Safety validation
- Generated SQL

### Approve or reject

Choose **Approve and execute** to run the query.

Choose **Reject SQL** to stop execution. Rejected SQL is not run against the database.

### Review results

After approval, the interface shows:

- Business answer
- Summary metrics
- Key findings
- Recommended follow-up questions
- Chart or table
- Underlying query result
- Audit information
- Execution time

### Use run history

Open the **Run history** tab to:

- View recent analyses
- Reopen a paused approval
- Review a completed analysis
- View rejected or failed runs
- Retry a finished analysis
- Download completed results

## API endpoints

The main API endpoints are:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Check backend health |
| `POST` | `/api/v1/agent/runs` | Start a new agent analysis |
| `POST` | `/api/v1/agent/runs/{thread_id}/decision` | Approve or reject generated SQL |
| `GET` | `/api/v1/agent/runs/history` | List saved analysis runs |
| `GET` | `/api/v1/agent/runs/{thread_id}` | Get one saved run |
| `POST` | `/api/v1/agent/runs/{thread_id}/retry` | Retry a finished run |
| `GET` | `/api/v1/agent/runs/{thread_id}/export?format=json` | Export a result as JSON |
| `GET` | `/api/v1/agent/runs/{thread_id}/export?format=csv` | Export query rows as CSV |

Full request and response schemas can be viewed through the FastAPI documentation at `/docs`.

## Command-line agent demo

The interactive agent workflow can also be tested without Streamlit:

```bash
uv run python scripts/run_agent_demo.py
```

The script will:

1. Start the workflow.
2. Display the generated SQL.
3. Display the safety-validation result.
4. Ask for approval.
5. Execute the query only after approval.
6. Print the business answer and unusual findings.

Type exactly:

```text
APPROVE
```

to allow execution.

## Environment variables

Important settings include:

| Variable | Purpose |
|---|---|
| `APP_ENV` | Application environment |
| `DATABASE_URL` | Read-only analytics database connection |
| `DATABASE_ADMIN_URL` | Administrative connection used for database setup and seeding |
| `CHECKPOINT_DATABASE_URL` | PostgreSQL connection used for workflow checkpoints and run history |
| `CHECKPOINT_POOL_MIN_SIZE` | Minimum persistence connection-pool size |
| `CHECKPOINT_POOL_MAX_SIZE` | Maximum persistence connection-pool size |
| `API_BASE_URL` | FastAPI URL used by Streamlit |
| `OPENAI_API_KEY` | OpenAI API key |
| `MODEL_NAME` | Model used for planning, SQL generation, and result analysis |
| `LANGSMITH_TRACING` | Enables or disables LangSmith tracing |
| `LANGSMITH_API_KEY` | Optional LangSmith API key |
| `LANGSMITH_PROJECT` | LangSmith project name |
| `MAX_RESULT_ROWS` | Maximum rows returned by an analytics query |
| `SQL_STATEMENT_TIMEOUT_MS` | SQL execution timeout |
| `DATA_AS_OF_DATE` | Last date available in the sample dataset |

The passwords included in `.env.example` are local development values only. Use strong secrets in any deployed environment.

## Database roles

### `bi_admin`

Used for:

- Database initialization
- Table creation
- Dataset seeding
- Local administration

The running analytics application should not use this account for user-generated queries.

### `bi_reader`

Used for:

- Validated analytics queries
- Read-only access to approved retail tables

This account cannot modify the database.

### `bi_agent`

Used for:

- LangGraph checkpoints
- Analysis history
- Retry relationships
- Stored approval and result information

This account is restricted to the `agent_state` schema and cannot read the retail tables.

## Testing

Make sure PostgreSQL is running before executing the complete test suite:

```bash
docker compose up -d postgres
```

Run lint checks:

```bash
uv run ruff check .
```

Run all tests:

```bash
uv run pytest -q
```

At version `v0.2.0`, the complete suite contains **110 passing tests**.

Run a specific test file:

```bash
uv run pytest tests/unit/test_sql_validator.py -v
```

Run the persistence integration test:

```bash
uv run pytest \
  tests/integration/test_postgres_persistence.py \
  -v
```

Run the history integration tests:

```bash
uv run pytest \
  tests/integration/test_run_history.py \
  -v
```

The test suite covers:

- Health endpoint
- Database connection
- Read-only database enforcement
- Query execution
- Result limits
- SQL validation
- Schema discovery
- Deterministic analysis
- Generic result analysis
- Chart generation
- LangGraph nodes and routing
- Human approval and rejection
- Agent API endpoints
- PostgreSQL checkpoint persistence
- Analysis history
- Retry behavior
- JSON and CSV exports
- Pydantic response schemas

## Code formatting

Format the code with:

```bash
uv run ruff format .
```

Check code quality with:

```bash
uv run ruff check .
```

Check for whitespace problems with:

```bash
git diff --check
```

## Useful Docker commands

Start PostgreSQL:

```bash
docker compose up -d postgres
```

View service status:

```bash
docker compose ps
```

View PostgreSQL logs:

```bash
docker compose logs postgres
```

Stop the containers:

```bash
docker compose down
```

Do not add the `-v` option unless you intentionally want to remove the PostgreSQL volume and its stored data.

## Security design

The project uses several layers of protection:

1. The model receives a restricted database schema.
2. SQL is parsed before execution.
3. Only one read-only query is allowed.
4. Tables and schemas are allow-listed.
5. Dangerous operations and functions are rejected.
6. A result limit is required.
7. A database statement timeout is applied.
8. A human must approve the SQL.
9. Queries run through a read-only database account.
10. Workflow persistence uses a separate restricted account.
11. Secrets remain in the ignored `.env` file.

These protections reduce risk, but generated SQL should still be carefully reviewed before approval.

## Current limitations

This is a portfolio and development project, not a production-ready analytics platform.

Current limitations include:

- It uses a synthetic retail dataset.
- It requires an OpenAI API key.
- SQL quality depends partly on the selected model.
- Human approval is required for every generated query.
- Authentication and user accounts are not implemented.
- Run history is not separated by individual user.
- Deployment configuration is not included.
- Database passwords in the example configuration are intended only for local development.
- Large-scale performance and concurrency have not been tested.

## Version history

### v0.2.0

- Added PostgreSQL-backed LangGraph checkpoints.
- Added restart-safe approval workflows.
- Added an isolated `bi_agent` persistence account.
- Added saved analysis history.
- Added reopening of paused and completed runs.
- Added retry support.
- Added JSON and CSV exports.
- Added history, retry, and export controls to Streamlit.
- Expanded the automated test suite to 110 tests.

### v0.1.0

- Added deterministic retail data.
- Added safe read-only SQL execution.
- Added SQL validation.
- Added human approval.
- Added the LangGraph workflow.
- Added business analysis and charts.
- Added FastAPI and Streamlit interfaces.

## Future improvements

Possible future improvements include:

- GitHub Actions for automated testing
- A deployed live demonstration
- User authentication
- User-specific history
- More evaluation questions and expected results
- Automated SQL-quality scoring
- Query-cost estimation
- Additional chart types
- PDF and Excel exports
- Production secret management
- Cloud-hosted PostgreSQL
- Monitoring and rate limiting

## Author

**Atishya Jain**

GitHub: [jainatishya53-hub](https://github.com/jainatishya53-hub)

## Release

The latest completed release is:

```text
v0.2.0
```

It includes persistent agent workflows, analysis history, retries, and result exports.