# OpenNotebook — Frontend Application

This directory contains the user interface for **OpenNotebook**, built with React 19, TypeScript, and Vite.

---

## 1. Tech Stack

* **Framework:** React 19 + TypeScript
* **Build Tool:** Vite
* **Styling:** Tailwind CSS v4
* **State & Data Fetching:** TanStack Query (`@tanstack/react-query`)
* **Routing:** TanStack Router (`@tanstack/react-router`)
* **Icons:** Lucide React (`lucide-react`)
* **Markdown Rendering:** `react-markdown` + `rehype-highlight`
* **File Uploads:** `react-dropzone`
* **Command Palette:** `cmdk`

---

## 2. Directory Structure

```
frontend/
├── src/
│   ├── components/      # UI components (chat, notebooks, sources, modals)
│   ├── hooks/           # Custom React hooks (useChat, useStream, useAuth)
│   ├── lib/             # API client, utility functions, type definitions
│   ├── stores/          # Client-side state stores (auth, theme)
│   ├── App.tsx          # Root application component
│   └── main.tsx         # Entrypoint
├── nginx.conf           # Production Nginx reverse-proxy configuration
├── Dockerfile           # Multi-stage production container build
├── package.json         # Dependencies and scripts
└── vite.config.ts       # Vite and Vitest configuration
```

---

## 3. Development Scripts

```bash
# Install dependencies
npm ci

# Start local dev server (http://localhost:5173)
npm run dev

# Run TypeScript type check
npm run typecheck

# Lint with ESLint
npm run lint

# Run unit tests with Vitest
npm test

# Build production bundle for deployment
npm run build
```

---

## 4. Cloud Run & Nginx Containerization

The production Docker image (`frontend/Dockerfile`) uses a 2-stage build:
1. **Build Stage:** `node:20-slim` compiles the React TypeScript source to static assets (`dist/`).
2. **Serving Stage:** `nginx:alpine` serves static assets and reverse-proxies `/api/*` to the backend.

### Cloud Run Compatibility
* **Dynamic `$PORT`:** At container startup, Nginx dynamically rewrites `listen 80;` to `listen ${PORT:-80};` to adhere to Google Cloud Run's port contract.
* **Dynamic `$BACKEND_URL`:** If `BACKEND_URL` is passed (e.g. `https://opennotebook-api-...run.app`), Nginx rewrites the `proxy_pass` directive, enables `proxy_ssl_server_name on;`, and sets `Host $proxy_host;` to avoid Cloud Run SSL SNI failures or 404 Host mismatches.
