# Invoice Processing Agent with HITL - LangGraph Implementation

A production-ready **LangGraph-based Invoice Processing Workflow** with **Human-In-The-Loop (HITL)** checkpoints, **Bigtool** dynamic tool selection, and **MCP client** orchestration.

## 🎯 Overview

This implementation demonstrates a sophisticated invoice processing system that:

- ✅ **12-Stage Deterministic & Non-Deterministic Workflow** using LangGraph
- ✅ **Stateful Execution** with persistent state across all stages
- ✅ **HITL Checkpoint System** - pause workflow for human review when matching fails
- ✅ **Pydantic Schema Validation** for all data models
- ✅ **Gemini 2.5 Flash LLM** for intelligent extraction and matching
- ✅ **Bigtool Dynamic Tool Selection** from configurable pools
- ✅ **MCP Client Integration** for COMMON/ATLAS server routing
- ✅ **FastAPI REST API** with human review endpoints
- ✅ **SQLite/Postgres Checkpoint Persistence** for resumable workflows

## 📋 Architecture

### Workflow Stages

```
INTAKE (Validate)
    ↓
UNDERSTAND (OCR & Parse)
    ↓
PREPARE (Normalize & Enrich)
    ↓
RETRIEVE (Fetch PO/GRN)
    ↓
MATCH_TWO_WAY (Compute Score)
    ↓
[CONDITIONAL] Match Failed?
    ├─ YES → CHECKPOINT_HITL → HITL_DECISION → [Human Review]
    │                              ↓
    │                         ACCEPT/REJECT
    │                              ↓
    └─ NO → RECONCILE
    ↓
RECONCILE (Accounting Entries)
    ↓
APPROVE (Apply Policies)
    ↓
POSTING (Post to ERP)
    ↓
NOTIFY (Send Notifications)
    ↓
COMPLETE (Final Payload)
```

### Key Components

| Component | Purpose |
|-----------|---------|
| **schemas.py** | Pydantic models for all data validation |
| **config.py** | Configuration management with environment variables |
| **database.py** | SQLAlchemy models and checkpoint persistence |
| **llm_utils.py** | Gemini 2.5 Flash LLM integration |
| **bigtool.py** | Dynamic tool selection and MCP client routing |
| **workflow.py** | LangGraph workflow definition with all 12 nodes |
| **main.py** | FastAPI application with REST endpoints |
| **demo.py** | End-to-end demo script |

## 🚀 Quick Start

### 1. Installation

```bash
# Clone/navigate to project
cd windsurd_proj

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Edit `.env` file with your settings:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=sqlite:///./invoice_processing.db
MATCH_THRESHOLD=0.90
AUTO_APPROVE_THRESHOLD=10000.0
```

### 3. Run Demo

```bash
python demo.py
```

This will:
- Create a sample invoice
- Execute all 12 workflow stages
- Display execution logs and tool selections
- Show final payload and audit trail

### 4. Start API Server

```bash
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Access:
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Configuration**: http://localhost:8000/config

## 📡 API Endpoints

### Process Invoice

```bash
POST /process-invoice
Content-Type: application/json

{
  "invoice_id": "INV-2024-12-001",
  "vendor_name": "Acme Corp",
  "vendor_tax_id": "TAX-123456789",
  "invoice_date": "2024-12-07",
  "due_date": "2024-12-22",
  "amount": 5000.00,
  "currency": "USD",
  "line_items": [
    {
      "desc": "Software License",
      "qty": 1,
      "unit_price": 2000.00,
      "total": 2000.00
    }
  ],
  "attachments": ["invoice.pdf"]
}
```

**Response (Match Succeeds):**
```json
{
  "status": "COMPLETED",
  "workflow_id": "uuid",
  "final_payload": { ... },
  "audit_log": [ ... ],
  "tool_selections": { ... }
}
```

**Response (Match Fails - HITL):**
```json
{
  "status": "PAUSED_FOR_REVIEW",
  "checkpoint_id": "uuid",
  "review_url": "http://localhost:8000/human-review/uuid",
  "reason": "Match score 0.65 below threshold 0.90",
  "workflow_id": "uuid"
}
```

### List Pending Reviews

```bash
GET /human-review/pending
```

**Response:**
```json
{
  "items": [
    {
      "checkpoint_id": "uuid",
      "invoice_id": "INV-2024-12-001",
      "vendor_name": "Acme Corp",
      "amount": 5000.00,
      "created_at": "2024-12-07T10:30:00",
      "reason_for_hold": "Match score 0.65 below threshold 0.90",
      "review_url": "http://localhost:8000/human-review/uuid"
    }
  ]
}
```

### Get Review Details

```bash
GET /human-review/{checkpoint_id}
```

Returns full checkpoint state blob for human review.

### Submit Human Decision

```bash
POST /human-review/decision
Content-Type: application/json

