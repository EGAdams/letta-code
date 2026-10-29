/**
 * The live form state and view operations needed by batch saving.
 * No DOM queries or HTTP behavior belong in this agreement.
 *
 * @typedef {object} ManualEntrySaveView
 * @property {object[]} items
 * @property {number} currentIndex
 * @property {object|null} statementHeader
 * @property {object[]} statementExcludedRows
 * @property {{value: string}} imagePathInput
 * @property {string} conversationId
 * @property {boolean} addExpenseMode
 * @property {{postJSON: Function}} http
 * @property {{location: {reload: Function}}} doc
 * @property {function(): void} _captureCurrentItem
 * @property {function(): void} _renderCurrentItem
 * @property {function(object): void} _renderErrors
 * @property {function(string): void} _setStatus
 * @property {function(object, object): Promise<object>} _saveOneItem
 * @property {function(): Promise<void>} _saveStatement
 * @property {function(): Promise<void>} _loadDropdownOptions
 */
export {};
