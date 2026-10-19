# Twerva

Twerva makes Instagram and TikTok photo carousels for my own brands from my own source material. Skeletons are the frame layout. Albums are image libraries. Research is text documents. Carousels are built in stages. An LLM drafts slide text, and a person reviews it before it goes live. This project may expand to other social media platforms and content types later.

Twerva runs on a server in my own AWS account, as a separate service from Spotmu.

## Why

Most carousel tools optimize for ease. A paragraph prompt turns into hundreds of posts, and that ease leads to oversupply of the same kind of post. I want deep control instead: the drafts should stay grounded in the research, rules, specs, and images I upload, and I review them before they go live. The roadmap is to learn which research sources, topics, and angles perform, from intent signals such as saves, shares, and profile visits, rather than only which post did. The full case is in [`docs/theory_of_the_case.md`](docs/theory_of_the_case.md).

## Who it's for

Me and my own brands first, with Spotmu as the first user. Also small teams with real products who want control over their content.

## Current features

Phases 1–4 in [`docs/planning/phase_map.md`](docs/planning/phase_map.md) are in.

- **Skeletons, Carousels, and Slides.** A skeleton is one frame: a background (picture, solid color, or gradient), spacing, and named text or image elements. A carousel is bound to one skeleton, chosen at create and not changed later. A slide has a name, one text per named text element, and an image when the skeleton needs a picture.
- **Albums.** An album is a named set of images. Upload and URL import store a license and a source note. A carousel attaches one album. Slides pick an image from that album. The six packaged photos are the Default album.
- **Research.** A research item is one document: a title and a body of Markdown or plain text. A carousel can attach several, in order. The body is edited on the Research page.
- **Carousel stepper and Content step.** Create opens on Basic: generation 1, the skeleton name, and the label. Content attaches an album and optional research, and can add images to that album. Slides is the editor (name, text, exclusions, image pick) and autosaves. Instructions and Final are on the stepper and stay closed.
- **OpenAI-drafted slide text.** When `OPENAI_API_KEY` is set, Generate drafts a slide's name and text (`TEXT_GENERATION_PROVIDER` is `openai` or `fake`; the model defaults to `gpt-4o-mini`). Accept makes that text the live text. A slide left unreviewed stays off a run. Images are not generated. With no key, Generate stays off.
- **Signed-in ops console.** Cookie session. An admin can change rows. A reader can look. The rail is Content (Campaigns, Skeletons, Carousels), Library (Albums, Research), Run (Queue, Schedule, Results), and Setup (Accounts, Users).
- **Mock publish and manual metrics.** The earlier loop can still approve a draft, set a time, mock-publish, and record a metric by hand. Publish is a mock adapter. An account can store a per-day cadence cap. It does not store a login. Real Instagram and TikTok publishing is not built. Pulling views and engagement from the platforms is not built.

## Built with

- API: FastAPI, SQLAlchemy, PostgreSQL, in `apps/server`.
- Ops console: React, Vite, TypeScript, in `apps/ops`.

## How to run

`GET /health` does not need Postgres. `/api/v1` and `python -m app.seed` do. `/api/v1` except `/auth/login`, `/logout`, and `/me` needs a session cookie.

Postgres has to be listening at the URL in `apps/server/.env.example`. The local default is `postgresql+psycopg://twerva:twerva@127.0.0.1:5432/twerva`. Bare `postgresql://` and `postgres://` URLs are rewritten to the psycopg3 dialect.

**API** (Python 3.11+):

```bash
cd apps/server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m app.seed
python -m app.auth.bootstrap
uvicorn app.main:application --reload --host 127.0.0.1 --port 8000
```

`GET http://127.0.0.1:8000/health` returns `{"status":"ok"}` without `DATABASE_URL`. With a URL, `/api/v1` mounts.

`.env` is gitignored. The example file sets a local `SESSION_SECRET`, `SESSION_COOKIE_SECURE=false`, and the bootstrap admin (`OPS_ADMIN_USERNAME` / `OPS_ADMIN_PASSWORD`). Change those before anyone else can reach the process. `python -m app.auth.bootstrap` does nothing if an operator row already exists. Details: [`apps/server/README.md`](apps/server/README.md).

**Ops console** (Node.js 20+):

```bash
cd apps/ops
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173) and sign in with the bootstrap admin. Vite proxies `/api` and `/health` to the API on port 8000 when `VITE_API_BASE_URL` is unset. Copy `apps/ops/.env.example` to `.env` only if the console should call another origin. Do not set `VITE_API_BASE_URL` for a production build. Details: [`apps/ops/README.md`](apps/ops/README.md).

## Roadmap

Phases 5–12 in [`docs/planning/phase_map.md`](docs/planning/phase_map.md): Instructions, AI slide generation, Final assembly, Generations, Campaign timeline, Accounts and publishing, Measurement, Next generation from results.

## License

MIT. Copyright (c) 2026 Brendan Conlon. See [LICENSE](LICENSE).

Bundled fonts keep the SIL Open Font License in `apps/server/app/skeletons/bundled_fonts/*/OFL.txt`. Default photos keep their own public-domain and CC0 terms in [`apps/server/app/skeletons/default_images/LICENSES.md`](apps/server/app/skeletons/default_images/LICENSES.md).