{
  "checkpoint_id": "uuid",
  "decision": "ACCEPT",
  "notes": "Verified with vendor",
  "reviewer_id": "john_doe"
}
```

**Response:**
```json
{
  "resume_token": "token-uuid",
  "next_stage": "RECONCILE"
}
```

## 🧩 Bigtool Tool Selection

The system uses **Bigtool** to dynamically select tools from configurable pools:

### OCR Tools
- `google_vision` - Google Cloud Vision API
- `tesseract` - Open-source OCR
- `aws_textract` - AWS Textract

### Enrichment Tools
- `clearbit` - Clearbit API
- `people_data_labs` - PDL API
- `vendor_db` - Internal vendor database

### ERP Tools
- `sap_sandbox` - SAP sandbox environment
- `netsuite` - NetSuite ERP
- `mock_erp` - Mock ERP for testing

### Database Tools
- `postgres` - PostgreSQL
- `sqlite` - SQLite
- `dynamodb` - AWS DynamoDB

### Email Tools
- `sendgrid` - SendGrid API
- `smartlead` - SmartLead API
- `ses` - AWS SES

## 🤖 LLM Integration (Gemini 2.5 Flash)

The workflow uses **Gemini 2.5 Flash** for:

1. **Invoice Text Extraction** - Extract structured data from OCR text
2. **Vendor Name Normalization** - Standardize vendor names
3. **Match Score Computation** - Compare invoice vs PO intelligently
4. **Accounting Entry Generation** - Create GL entries automatically

## 💾 Checkpoint Persistence

### Database Schema

**checkpoints table:**
```sql
CREATE TABLE checkpoints (
  checkpoint_id VARCHAR PRIMARY KEY,
  workflow_id VARCHAR,
  invoice_id VARCHAR,
  vendor_name VARCHAR,
  amount FLOAT,
  currency VARCHAR,
  state_blob JSON,
  created_at DATETIME,
  reason_for_hold VARCHAR,
  review_url VARCHAR,
  status VARCHAR,
  reviewer_id VARCHAR,
  decision VARCHAR,
  decision_notes VARCHAR,
  decided_at DATETIME
);
```

**human_review_queue table:**
```sql
CREATE TABLE human_review_queue (
  id VARCHAR PRIMARY KEY,
  checkpoint_id VARCHAR,
  invoice_id VARCHAR,
  vendor_name VARCHAR,
  amount FLOAT,
  currency VARCHAR,
  created_at DATETIME,
  reason_for_hold VARCHAR,
  review_url VARCHAR,
  status VARCHAR
);
```

**audit_logs table:**
```sql
CREATE TABLE audit_logs (
  id VARCHAR PRIMARY KEY,
  workflow_id VARCHAR,
  invoice_id VARCHAR,
  timestamp DATETIME,
  stage VARCHAR,
  action VARCHAR,
  details JSON
);
```

## 📊 Execution Log Example

```
[INTAKE] invoice_validated
  Time: 2024-12-07T10:30:00.123456
  Details: {"raw_id": "uuid", "invoice_id": "INV-2024-12-001"}

[UNDERSTAND] invoice_parsed
  Time: 2024-12-07T10:30:01.234567
  Details: {"line_items_count": 2, "ocr_tool": "tesseract"}

[PREPARE] vendor_enriched
  Time: 2024-12-07T10:30:02.345678
  Details: {"normalized_name": "Acme Corporation", "enrichment_tool": "vendor_db"}

[RETRIEVE] po_grn_fetched
  Time: 2024-12-07T10:30:03.456789
  Details: {"pos_count": 1, "grns_count": 1, "erp_tool": "mock_erp"}

[MATCH_TWO_WAY] match_computed
  Time: 2024-12-07T10:30:04.567890
  Details: {"match_score": 0.95, "match_result": "MATCHED"}

