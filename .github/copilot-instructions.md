# Copilot Instructions

## Build, test, and lint commands

### Full stack

```bash
docker compose up --build
```

Services run on **frontend 3003**, **backend 8003**, and **PostgreSQL 5432**.

### Backend (Django)

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8003
python manage.py test
python manage.py test apps.articles.tests.ArticleTests.test_name
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
npm run build
npm run lint
```

There is no committed frontend test script or backend lint script in this repository.

## High-level architecture

- The repo is a split **Django REST API + Next.js App Router** app. The backend owns persistence, permissions, sanitization, and API shape; the frontend is mostly client-rendered and talks to the API directly with Axios.
- Backend API routes are mounted in `backend/config/urls.py` under `/api/auth/`, `/api/categories/`, `/api/articles/`, and `/api/media/`. Global DRF behavior lives in `backend/config/settings/base.py`: JWT auth, page-number pagination (`page_size=12`), filter/search/ordering backends, and drf-spectacular schema generation.
- Auth is role-based around the custom `accounts.User` model (`admin`, `author`, `reader`) with **email as the login identifier**. Access rules are centralized in `backend/common/permissions.py` and reused across article, category, and media views.
- Articles are the core domain object. `apps.articles.models.Article` stores **Editor.js output in a JSONField**, generates a unique slug from the title, sets `published_at` when status becomes `published`, and derives `reading_time` from block content. `apps.articles.serializers` validates allowed block types and sanitizes HTML-bearing text fields with `nh3`.
- Frontend routing is grouped under `src/app/(public)`, `src/app/(auth)`, `src/app/admin`, and `src/app/dashboard`. `src/app/providers.tsx` wraps the app in `ThemeProvider` and `AuthProvider`.
- Frontend auth state lives in `src/lib/auth.tsx` and `src/lib/api.ts`: tokens and user are cached in `localStorage`, requests automatically attach the bearer token, and 401s trigger refresh via `/auth/token/refresh/` before falling back to `/login`.
- Article creation/editing is entirely client-side in the admin area. `src/components/editor/Editor.tsx` dynamically loads Editor.js on the client, uploads files to `/api/media/upload/`, and emits Editor.js JSON. Public article pages fetch by **slug**, render `content.blocks` through `src/components/article/BlockRenderer.tsx`, and separately POST to `/api/articles/<slug>/view/` to increment view counts.

## Key conventions

- **Use slugs for reads in URLs.** Article and category detail routes use slugs, not numeric IDs. Write payloads still send foreign keys such as `category` and `subcategory` as numeric IDs.
- **Keep the backend/frontend block contract in sync.** If you add an Editor.js block type, update backend validation in `apps.articles.serializers.ALLOWED_BLOCK_TYPES`, the shared frontend types in `src/lib/types.ts`, and the renderer mapping in `src/components/article/BlockRenderer.tsx`.
- **Preserve the Editor.js upload response shape.** `MediaUploadView` returns `{ success, file }` because the editor image tool depends on that exact structure.
- **Expect paginated list responses from DRF.** Frontend list pages commonly read `res.data.results || res.data`; keep that compatibility when changing serializers or endpoints.
- **Category list responses already include nested subcategories.** Admin article forms use the category payload to populate the subcategory dropdown client-side instead of making a second request.
- **Route protection happens in layout components.** `src/app/admin/layout.tsx` admits only `admin` and `author`; `src/app/dashboard/layout.tsx` requires any authenticated user.
- **Reuse shared Tailwind component classes** from `src/app/globals.css` (`btn-primary`, `btn-secondary`, `btn-danger`, `input-field`, `card`) instead of introducing one-off button/input styling.
- **If image hosts change, update `frontend/next.config.js`.** Remote image loading is explicitly allowlisted for the backend host/port.
