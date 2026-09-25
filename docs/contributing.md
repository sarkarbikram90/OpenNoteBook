# Contributing to OpenNotebook

Thank you for your interest in contributing to **OpenNotebook**! We welcome bug reports, documentation improvements, feature enhancements, and new document extractors or connectors.

---

## 1. Getting Started

1. **Fork the repository** on GitHub.
2. **Clone your fork locally**:
   ```bash
   git clone https://github.com/<your-username>/OpenNoteBook.git
   cd OpenNoteBook
   ```
3. Follow the [Local Development Guide](local-dev.md) to set up your environment.

---

## 2. Development Workflow

1. Create a feature branch off `main`:
   ```bash
   git checkout -b feature/my-new-feature
   ```
2. Write clean, modular, and well-tested code following repository architectural guidelines:
   * Keep FastAPI route handlers thin.
   * Encapsulate business logic in `backend/app/domain/`.
   * Use the repository pattern for all database interactions.
   * Write unit tests for new functionality in `backend/tests/unit/`.
3. Format and lint your code before committing:
   * **Python:**
     ```bash
     ruff check backend/app
     ruff format backend/app
     mypy backend/app
     ```
   * **Frontend:**
     ```bash
     cd frontend
     npm run lint
     npm run typecheck
     ```
4. Run the test suites to ensure zero regressions:
   ```bash
   cd backend && pytest tests/evaluation tests/unit -o addopts="" -q
   cd ../frontend && npm test
   ```

---

## 3. Pull Request Guidelines

* **Descriptive Titles & Commit Messages:** Use conventional commit syntax (e.g. `feat: add Notion connector`, `fix: resolve token expiry`).
* **CI Verification:** Ensure that all automated GitHub Actions checks (Backend CI, Frontend CI, Docker validation, Evaluation regression) pass.
* **Documentation:** If your change modifies an API endpoint, configuration setting, or deployment step, update the corresponding documentation in `docs/`.

---

## 4. Submitting New Document Extractors / Plugins

OpenNotebook uses an extensible connector framework. To add support for a new file format or data source:
1. Implement your extractor in `backend/app/domain/sources/`.
2. Follow the plugin interface documented in [Plugin Guide](plugin-guide.md).
3. Add unit tests verifying extraction with representative sample files.