[RECONCILE] entries_created
  Time: 2024-12-07T10:30:05.678901
  Details: {"entries_count": 2, "balanced": true}

[APPROVE] approval_determined
  Time: 2024-12-07T10:30:06.789012
  Details: {"approval_status": "AUTO_APPROVED", "amount": 5000.0}

[POSTING] posted_to_erp
  Time: 2024-12-07T10:30:07.890123
  Details: {"erp_txn_id": "TXN-20241207103007-abc123", "payment_id": "PAY-def456"}

[NOTIFY] notifications_sent
  Time: 2024-12-07T10:30:08.901234
  Details: {"parties": ["Acme Corporation", "finance_team@company.com"], "email_tool": "sendgrid"}

[COMPLETE] workflow_completed
  Time: 2024-12-07T10:30:09.012345
  Details: {"invoice_id": "INV-2024-12-001", "db_tool": "sqlite"}
```

## 🔄 HITL Workflow Example

### Scenario: Match Fails

1. **Invoice Processing**
   ```
   POST /process-invoice
   → Match Score: 0.65 (below 0.90 threshold)
   → Checkpoint Created
   → Workflow Paused
   ```

2. **Human Review**
   ```
   GET /human-review/pending
   → Returns checkpoint for review
   
   GET /human-review/{checkpoint_id}
   → Returns full state for inspection
   ```

3. **Human Decision**
   ```
   POST /human-review/decision
   {
     "checkpoint_id": "uuid",
     "decision": "ACCEPT",
     "notes": "Verified with vendor - discrepancy explained",
     "reviewer_id": "john_doe"
   }
   → Workflow Resumes at RECONCILE
   ```

4. **Completion**
   ```
   RECONCILE → APPROVE → POSTING → NOTIFY → COMPLETE
   → Final Payload Generated
   ```

## 🧪 Testing

### Run Demo Script
```bash
python demo.py
```

### Run with Sample Invoice
```python
from src.schemas import InvoicePayload, LineItem
from src.workflow import create_workflow_state, invoice_processing_workflow

invoice = InvoicePayload(
    invoice_id="INV-2024-12-001",
    vendor_name="Acme Corp",
    vendor_tax_id="TAX-123456789",
    invoice_date="2024-12-07",
    due_date="2024-12-22",
    amount=5000.00,
    currency="USD",
    line_items=[
        LineItem(desc="Software", qty=1, unit_price=5000.00, total=5000.00)
    ],
)

state = create_workflow_state(invoice)
final_state = invoice_processing_workflow.invoke(state)
print(final_state.complete_output)
```

## 📝 Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `MATCH_THRESHOLD` | 0.90 | Minimum match score to pass 2-way matching |
| `TWO_WAY_TOLERANCE_PCT` | 5.0 | Tolerance percentage for amount matching |
| `AUTO_APPROVE_THRESHOLD` | 10000.0 | Amount below which invoices auto-approve |
| `GEMINI_MODEL` | gemini-2.5-flash | LLM model to use |
| `DATABASE_URL` | sqlite:///./invoice_processing.db | Database connection string |

## 🔐 Security Notes

- Store `GEMINI_API_KEY` in environment variables, never in code
- Use HTTPS in production for all API endpoints
- Implement authentication/authorization for human review endpoints
- Encrypt sensitive data in checkpoint state blobs
- Audit all human decisions and modifications

## 📦 Project Structure

```
windsurd_proj/
├── src/
│   ├── __init__.py
│   ├── schemas.py          # Pydantic models
│   ├── config.py           # Configuration
│   ├── database.py         # Database models & persistence
│   ├── llm_utils.py        # Gemini LLM integration
│   ├── bigtool.py          # Tool selection & MCP clients
│   ├── workflow.py         # LangGraph workflow (12 nodes)
│   └── main.py             # FastAPI application
├── .env                    # Environment variables
├── requirements.txt        # Python dependencies
├── demo.py                 # Demo script
└── README.md              # This file
```

## 🚀 Production Deployment

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Setup

```bash
# Production .env
GEMINI_API_KEY=prod_key_here
DATABASE_URL=postgresql://user:pass@prod-db:5432/invoices
API_DEBUG=False
MATCH_THRESHOLD=0.95
AUTO_APPROVE_THRESHOLD=5000.0
```
---

**Built with LangGraph, Pydantic, Gemini 2.5 Flash, and FastAPI**
