/**
 * GaugeRegistry — the open half of Oak Ridge's GaugeFactory. Its switch
 * statement is replaced by a map, so a new gauge type is one register() call,
 * not an edit (OCP).
 */
export class GaugeRegistry {
  constructor() {
    this._types = new Map();
  }

  register(type, GaugeClass) {
    this._types.set(type, GaugeClass);
    return this;
  }

  has(type) {
    return this._types.has(type);
  }

  create(type, renderTo, Engine) {
    const GaugeClass = this._types.get(type);
    if (!GaugeClass) throw new Error(`Invalid gauge type: ${type}`);
    return new GaugeClass(renderTo, Engine);
  }
}
