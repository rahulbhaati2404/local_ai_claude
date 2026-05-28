# Local AI Agent Engine

Local AI Agent Engine is a FastAPI-based backend that exposes two streamed workflows:

- `PR Review` for reviewing a pull request from a `pr_url`
- `Code Editor` for running a mode-driven code assistant with `ask`, `agent`, or `plan`

The backend streams progress and final output over Server-Sent Events, which makes it a good fit for a lightweight live chat-style UI.

## What is included

- FastAPI backend with two SSE endpoints
- Workflow graphs for PR review and code editor automation
- A simple frontend screen in `frontend/` with two independent chat panels
- Project architecture documentation and flow diagrams

## Backend APIs

### PR Review

- `POST /api/v1/review-pr`
- Frontend input: `pr_url`
- Hidden backend fields: `repository_path`, `source_branch`, `target_branch`, `pr_id`
- Response: streamed status updates plus final JSON result

### Code Editor

- `POST /api/v1/edit-code`
- Frontend inputs: `workspace_path`, `user_prompt`, `file_path`, `mode`
- `mode` options: `ask`, `agent`, `plan`
- Response: streamed status updates plus final JSON result

## Frontend

The frontend is a static browser page that:

- shows two separate chatboxes, one for each API
- locks the active form while the stream is running
- shows a loading state until the SSE stream ends
- appends streamed status messages and the final result into the chat area

## Run the backend

```bash
python -m venv venv311
.\\venv311\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Run the frontend

Serve the `frontend/` folder with any local static server, for example:

```bash
cd frontend
python -m http.server 5173
```

Then open `http://127.0.0.1:5173` in the browser.

## Documentation

- [Architecture](ARCHITECTURE.md)

