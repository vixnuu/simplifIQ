# SimplifIQ — AI Lead Automation System

🔗 **Live Demo:** https://simplifiq-nrm8.onrender.com  
🔗 **GitHub:** https://github.com/vixnuu/simplifIQ

---

## What It Does

When a prospect submits the lead form, the system automatically:
- ✅ Captures and validates their information
- ✅ Enriches company data using Groq AI (LLaMA 3.3 70B)
- ✅ Generates a personalised PDF audit report
- ✅ Sends the report to the prospect via email
- ✅ All without any human intervention

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django + Django REST Framework |
| AI Enrichment | Groq API (LLaMA 3.3 70B) |
| PDF Generation | ReportLab |
| Email Delivery | SendGrid |
| Database | SQLite |
| Deployment | Render |

---

## Project Structure

simplifiq/
├── core/                  # Django settings & root URLs
├── leads/
│   ├── models.py          # Lead model with status tracking
│   ├── serializers.py     # Input validation
│   ├── views.py           # API endpoints + pipeline
│   ├── urls.py            # URL routes
│   └── services/
│       ├── enrichment.py  # Groq AI company research
│       ├── pdf_generator.py # ReportLab PDF creation
│       ├── email_sender.py  # SendGrid email delivery
│       ├── sheets_logger.py # Google Sheets logging
│       └── drive_archiver.py # Google Drive archiving
├── templates/
│   └── frontend.html      # Lead intake form
├── requirements.txt
├── reflection.txt
└── README.md

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health/` | Liveness check |
| POST | `/api/leads/submit/` | Submit lead (triggers full pipeline) |
| GET | `/api/leads/` | List all submitted leads |

---

## Local Setup

### 1. Clone the repo
```bash
git clone https://github.com/vixnuu/simplifIQ.git
cd simplifIQ/core
```

### 2. Create virtual environment
```bash
python -m venv env
env\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Create `.env` file

DJANGO_SECRET_KEY=your-secret-key
GROQ_API_KEY=your-groq-key
SENDGRID_API_KEY=your-sendgrid-key
DEFAULT_FROM_EMAIL=your-verified-email

### 5. Run migrations
```bash
python manage.py migrate
```

### 6. Start server
```bash
python manage.py runserver
```

### 7. Open the form
Visit `http://127.0.0.1:8000` in your browser!

---

## Running Tests

```bash
python manage.py test leads --verbosity=2
```

20 tests covering models, validation, enrichment, PDF generation, and API endpoints.

---

## Pipeline Flow

Form Submission
↓
Validate Input (DRF)
↓
Save Lead to Database
↓
AI Enrichment (Groq)
↓
Generate PDF (ReportLab)
↓
Send Email (SendGrid)
↓
Archive to Drive + Log to Sheets (optional)


---

## Deployment

Deployed on Render with:
- Auto-deploy from GitHub
- Environment variables for all secrets
- Background threading for heavy pipeline tasks
- WhiteNoise for static files

