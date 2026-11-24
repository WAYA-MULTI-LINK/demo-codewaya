const API = "/api/tasks";

const state = { tasks: [], filter: "all" };

const listEl = document.getElementById("task-list");
const emptyEl = document.getElementById("empty");
const counterEl = document.getElementById("counter");
const errorEl = document.getElementById("error");
const addForm = document.getElementById("add-form");
const titleInput = document.getElementById("title");
const descInput = document.getElementById("description");

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
}

function clearError() {
  errorEl.hidden = true;
  errorEl.textContent = "";
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let body = null;
  if (res.status !== 204) {
    body = await res.json().catch(() => null);
  }
  if (!res.ok) {
    throw new Error((body && body.error) || `Request failed (${res.status})`);
  }
  return body;
}

async function loadTasks() {
  try {
    state.tasks = await api(API);
    clearError();
    render();
  } catch (err) {
    showError(`Could not load tasks: ${err.message}`);
  }
}

function visibleTasks() {
  if (state.filter === "active") return state.tasks.filter((t) => !t.completed);
  if (state.filter === "done") return state.tasks.filter((t) => t.completed);
  return state.tasks;
}

function render() {
  listEl.replaceChildren();
  const tasks = visibleTasks();
  const total = state.tasks.length;
  const done = state.tasks.filter((t) => t.completed).length;
  counterEl.textContent = `${done} of ${total} completed`;
  emptyEl.hidden = tasks.length > 0;
  if (total === 0) {
    emptyEl.textContent = "No tasks yet. Add one above!";
  } else if (tasks.length === 0) {
    emptyEl.textContent = "No tasks match this filter.";
  }
  for (const task of tasks) listEl.appendChild(renderTask(task));
}

function renderTask(task) {
  const li = document.createElement("li");
  li.className =
    "task list-group-item d-flex align-items-start gap-3" +
    (task.completed ? " done" : "");
  li.dataset.id = task.id;

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.className = "form-check-input";
  checkbox.checked = task.completed;
  checkbox.setAttribute("aria-label", `Mark "${task.title}" as completed`);
  checkbox.addEventListener("change", () => toggleTask(task, checkbox));

  const body = document.createElement("div");
  body.className = "task-body";
  const title = document.createElement("div");
  title.className = "task-title";
  title.textContent = task.title;
  body.appendChild(title);
  if (task.description) {
    const desc = document.createElement("div");
    desc.className = "task-desc";
    desc.textContent = task.description;
    body.appendChild(desc);
  }

  const actions = document.createElement("div");
  actions.className = "task-actions";
  actions.append(
    actionButton("Edit", () => startEdit(li, task)),
    actionButton("Delete", () => deleteTask(task), "danger")
  );

  li.append(checkbox, body, actions);
  return li;
}

function actionButton(label, onClick, danger = false) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = danger
    ? "btn btn-sm btn-outline-danger"
    : "btn btn-sm btn-outline-secondary";
  btn.textContent = label;
  btn.addEventListener("click", onClick);
  return btn;
}

function startEdit(li, task) {
  li.replaceChildren();
  const form = document.createElement("form");
  form.className = "edit-form";

  const title = document.createElement("input");
  title.type = "text";
  title.className = "form-control form-control-sm";
  title.value = task.title;
  title.required = true;
  title.maxLength = 200;

  const desc = document.createElement("input");
  desc.type = "text";
  desc.className = "form-control form-control-sm";
  desc.value = task.description || "";
  desc.placeholder = "Description";
  desc.maxLength = 500;

  const row = document.createElement("div");
  row.className = "d-flex gap-2";
  const save = document.createElement("button");
  save.type = "submit";
  save.textContent = "Save";
  save.className = "btn btn-sm btn-primary fw-semibold";
  const cancel = actionButton("Cancel", () => render());
  cancel.type = "button";
  row.append(save, cancel);

  form.append(title, desc, row);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api(`${API}/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: title.value, description: desc.value }),
      });
      await loadTasks();
    } catch (err) {
      showError(err.message);
    }
  });

  li.appendChild(form);
  title.focus();
  title.select();
}

async function toggleTask(task, checkbox) {
  checkbox.disabled = true;
  try {
    await api(`${API}/${task.id}`, {
      method: "PATCH",
      body: JSON.stringify({ completed: checkbox.checked }),
    });
    await loadTasks();
  } catch (err) {
    checkbox.checked = task.completed;
    checkbox.disabled = false;
    showError(err.message);
  }
}

async function deleteTask(task) {
  if (!confirm(`Delete "${task.title}"?`)) return;
  try {
    await api(`${API}/${task.id}`, { method: "DELETE" });
    await loadTasks();
  } catch (err) {
    showError(err.message);
  }
}

addForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = titleInput.value.trim();
  if (!title) return;
  const submit = addForm.querySelector("button[type=submit]");
  submit.disabled = true;
  try {
    await api(API, {
      method: "POST",
      body: JSON.stringify({ title, description: descInput.value.trim() }),
    });
    addForm.reset();
    titleInput.focus();
    await loadTasks();
  } catch (err) {
    showError(err.message);
  } finally {
    submit.disabled = false;
  }
});

document.querySelectorAll(".filters button").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.filter = btn.dataset.filter;
    document.querySelectorAll(".filters button").forEach((b) => {
      const isActive = b === btn;
      b.classList.toggle("active", isActive);
      b.setAttribute("aria-pressed", String(isActive));
    });
    render();
  });
});

loadTasks();
