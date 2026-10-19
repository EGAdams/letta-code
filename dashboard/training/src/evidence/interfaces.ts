export interface IReadJson {
  get(url: string, options: RequestInit): Promise<unknown>;
}
