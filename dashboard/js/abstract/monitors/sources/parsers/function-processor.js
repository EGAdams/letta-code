import { IQueryResultProcessor } from "../../interfaces/query-result-processor.interface.js";

/**
 * FunctionProcessor — Adapter from a plain `parse(payload) → MonitorSnapshot`
 * function to the-factory's IQueryResultProcessor, so each endpoint's parser
 * stays one small pure function.
 */
export class FunctionProcessor extends IQueryResultProcessor {
  constructor(parse) {
    super();
    this.parse = parse;
  }

  processQueryResult(_callbackObject, queryResult) {
    return this.parse(queryResult ?? {});
  }
}
