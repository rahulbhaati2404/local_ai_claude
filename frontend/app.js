const CONFIG = {
  backendBaseUrl: 'http://127.0.0.1:9002/api/v1', // edit this if your backend runs elsewhere
};

const state = {
  prBusy: false,
  codeBusy: false,
  selectedFileName: '',
};

const $ = (id) => document.getElementById(id);

const prForm = $('prForm');
const prUrl = $('prUrl');
const prSubmit = $('prSubmit');
const prLog = $('prLog');
const prState = $('prState');

const codeForm = $('codeForm');
const filePath = $('filePath');
const codePrompt = $('codePrompt');
const mode = $('mode');
const codeSubmit = $('codeSubmit');
const codeLog = $('codeLog');
const codeState = $('codeState');
const pickFileBtn = $('pickFileBtn');
const filePicker = $('filePicker');

const template = $('messageTemplate');

function nowStamp() {
  return new Date().toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function setState(pill, text, variant) {
  pill.className = `state-pill ${variant}`;
  pill.textContent = text;
}

function setLoading(button, loading) {
  button.disabled = loading;
  button.classList.toggle('is-loading', loading);
}

function setPanelBusy(panelBusy, controls, pill, variant, label, button) {
  const loading = panelBusy;
  controls.forEach((control) => {
    control.disabled = loading;
  });
  setLoading(button, loading);
  setState(pill, label, variant);
}

function clearLog(logNode) {
  logNode.innerHTML = '';
}

function appendMessage(logNode, kind, label, body) {
  const fragment = template.content.cloneNode(true);
  const message = fragment.querySelector('.message');
  const typeNode = fragment.querySelector('.message-type');
  const timeNode = fragment.querySelector('.message-time');
  const bodyNode = fragment.querySelector('.message-body');

  message.classList.add(kind);
  typeNode.textContent = label;
  timeNode.textContent = nowStamp();
  bodyNode.textContent = typeof body === 'string' ? body : JSON.stringify(body, null, 2);

  logNode.appendChild(fragment);
  logNode.scrollTop = logNode.scrollHeight;
}

function safeJsonParse(text) {
  try {
    return JSON.parse(text);
  } catch (error) {
    return text;
  }
}

function getStreamUrl(pathname, params) {
  const url = new URL(`${CONFIG.backendBaseUrl}${pathname}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.set(key, value);
    }
  });
  return url.toString();
}

function openStream({
  pathname,
  params,
  logNode,
  pill,
  busySetter,
  onResult,
  onDone,
}) {
  const url = getStreamUrl(pathname, params);
  const source = new EventSource(url);

  source.addEventListener('status', (event) => {
    appendMessage(logNode, 'status', 'Status', event.data);
  });

  source.addEventListener('result', (event) => {
    const payload = safeJsonParse(event.data);
    appendMessage(logNode, 'result', 'Result', payload);
    onResult?.(payload);
    source.close();
    busySetter(false);
    setState(pill, 'Done', 'done');
    onDone?.(null, payload);
  });

  source.addEventListener('error', (event) => {
    const payload = event?.data ? safeJsonParse(event.data) : { detail: 'Stream failed' };
    appendMessage(logNode, 'error', 'Error', payload);
    source.close();
    busySetter(false);
    setState(pill, 'Error', 'error');
    onDone?.(payload, null);
  });

  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) {
      return;
    }
    source.close();
    busySetter(false);
    setState(pill, 'Error', 'error');
    appendMessage(logNode, 'error', 'Error', 'Stream connection closed unexpectedly.');
    onDone?.({ detail: 'Stream connection closed unexpectedly.' }, null);
  };

  return source;
}

function updateControlLock(lock) {
  const prControls = [prUrl];
  const codeControls = [filePath, codePrompt, mode, pickFileBtn, filePicker];

  setPanelBusy(
    lock && state.prBusy,
    prControls,
    prState,
    lock && state.prBusy ? 'loading' : 'idle',
    lock && state.prBusy ? 'Working' : 'Idle',
    prSubmit,
  );

  setPanelBusy(
    lock && state.codeBusy,
    codeControls,
    codeState,
    lock && state.codeBusy ? 'loading' : 'idle',
    lock && state.codeBusy ? 'Working' : 'Idle',
    codeSubmit,
  );
}

function syncBusyFlags() {
  setPanelBusy(
    state.prBusy,
    [prUrl],
    prState,
    state.prBusy ? 'loading' : 'idle',
    state.prBusy ? 'Working' : 'Idle',
    prSubmit,
  );

  setPanelBusy(
    state.codeBusy,
    [filePath, codePrompt, mode, pickFileBtn, filePicker],
    codeState,
    state.codeBusy ? 'loading' : 'idle',
    state.codeBusy ? 'Working' : 'Idle',
    codeSubmit,
  );
}

prForm.addEventListener('submit', (event) => {
  event.preventDefault();
  if (state.prBusy) return;

  const url = prUrl.value.trim();
  if (!url) {
    appendMessage(prLog, 'error', 'Validation', 'PR URL cannot be empty.');
    return;
  }

  state.prBusy = true;
  clearLog(prLog);
  setState(prState, 'Working', 'loading');
  syncBusyFlags();
  appendMessage(prLog, 'status', 'Status', 'Connected. Streaming live output...');

  openStream({
    pathname: '/review-pr',
    params: { pr_url: url },
    logNode: prLog,
    pill: prState,
    busySetter: (busy) => {
      state.prBusy = busy;
      syncBusyFlags();
    },
  });
});

pickFileBtn.addEventListener('click', async () => {
  if (state.codeBusy) return;

  if (window.showOpenFilePicker) {
    try {
      const [handle] = await window.showOpenFilePicker({
        multiple: false,
        excludeAcceptAllOption: false,
      });
      const file = await handle.getFile();
      filePath.value = file.webkitRelativePath || file.name;
      state.selectedFileName = file.name;
      appendMessage(
        codeLog,
        'status',
        'File',
        `Selected "${file.name}". Paste the absolute path into the field if your browser does not expose it.`,
      );
      return;
    } catch (error) {
      // User canceled the picker or the browser blocked the API.
    }
  }

  filePicker.click();
});

filePicker.addEventListener('change', () => {
  if (!filePicker.files || !filePicker.files.length) return;
  const file = filePicker.files[0];
  state.selectedFileName = file.name;
  if (!filePath.value.trim()) {
    filePath.value = file.name;
  }
  appendMessage(
    codeLog,
    'status',
    'File',
    `Selected "${file.name}". Enter the absolute path if needed before submitting.`,
  );
});

codeForm.addEventListener('submit', (event) => {
  event.preventDefault();
  if (state.codeBusy) return;

  const file = filePath.value.trim();
  const prompt = codePrompt.value.trim();
  const selectedMode = mode.value.trim();

  if (!file) {
    appendMessage(codeLog, 'error', 'Validation', 'File path cannot be empty.');
    return;
  }

  if (!prompt) {
    appendMessage(codeLog, 'error', 'Validation', 'Prompt cannot be empty.');
    return;
  }

  state.codeBusy = true;
  clearLog(codeLog);
  setState(codeState, 'Working', 'loading');
  syncBusyFlags();
  appendMessage(codeLog, 'status', 'Status', 'Connected. Streaming live output...');

  openStream({
    pathname: '/code-editor',
    params: {
      file_path: file,
      user_prompt: prompt,
      mode: selectedMode,
    },
    logNode: codeLog,
    pill: codeState,
    busySetter: (busy) => {
      state.codeBusy = busy;
      syncBusyFlags();
    },
    onResult: (payload) => {
      if (payload && payload.modified_files && Array.isArray(payload.modified_files)) {
        appendMessage(
          codeLog,
          'result',
          'Modified',
          `Modified files: ${payload.modified_files.join(', ') || 'none'}`,
        );
      }
    },
  });
});

updateControlLock(false);
syncBusyFlags();

