import { createHash, randomUUID } from "node:crypto";
import {
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

type ConversationLeaseRecord = {
  pid: number;
  token: string;
  agentId: string;
  conversationId: string;
  createdAt: string;
};

export type ConversationLease = {
  path: string;
  release: () => void;
};

export class ConversationInUseError extends Error {
  constructor(
    readonly ownerPid: number,
    readonly agentId: string,
    readonly conversationId: string,
  ) {
    super(
      `Conversation ${conversationId} is already open in another Letta Code process ` +
        `(PID ${ownerPid}). Use that terminal, close it, or start this one with \`letta --new\`.`,
    );
    this.name = "ConversationInUseError";
  }
}

type AcquireConversationLeaseOptions = {
  agentId: string;
  conversationId: string;
  serverUrl?: string;
  leaseRoot?: string;
  pid?: number;
  isProcessAlive?: (pid: number) => boolean;
};

function defaultLeaseRoot(): string {
  return join(homedir(), ".letta", "locks", "conversations");
}

function defaultIsProcessAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (
      error instanceof Error &&
      "code" in error &&
      (error as NodeJS.ErrnoException).code === "EPERM"
    );
  }
}

function leasePath(
  leaseRoot: string,
  serverUrl: string,
  agentId: string,
  conversationId: string,
): string {
  const digest = createHash("sha256")
    .update(`${serverUrl}\0${agentId}\0${conversationId}`)
    .digest("hex");
  return join(leaseRoot, `${digest}.json`);
}

function readLease(path: string): ConversationLeaseRecord | null {
  try {
    const parsed = JSON.parse(
      readFileSync(path, "utf8"),
    ) as Partial<ConversationLeaseRecord>;
    if (
      typeof parsed.pid !== "number" ||
      typeof parsed.token !== "string" ||
      typeof parsed.agentId !== "string" ||
      typeof parsed.conversationId !== "string" ||
      typeof parsed.createdAt !== "string"
    ) {
      return null;
    }
    return parsed as ConversationLeaseRecord;
  } catch {
    return null;
  }
}

export function acquireConversationLease(
  options: AcquireConversationLeaseOptions,
): ConversationLease {
  const leaseRoot = options.leaseRoot ?? defaultLeaseRoot();
  const pid = options.pid ?? process.pid;
  const isProcessAlive = options.isProcessAlive ?? defaultIsProcessAlive;
  const path = leasePath(
    leaseRoot,
    options.serverUrl ?? "default-server",
    options.agentId,
    options.conversationId,
  );
  const token = randomUUID();
  const record: ConversationLeaseRecord = {
    pid,
    token,
    agentId: options.agentId,
    conversationId: options.conversationId,
    createdAt: new Date().toISOString(),
  };

  mkdirSync(leaseRoot, { recursive: true });

  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const fd = openSync(path, "wx", 0o600);
      try {
        writeFileSync(fd, JSON.stringify(record));
      } finally {
        closeSync(fd);
      }
      return {
        path,
        release: () => {
          const current = readLease(path);
          if (current?.token === token) {
            try {
              unlinkSync(path);
            } catch {
              // Best-effort cleanup. A dead PID is reclaimed on next startup.
            }
          }
        },
      };
    } catch (error) {
      const code =
        error instanceof Error && "code" in error
          ? (error as NodeJS.ErrnoException).code
          : undefined;
      if (code !== "EEXIST") throw error;

      const owner = readLease(path);
      if (owner && isProcessAlive(owner.pid)) {
        throw new ConversationInUseError(
          owner.pid,
          options.agentId,
          options.conversationId,
        );
      }

      // The owner exited without cleanup (SIGKILL, crash, power loss).
      if (existsSync(path)) {
        try {
          unlinkSync(path);
        } catch {
          // Another process may have reclaimed it first; retry the exclusive open.
        }
      }
    }
  }

  const owner = readLease(path);
  throw new ConversationInUseError(
    owner?.pid ?? -1,
    options.agentId,
    options.conversationId,
  );
}
