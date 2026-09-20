export class NotImplementedError extends Error {
  constructor(method: string);
}

export function abstractMethod(name: string): never;
