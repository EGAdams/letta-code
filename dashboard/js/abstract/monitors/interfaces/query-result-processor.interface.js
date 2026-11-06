import { abstractMethod } from "../../not-implemented.js";

/**
 * IQueryResultProcessor — the-factory's interface: turn one raw query result
 * into something the callback object can show. Parsers implement it.
 */
export class IQueryResultProcessor {
  /**
   * @param {object} _callbackObject whoever asked (a MonitorSource)
   * @param {any} _queryResult the endpoint's JSON payload
   * @returns {import("../sources/monitor-snapshot.js").MonitorSnapshot}
   */
  processQueryResult(_callbackObject, _queryResult) {
    abstractMethod("processQueryResult");
  }
}
