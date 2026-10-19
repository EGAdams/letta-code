export interface ExpenseDialogPort {
  selectedId: number | null;
  searchById(id: number): Promise<boolean>;
  selectCategory(id: number): void;
  saveChanges(): Promise<{
    ok: boolean;
    error?: string;
    warnings?: string[];
  } | null>;
}
export class ExpenseEditPanel {
  constructor(options: { http: object; root: HTMLElement; expanded?: boolean });
  dialog: ExpenseDialogPort;
  mount(): Promise<unknown>;
}
