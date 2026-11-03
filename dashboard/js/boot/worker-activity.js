import {
  renderWorkerActivity,
  workerTabClass,
} from "../abstract/worker-activity-render.js";

export function createWorkerActivity({ doc = document, http }) {
  const body = doc.getElementById("worker-activity-body");
  const tab = doc.getElementById("btn-worker-activity");
  const controller = {
    async open() {
      if (!body) return;
      body.innerHTML = '<p class="am-dim">Checking worker activity&hellip;</p>';
      try {
        controller.payload = await http.getJSON("/api/worker-activity");
      } catch (error) {
        controller.payload = {
          ok: false,
          tasks_available: false,
          tasks_error: error.message,
        };
      }
      body.innerHTML = renderWorkerActivity(controller.payload);
      tab?.classList.remove("server-up", "server-concern", "poll-disabled");
      tab?.classList.add(workerTabClass(controller.payload));
    },
    bind() {
      body?.addEventListener("click", (event) => {
        if (event.target.closest("[data-worker-activity=refresh]"))
          void controller.open();
      });
    },
  };
  controller.bind();
  return controller;
}
