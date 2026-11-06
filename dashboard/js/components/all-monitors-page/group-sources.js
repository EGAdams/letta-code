/** Groups sources by their catalog `group`, keeping first-seen order. */
export function groupSources(sources) {
  const groups = new Map();
  for (const source of sources) {
    const name = source.group || "Other";
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(source);
  }
  return [...groups].map(([name, members]) => ({ name, members }));
}
