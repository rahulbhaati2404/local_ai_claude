const API_BASE_URL = "http://127.0.0.1:8000/api/v1";

const state = {
  prReview: { busy: false },
  codeEditor: { busy: false },
};

const prForm = document.getElementById("pr-form");
const prUrlInput = document.getElementById("pr-url");
const prChat = document.getElementById("pr-chat");
const prPanel = document.getElementById("pr-panel");
const prStatus = prPanel.querySelector("[data-status]");

const codeForm = document.getElementById("code-form");
const workspacePathInput = document.getElementById("workspace-path");
const userPromptInput = document.getElementById("user-prompt");
const filePathInput = document.getElementById("file-path");
const modeSelect = document.getElementById("mode");
const codeChat = document.getElementById("code-chat");
const codePanel = document.getElementById("code-panel");
const codeStatus = codePanel.querySelector("[data-status]");

renderEmptyState(prChat, "Submit a PR URL to start a live review stream.");
renderEmptyState(codeChat, "Submit code editor inputs to start a live execution stream.");

prForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (state.prReview.busy) {
    return;
  }
  void runPrReview();
});

codeForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (state.codeEditor.busy) {
    return;
  }
  void runCodeEditor();
});

async function runPrReview() {
  const prUrl = prUrlInput.value.trim();
  if (!prUrl) {
    appendBubble(prChat, "error", "PR URL is required.");
    return;
  }

  clearEmptyState(prChat);
  appendBubble(prChat, "user", `PR URL: ${prUrl}`);
  setBusy("prReview", true, "Running PR review...");

  try {
    const params = new URLSearchParams({ pr_url: prUrl });
    const response = await fetch(`${API_BASE_URL}/review-pr?${params.toString()}`, {
      method: "POST",
      headers: { Accept: "text/event-stream" },
    });

    await handleSseResponse(response, prChat, "prReview");
  } catch (error) {
    appendBubble(prChat, "error", `Request failed: ${formatError(error)}`);
  } finally {
    setBusy("prReview", false, "Idle");
  }
}

async function runCodeEditor() {
  const workspacePath = workspacePathInput.value.trim();
  const userPrompt = userPromptInput.value.trim();
  const filePath = filePathInput.value.trim();
  const mode = modeSelect.value;

  if (!workspacePath || !userPrompt) {
    appendBubble(codeChat, "error", "Workspace path and user prompt are required.");
    return;
  }

  clearEmptyState(codeChat);
  appendBubble(
    codeChat,
    "user",
    [
      `Workspace path: ${workspacePath}`,
      `Mode: ${mode}`,
      `File path: ${filePath || "(none)"}`,
      `Prompt: ${userPrompt}`,
    ].join("\n"),
  );
  setBusy("codeEditor", true, "Running code editor...");

  try {
    const params = new URLSearchParams({
      workspace_path: workspacePath,
      user_prompt: userPrompt,
      mode,
    });

    if (filePath) {
      params.set("file_path", filePath);
    }

    const response = await fetch(`${API_BASE_URL}/edit-code?${params.toString()}`, {
      method: "POST",
      headers: { Accept: "text/event-stream" },
    });

    await handleSseResponse(response, codeChat, "codeEditor");
  } catch (error) {
    appendBubble(codeChat, "error", `Request failed: ${formatError(error)}`);
  } finally {
    setBusy("codeEditor", false, "Idle");
  }
}

async function handleSseResponse(response, chatContainer, sectionKey) {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(parseResponseError(body, response.status));
  }

  if (!response.body) {
    throw new Error("The browser did not expose a readable stream.");
  }

  appendBubble(chatContainer, "status", "Connected. Streaming live output...");
  await readSseStream(response.body, (event) => {
    if (!event.type && !event.data) {
      return;
    }

    if (event.type === "status") {
      appendBubble(chatContainer, "status", event.data || "Working...");
      return;
    }

    if (event.type === "error") {
      appendBubble(chatContainer, "error", normalizePayload(event.data));
      return;
    }

    if (event.type === "result") {
      appendResultBubble(chatContainer, event.data);
      return;
    }

    appendBubble(chatContainer, "status", event.data || event.type);
  });

  const statusLabel = sectionKey === "prReview" ? "Review complete" : "Execution complete";
  appendBubble(chatContainer, "status", statusLabel);
}

async function readSseStream(stream, onEvent) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (value) {
      buffer += decoder.decode(value, { stream: !done });
      buffer = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    }

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const parsed = parseSseBlock(rawEvent);
      if (parsed) {
        onEvent(parsed);
      }
      boundary = buffer.indexOf("\n\n");
    }

    if (done) {
      const tail = buffer.trim();
      if (tail) {
        const parsed = parseSseBlock(tail);
        if (parsed) {
          onEvent(parsed);
        }
      }
      break;
    }
  }
}

function parseSseBlock(block) {
  const event = { type: "message", data: "" };
  const lines = block.split(/\r?\n/);

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event.type = line.slice(6).trim();
      continue;
    }

    if (line.startsWith("data:")) {
      const value = line.slice(5).trimStart();
      event.data = event.data ? `${event.data}\n${value}` : value;
    }
  }

  return event.data || event.type !== "message" ? event : null;
}

function setBusy(sectionKey, busy, label) {
  state[sectionKey].busy = busy;

  const isPrReview = sectionKey === "prReview";
  const panel = isPrReview ? prPanel : codePanel;
  const status = isPrReview ? prStatus : codeStatus;
  const form = isPrReview ? prForm : codeForm;
  const button = form.querySelector("button[type='submit']");

  status.textContent = label;
  status.classList.toggle("is-active", busy);

  for (const element of form.querySelectorAll("input, textarea, select, button")) {
    element.disabled = busy;
  }

  button.textContent = busy ? "Loading..." : (isPrReview ? "Run PR Review" : "Run Code Editor");
  panel.dataset.busy = String(busy);
}

function appendBubble(container, tone, text) {
  clearEmptyState(container);

  const bubble = document.createElement("div");
  bubble.className = `bubble ${tone}`;

  if (tone === "status" && typeof text === "string" && text.startsWith("Connected.")) {
    const spinner = document.createElement("span");
    spinner.className = "spinner";
    spinner.textContent = text;
    bubble.appendChild(spinner);
  } else if (typeof text === "string") {
    bubble.textContent = text;
  } else {
    bubble.textContent = normalizePayload(text);
  }

  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function appendResultBubble(container, payload) {
  const bubble = document.createElement("div");
  bubble.className = "bubble result";

  const title = document.createElement("strong");
  title.textContent = "Final result";

  const pre = document.createElement("pre");
  pre.textContent = normalizePayload(payload);

  bubble.append(title, document.createElement("br"), pre);
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function renderEmptyState(container, message) {
  container.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = message;
  container.appendChild(empty);
}

function clearEmptyState(container) {
  const emptyState = container.querySelector(".empty-state");
  if (emptyState) {
    emptyState.remove();
  }
}

function formatError(error) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function parseResponseError(body, statusCode) {
  const fallback = `Request failed with status ${statusCode}.`;
  if (!body) {
    return fallback;
  }

  try {
    const parsed = JSON.parse(body);
    return parsed.detail || parsed.message || fallback;
  } catch {
    return body.trim() || fallback;
  }
}

function normalizePayload(payload) {
  if (payload == null) {
    return "";
  }

  if (typeof payload === "string") {
    try {
      const parsed = JSON.parse(payload);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return payload;
    }
  }

  return JSON.stringify(payload, null, 2);
}
