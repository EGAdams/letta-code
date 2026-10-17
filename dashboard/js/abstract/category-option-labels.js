/** Display-only labels; canonical category values still drive validation/saves. */
export function categoryOptionLabels(names) {
  const rows = names.map((value) => {
    const match = /^(.*?)\s+\[(\d+)\]$/.exec(value);
    const path = (match?.[1] || value).split(" / ");
    const name = path.pop();
    return {
      value,
      id: match ? `[${match[2]}]` : "",
      name,
      parents: path.join(" / "),
    };
  });
  const idWidth = Math.max(0, ...rows.map((row) => row.id.length));
  const nameWidth = Math.max(0, ...rows.map((row) => row.name.length));
  // Native select menus collapse ordinary spaces on some platforms.
  const pad = (text, width) => text.padEnd(width, "\u00a0");
  return rows
    .sort(
      (a, b) =>
        a.name.localeCompare(b.name, undefined, { sensitivity: "base" }) ||
        a.parents.localeCompare(b.parents) ||
        a.value.localeCompare(b.value),
    )
    .map((row) => ({
      value: row.value,
      label:
        `${pad(row.id, idWidth)} ${row.parents ? pad(row.name, nameWidth) : row.name}` +
        (row.parents ? ` / ${row.parents}` : ""),
    }));
}
