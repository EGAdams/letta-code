import type Letta from "@letta-ai/letta-client";

type LettaClient = Letta;

export function sortNames(names: Iterable<string>): string[] {
  return [...names].sort();
}

export function formatNames(names: Iterable<string>): string {
  return sortNames(names).join(", ");
}

export async function listAgentToolNames(
  client: LettaClient,
  agentId: string,
): Promise<string[]> {
  const page = await client.agents.tools.list(agentId, { limit: 50 });
  return sortNames(
    page
      .getPaginatedItems()
      .map((t) => t.name)
      .filter((n): n is string => typeof n === "string"),
  );
}

export async function resolveToolIdByName(
  client: LettaClient,
  name: string,
): Promise<string> {
  const page = await client.tools.list({ name, limit: 10 });
  const tool = page.items.find((t) => t.name === name);
  if (!tool?.id) throw new Error(`Required server tool not found: ${name}`);
  return tool.id;
}

/** Attach any missing required tools and detach any unexpected ones. */
export async function ensureExactToolSet(
  client: LettaClient,
  agentId: string,
  requiredNames: readonly string[],
): Promise<void> {
  const page = await client.agents.tools.list(agentId, { limit: 50 });
  const attachedByName = new Map(
    page
      .getPaginatedItems()
      .filter(
        (t): t is typeof t & { id: string; name: string } =>
          typeof t.id === "string" && typeof t.name === "string",
      )
      .map((t) => [t.name, t.id]),
  );

  for (const name of requiredNames) {
    if (!attachedByName.has(name)) {
      const toolId = await resolveToolIdByName(client, name);
      await client.agents.tools.attach(toolId, { agent_id: agentId });
    }
  }
  for (const [name, toolId] of attachedByName) {
    if (!requiredNames.includes(name)) {
      await client.agents.tools.detach(toolId, { agent_id: agentId });
    }
  }
}
