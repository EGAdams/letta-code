// Human-friendly dashboard version. Update deliberately; do not bump
// automatically as part of deployment.
export const DASHBOARD_VERSION = "v1";

export function createDashboardVersion({ doc = document }) {
  const heading = doc.querySelector?.("#worker-activity h2");
  if (!heading) return;
  const version = doc.createElement("span");
  version.className = "dashboard-version";
  version.textContent = ` (${DASHBOARD_VERSION})`;
  heading.append(version);
}
