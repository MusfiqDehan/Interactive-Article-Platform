# Interactive Articles Platform

A full-stack web application for creating and viewing interactive articles with modal/popup-based content elements.

## Tech Stack

- **Backend**: Django 5.1 + Django REST Framework
- **Frontend**: Next.js 14 (App Router) + TypeScript + Tailwind CSS
- **Database**: PostgreSQL 16
- **Auth**: JWT (SimpleJWT)
- **Editor**: Editor.js (block-based content editor)
- **API Docs**: drf-spectacular (Swagger/OpenAPI 3.0)
- **Containerization**: Docker + Docker Compose

## Features

- Block-based article editor with Editor.js
- Interactive content blocks (text annotations with modals, image hotspots)
- JWT authentication with role-based access (admin, author, reader)
- Category/subcategory management
- Media library with file upload
- Dark/light theme toggle
- Responsive design
- Admin panel and user dashboard
- Swagger API documentation

## Getting Started

### Prerequisites

- Docker & Docker Compose

### Quick Start

```bash
# Clone and navigate to the project
cd Interactive-Articles

# Start all services
docker compose up --build

# The services will be available at:
# Frontend: http://localhost:3003
# Backend API: http://localhost:8003/api/
# Swagger Docs: http://localhost:8003/api/docs/
# Django Admin: http://localhost:8003/admin/
```

### Create a Superuser

```bash
docker compose exec backend python manage.py createsuperuser
```

### Development Setup (without Docker)

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Make sure PostgreSQL is running and update .env with correct POSTGRES_HOST=localhost
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8003
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Project Structure

```
Interactive-Articles/
├── backend/
│   ├── apps/
│   │   ├── accounts/      # User auth, JWT, profiles
│   │   ├── articles/       # Articles CRUD, block validation
│   │   ├── categories/     # Categories & subcategories
│   │   └── media_library/  # File uploads
│   ├── common/             # Shared pagination, permissions
│   ├── config/             # Django settings (base/dev/prod)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js App Router pages
│   │   │   ├── (public)/   # Public pages (landing, articles, categories)
│   │   │   ├── (auth)/     # Login & register
│   │   │   ├── admin/      # Admin panel
│   │   │   └── dashboard/  # User dashboard
│   │   ├── components/     # Reusable components
│   │   │   ├── article/    # Block renderers (interactive text/image)
│   │   │   ├── editor/     # Editor.js wrapper
│   │   │   ├── layout/     # Header, Footer, ThemeToggle
│   │   │   └── ui/         # Modal
│   │   └── lib/            # API client, auth context, types
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── .env
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/register/` | POST | Register new user |
| `/api/auth/login/` | POST | Login (get JWT tokens) |
| `/api/auth/logout/` | POST | Logout (blacklist token) |
| `/api/auth/profile/` | GET/PUT | User profile |
| `/api/articles/` | GET/POST | List/create articles |
| `/api/articles/{slug}/` | GET/PUT/DELETE | Article detail |
| `/api/articles/featured/` | GET | Featured articles |
| `/api/articles/my-articles/` | GET | User's articles |
| `/api/categories/` | GET/POST | List/create categories |
| `/api/media/upload/` | POST | Upload media file |
| `/api/docs/` | GET | Swagger UI |

## Interactive Content

Articles support two special interactive block types:

### Interactive Text
Text with clickable annotation spans that open modal popups with additional content.

### Interactive Image
Images with positioned hotspot buttons that open modal popups when clicked.

These are stored as JSON blocks in the article content and rendered client-side with React modals.

## Environment Variables

See `.env` for all configuration options.
