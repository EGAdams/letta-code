/**
 * IMonitorLedData — the-factory's { classObject, ledText } pair: the object
 * that owns an LED, and the words it shows.
 */
export class MonitorLedData {
  /** @param {{classObject?: object, ledText?: string}} data */
  constructor({ classObject = null, ledText = "" } = {}) {
    this.classObject = classObject;
    this.ledText = String(ledText);
  }
}
