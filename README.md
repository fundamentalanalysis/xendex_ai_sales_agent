# AI Sales Agent - Xendex AI

Production-ready multi-agent sales outreach system with research, strategy, drafting, approval, and sequenced campaign execution. Powered by intelligent LinkedIn scraping, AI-driven lead analysis, and automated email personalization.

## 🚀 Features

- **Multi-Agent Research System**: Parallel execution of LinkedIn, Google Research, Website Analysis, and Lead Intelligence agents
- **LinkedIn Intelligence**: Automated profile scraping with SerpAPI fallback and Playwright browser automation
- **Lead Scoring**: Composite scoring based on fit, readiness, and intent signals
- **Email Draft Generation**: AI-powered personalized cold emails with multiple subject line options
- **Draft Approval Workflow**: Review, edit, and approve emails before sending
- **Rich Text Email Editor**: ReactQuill-based editor with font options and formatting
- **Campaign Management**: Multi-touch email sequences with scheduling
- **Analytics Dashboard**: Track lead performance and email metrics

## 🛠 Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python 3.11+ / FastAPI |
| **Frontend** | React 18 + TypeScript + Vite |
| **LLM** | Azure OpenAI GPT-4.1 |
| **Email** | Resend API |
| **Database** | PostgreSQL 15+ (AsyncPG) |
| **Queue** | Redis + Celery |
| **LinkedIn Scraping** | SerpAPI + Playwright (Authenticated) |
| **Web Scraping** | BeautifulSoup + HTTPX |

## 📋 Prerequisites

- **Python**: 3.9+ (3.11 recommended)
- **Node.js**: v18+
- **Docker**: For PostgreSQL & Redis
- **Redis**: Running locally or via Docker
- **Playwright**: Browser binaries installed

## 🔧 Environment Variables

Create `.env` file in both root and `backend/` directories:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_sales_agent

# Redis
REDIS_URL=redis://localhost:6379/0

# Azure OpenAI (Required)
AZURE_OPENAI_ENDPOINT=https://your-endpoint.cognitiveservices.azure.com/
AZURE_AI_API_KEY=your-azure-api-key
AZURE_OPENAI_DEPLOYMENT=gpt-4.1
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Resend Email (Required)
RESEND_API_KEY=re_your_api_key
RESEND_FROM_EMAIL=onboarding@resend.dev
RESEND_FROM_NAME=Xendex AI

# LinkedIn Scraping
SERPAPI_API_KEY=your_serpapi_key
PHANTOMBUSTER_LI_AT=your_linkedin_cookie
```

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```powershell
# Start all services (PostgreSQL, Redis, Backend, Frontend, Celery)
docker-compose up --build
```

Access:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Option 2: Local Development

#### 1. Start Database & Redis
```powershell
# PostgreSQL
docker run -d --name sales_agent_db `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=ai_sales_agent `
  -p 5432:5432 `
  postgres:15-alpine

# Redis
docker run -d --name sales_agent_redis -p 6379:6379 redis:7-alpine
```

#### 2. Setup Backend (Terminal 1)
```powershell
cd backend

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers (required for LinkedIn scraping)
python -m playwright install chromium

# Run database migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload
```
API running at: http://localhost:8000

#### 3. Start Celery Worker (Terminal 2)
```powershell
cd backend
.\.venv\Scripts\Activate

# Start Celery worker for background tasks
celery -A app.workers.celery_app worker --loglevel=info -P solo
```

#### 4. Setup Frontend (Terminal 3)
```powershell
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```
Dashboard running at: http://localhost:3000

## 📂 Project Structure

```
AI_Sales_Agent/
├── backend/
│   ├── app/
│   │   ├── agents/           # AI Research Agents
│   │   │   ├── linkedin_agent.py      # LinkedIn profile analysis
│   │   │   ├── google_research.py     # Google search for triggers
│   │   │   ├── lead_intelligence.py   # Company intelligence
│   │   │   ├── website_analyzer.py    # Website content analysis
│   │   │   ├── intent_scorer.py       # Lead scoring engine
│   │   │   └── risk_filter.py         # Spam/risk filtering
│   │   ├── api/
│   │   │   └── routes/       # REST API endpoints
│   │   │       ├── leads.py           # Lead CRUD + research
│   │   │       ├── drafts.py          # Email draft management
│   │   │       ├── campaigns.py       # Campaign orchestration
│   │   │       └── analytics.py       # Dashboard metrics
│   │   ├── engine/           # Core Business Logic
│   │   │   ├── draft_generator.py     # AI email generation
│   │   │   ├── strategy.py            # Outreach strategy
│   │   │   ├── normalizer.py          # Data normalization
│   │   │   └── personalization.py     # Personalization control
│   │   ├── integrations/     # External Services
│   │   │   ├── openai_client.py       # Azure OpenAI client
│   │   │   ├── sendgrid.py            # Resend email client
│   │   │   ├── linkedin_scraper.py    # Playwright LinkedIn scraper
│   │   │   └── scraper.py             # General web scraper
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   └── workers/          # Celery background tasks
│   │       ├── celery_app.py          # Celery configuration
│   │       ├── research_tasks.py      # Research pipeline task
│   │       └── send_tasks.py          # Email sending task
│   ├── alembic/              # Database migrations
│   └── pyproject.toml        # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── pages/            # React pages
│   │   │   ├── Dashboard.tsx          # Overview dashboard
│   │   │   ├── Leads.tsx              # Lead management
│   │   │   ├── Drafts.tsx             # Email draft approval
│   │   │   └── Campaigns.tsx          # Campaign management
│   │   ├── components/       # Reusable components
│   │   └── lib/
│   │       └── api.ts                 # API client
│   └── package.json
├── docker-compose.yml        # Docker orchestration
├── .env                      # Environment variables
└── README.md                 # This file
```

## 🔄 Workflow

1. **Add Leads**: Import leads via CSV or manual entry
2. **Run Research**: Triggers multi-agent research pipeline
   - LinkedIn profile analysis
   - Google trigger search (funding, hiring, etc.)
   - Website intelligence gathering
3. **Review Intelligence**: View lead scores, LinkedIn insights, and sales triggers
4. **Generate Drafts**: AI creates personalized email drafts
5. **Approve & Send**: Review, edit, and approve emails for sending

## 📧 Email Template System

The system generates personalized emails using:
- **Trigger-based hooks**: References recent news, funding, hiring
- **Role-specific messaging**: Tailored for managers, executives, founders
- **LinkedIn insights**: Topics, initiatives, and career context
- **Multiple subject lines**: Varied approaches for A/B testing

## 🔧 Troubleshooting

### Celery Worker Issues
```powershell
# Restart Celery worker to pick up code changes
# Stop with Ctrl+C, then:
celery -A app.workers.celery_app worker --loglevel=info -P solo
```

### Playwright Not Working
```powershell
# Install browser binaries
cd backend
.\.venv\Scripts\Activate
python -m playwright install chromium
```

### Database Connection Error
```powershell
# Check PostgreSQL is running
docker ps

# Restart if needed
docker start sales_agent_db
```

## 📝 API Documentation

Once the backend is running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📄 License

MIT License - See LICENSE file for details.

## 🙏 Acknowledgments

- Azure OpenAI for LLM capabilities
- Resend for email delivery
- SerpAPI for LinkedIn data
- Playwright for browser automation
