var ci = Object.defineProperty;
var ui = (e, t, s) => t in e ? ci(e, t, { enumerable: !0, configurable: !0, writable: !0, value: s }) : e[t] = s;
var j = (e, t, s) => ui(e, typeof t != "symbol" ? t + "" : t, s);
/**
* @vue/shared v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
/*! #__NO_SIDE_EFFECTS__ */
// @__NO_SIDE_EFFECTS__
function Ks(e) {
  const t = /* @__PURE__ */ Object.create(null);
  for (const s of e.split(",")) t[s] = 1;
  return (s) => s in t;
}
const V = {}, at = [], $e = () => {
}, ai = () => !1, os = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && // uppercase letter
(e.charCodeAt(2) > 122 || e.charCodeAt(2) < 97), Gs = (e) => e.startsWith("onUpdate:"), re = Object.assign, qs = (e, t) => {
  const s = e.indexOf(t);
  s > -1 && e.splice(s, 1);
}, fi = Object.prototype.hasOwnProperty, k = (e, t) => fi.call(e, t), O = Array.isArray, ft = (e) => ls(e) === "[object Map]", qn = (e) => ls(e) === "[object Set]", M = (e) => typeof e == "function", Z = (e) => typeof e == "string", Ue = (e) => typeof e == "symbol", J = (e) => e !== null && typeof e == "object", Jn = (e) => (J(e) || M(e)) && M(e.then) && M(e.catch), zn = Object.prototype.toString, ls = (e) => zn.call(e), di = (e) => ls(e).slice(8, -1), Yn = (e) => ls(e) === "[object Object]", Js = (e) => Z(e) && e !== "NaN" && e[0] !== "-" && "" + parseInt(e, 10) === e, At = /* @__PURE__ */ Ks(
  // the leading comma is intentional so empty string "" is also included
  ",key,ref,ref_for,ref_key,onVnodeBeforeMount,onVnodeMounted,onVnodeBeforeUpdate,onVnodeUpdated,onVnodeBeforeUnmount,onVnodeUnmounted"
), cs = (e) => {
  const t = /* @__PURE__ */ Object.create(null);
  return (s) => t[s] || (t[s] = e(s));
}, hi = /-(\w)/g, We = cs(
  (e) => e.replace(hi, (t, s) => s ? s.toUpperCase() : "")
), pi = /\B([A-Z])/g, ot = cs(
  (e) => e.replace(pi, "-$1").toLowerCase()
), Xn = cs((e) => e.charAt(0).toUpperCase() + e.slice(1)), _s = cs(
  (e) => e ? `on${Xn(e)}` : ""
), Be = (e, t) => !Object.is(e, t), bs = (e, ...t) => {
  for (let s = 0; s < e.length; s++)
    e[s](...t);
}, Zn = (e, t, s, n = !1) => {
  Object.defineProperty(e, t, {
    configurable: !0,
    enumerable: !1,
    writable: n,
    value: s
  });
}, gi = (e) => {
  const t = parseFloat(e);
  return isNaN(t) ? e : t;
};
let mn;
const us = () => mn || (mn = typeof globalThis < "u" ? globalThis : typeof self < "u" ? self : typeof window < "u" ? window : typeof global < "u" ? global : {});
function pe(e) {
  if (O(e)) {
    const t = {};
    for (let s = 0; s < e.length; s++) {
      const n = e[s], r = Z(n) ? vi(n) : pe(n);
      if (r)
        for (const i in r)
          t[i] = r[i];
    }
    return t;
  } else if (Z(e) || J(e))
    return e;
}
const mi = /;(?![^(]*\))/g, _i = /:([^]+)/, bi = /\/\*[^]*?\*\//g;
function vi(e) {
  const t = {};
  return e.replace(bi, "").split(mi).forEach((s) => {
    if (s) {
      const n = s.split(_i);
      n.length > 1 && (t[n[0].trim()] = n[1].trim());
    }
  }), t;
}
function Ve(e) {
  let t = "";
  if (Z(e))
    t = e;
  else if (O(e))
    for (let s = 0; s < e.length; s++) {
      const n = Ve(e[s]);
      n && (t += n + " ");
    }
  else if (J(e))
    for (const s in e)
      e[s] && (t += s + " ");
  return t.trim();
}
const wi = "itemscope,allowfullscreen,formnovalidate,ismap,nomodule,novalidate,readonly", yi = /* @__PURE__ */ Ks(wi);
function Qn(e) {
  return !!e || e === "";
}
const er = (e) => !!(e && e.__v_isRef === !0), X = (e) => Z(e) ? e : e == null ? "" : O(e) || J(e) && (e.toString === zn || !M(e.toString)) ? er(e) ? X(e.value) : JSON.stringify(e, tr, 2) : String(e), tr = (e, t) => er(t) ? tr(e, t.value) : ft(t) ? {
  [`Map(${t.size})`]: [...t.entries()].reduce(
    (s, [n, r], i) => (s[vs(n, i) + " =>"] = r, s),
    {}
  )
} : qn(t) ? {
  [`Set(${t.size})`]: [...t.values()].map((s) => vs(s))
} : Ue(t) ? vs(t) : J(t) && !O(t) && !Yn(t) ? String(t) : t, vs = (e, t = "") => {
  var s;
  return (
    // Symbol.description in es2019+ so we need to cast here to pass
    // the lib: es2016 check
    Ue(e) ? `Symbol(${(s = e.description) != null ? s : t})` : e
  );
};
/**
* @vue/reactivity v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
let he;
class xi {
  constructor(t = !1) {
    this.detached = t, this._active = !0, this.effects = [], this.cleanups = [], this._isPaused = !1, this.parent = he, !t && he && (this.index = (he.scopes || (he.scopes = [])).push(
      this
    ) - 1);
  }
  get active() {
    return this._active;
  }
  pause() {
    if (this._active) {
      this._isPaused = !0;
      let t, s;
      if (this.scopes)
        for (t = 0, s = this.scopes.length; t < s; t++)
          this.scopes[t].pause();
      for (t = 0, s = this.effects.length; t < s; t++)
        this.effects[t].pause();
    }
  }
  /**
   * Resumes the effect scope, including all child scopes and effects.
   */
  resume() {
    if (this._active && this._isPaused) {
      this._isPaused = !1;
      let t, s;
      if (this.scopes)
        for (t = 0, s = this.scopes.length; t < s; t++)
          this.scopes[t].resume();
      for (t = 0, s = this.effects.length; t < s; t++)
        this.effects[t].resume();
    }
  }
  run(t) {
    if (this._active) {
      const s = he;
      try {
        return he = this, t();
      } finally {
        he = s;
      }
    }
  }
  /**
   * This should only be called on non-detached scopes
   * @internal
   */
  on() {
    he = this;
  }
  /**
   * This should only be called on non-detached scopes
   * @internal
   */
  off() {
    he = this.parent;
  }
  stop(t) {
    if (this._active) {
      this._active = !1;
      let s, n;
      for (s = 0, n = this.effects.length; s < n; s++)
        this.effects[s].stop();
      for (this.effects.length = 0, s = 0, n = this.cleanups.length; s < n; s++)
        this.cleanups[s]();
      if (this.cleanups.length = 0, this.scopes) {
        for (s = 0, n = this.scopes.length; s < n; s++)
          this.scopes[s].stop(!0);
        this.scopes.length = 0;
      }
      if (!this.detached && this.parent && !t) {
        const r = this.parent.scopes.pop();
        r && r !== this && (this.parent.scopes[this.index] = r, r.index = this.index);
      }
      this.parent = void 0;
    }
  }
}
function Si() {
  return he;
}
let U;
const ws = /* @__PURE__ */ new WeakSet();
class sr {
  constructor(t) {
    this.fn = t, this.deps = void 0, this.depsTail = void 0, this.flags = 5, this.next = void 0, this.cleanup = void 0, this.scheduler = void 0, he && he.active && he.effects.push(this);
  }
  pause() {
    this.flags |= 64;
  }
  resume() {
    this.flags & 64 && (this.flags &= -65, ws.has(this) && (ws.delete(this), this.trigger()));
  }
  /**
   * @internal
   */
  notify() {
    this.flags & 2 && !(this.flags & 32) || this.flags & 8 || rr(this);
  }
  run() {
    if (!(this.flags & 1))
      return this.fn();
    this.flags |= 2, _n(this), ir(this);
    const t = U, s = _e;
    U = this, _e = !0;
    try {
      return this.fn();
    } finally {
      or(this), U = t, _e = s, this.flags &= -3;
    }
  }
  stop() {
    if (this.flags & 1) {
      for (let t = this.deps; t; t = t.nextDep)
        Xs(t);
      this.deps = this.depsTail = void 0, _n(this), this.onStop && this.onStop(), this.flags &= -2;
    }
  }
  trigger() {
    this.flags & 64 ? ws.add(this) : this.scheduler ? this.scheduler() : this.runIfDirty();
  }
  /**
   * @internal
   */
  runIfDirty() {
    Rs(this) && this.run();
  }
  get dirty() {
    return Rs(this);
  }
}
let nr = 0, Ct, Et;
function rr(e, t = !1) {
  if (e.flags |= 8, t) {
    e.next = Et, Et = e;
    return;
  }
  e.next = Ct, Ct = e;
}
function zs() {
  nr++;
}
function Ys() {
  if (--nr > 0)
    return;
  if (Et) {
    let t = Et;
    for (Et = void 0; t; ) {
      const s = t.next;
      t.next = void 0, t.flags &= -9, t = s;
    }
  }
  let e;
  for (; Ct; ) {
    let t = Ct;
    for (Ct = void 0; t; ) {
      const s = t.next;
      if (t.next = void 0, t.flags &= -9, t.flags & 1)
        try {
          t.trigger();
        } catch (n) {
          e || (e = n);
        }
      t = s;
    }
  }
  if (e) throw e;
}
function ir(e) {
  for (let t = e.deps; t; t = t.nextDep)
    t.version = -1, t.prevActiveLink = t.dep.activeLink, t.dep.activeLink = t;
}
function or(e) {
  let t, s = e.depsTail, n = s;
  for (; n; ) {
    const r = n.prevDep;
    n.version === -1 ? (n === s && (s = r), Xs(n), Ii(n)) : t = n, n.dep.activeLink = n.prevActiveLink, n.prevActiveLink = void 0, n = r;
  }
  e.deps = t, e.depsTail = s;
}
function Rs(e) {
  for (let t = e.deps; t; t = t.nextDep)
    if (t.dep.version !== t.version || t.dep.computed && (lr(t.dep.computed) || t.dep.version !== t.version))
      return !0;
  return !!e._dirty;
}
function lr(e) {
  if (e.flags & 4 && !(e.flags & 16) || (e.flags &= -17, e.globalVersion === Rt))
    return;
  e.globalVersion = Rt;
  const t = e.dep;
  if (e.flags |= 2, t.version > 0 && !e.isSSR && e.deps && !Rs(e)) {
    e.flags &= -3;
    return;
  }
  const s = U, n = _e;
  U = e, _e = !0;
  try {
    ir(e);
    const r = e.fn(e._value);
    (t.version === 0 || Be(r, e._value)) && (e._value = r, t.version++);
  } catch (r) {
    throw t.version++, r;
  } finally {
    U = s, _e = n, or(e), e.flags &= -3;
  }
}
function Xs(e, t = !1) {
  const { dep: s, prevSub: n, nextSub: r } = e;
  if (n && (n.nextSub = r, e.prevSub = void 0), r && (r.prevSub = n, e.nextSub = void 0), s.subs === e && (s.subs = n, !n && s.computed)) {
    s.computed.flags &= -5;
    for (let i = s.computed.deps; i; i = i.nextDep)
      Xs(i, !0);
  }
  !t && !--s.sc && s.map && s.map.delete(s.key);
}
function Ii(e) {
  const { prevDep: t, nextDep: s } = e;
  t && (t.nextDep = s, e.prevDep = void 0), s && (s.prevDep = t, e.nextDep = void 0);
}
let _e = !0;
const cr = [];
function Ke() {
  cr.push(_e), _e = !1;
}
function Ge() {
  const e = cr.pop();
  _e = e === void 0 ? !0 : e;
}
function _n(e) {
  const { cleanup: t } = e;
  if (e.cleanup = void 0, t) {
    const s = U;
    U = void 0;
    try {
      t();
    } finally {
      U = s;
    }
  }
}
let Rt = 0;
class Ai {
  constructor(t, s) {
    this.sub = t, this.dep = s, this.version = s.version, this.nextDep = this.prevDep = this.nextSub = this.prevSub = this.prevActiveLink = void 0;
  }
}
class Zs {
  constructor(t) {
    this.computed = t, this.version = 0, this.activeLink = void 0, this.subs = void 0, this.map = void 0, this.key = void 0, this.sc = 0;
  }
  track(t) {
    if (!U || !_e || U === this.computed)
      return;
    let s = this.activeLink;
    if (s === void 0 || s.sub !== U)
      s = this.activeLink = new Ai(U, this), U.deps ? (s.prevDep = U.depsTail, U.depsTail.nextDep = s, U.depsTail = s) : U.deps = U.depsTail = s, ur(s);
    else if (s.version === -1 && (s.version = this.version, s.nextDep)) {
      const n = s.nextDep;
      n.prevDep = s.prevDep, s.prevDep && (s.prevDep.nextDep = n), s.prevDep = U.depsTail, s.nextDep = void 0, U.depsTail.nextDep = s, U.depsTail = s, U.deps === s && (U.deps = n);
    }
    return s;
  }
  trigger(t) {
    this.version++, Rt++, this.notify(t);
  }
  notify(t) {
    zs();
    try {
      for (let s = this.subs; s; s = s.prevSub)
        s.sub.notify() && s.sub.dep.notify();
    } finally {
      Ys();
    }
  }
}
function ur(e) {
  if (e.dep.sc++, e.sub.flags & 4) {
    const t = e.dep.computed;
    if (t && !e.dep.subs) {
      t.flags |= 20;
      for (let n = t.deps; n; n = n.nextDep)
        ur(n);
    }
    const s = e.dep.subs;
    s !== e && (e.prevSub = s, s && (s.nextSub = e)), e.dep.subs = e;
  }
}
const Ms = /* @__PURE__ */ new WeakMap(), st = Symbol(
  ""
), Ps = Symbol(
  ""
), Mt = Symbol(
  ""
);
function te(e, t, s) {
  if (_e && U) {
    let n = Ms.get(e);
    n || Ms.set(e, n = /* @__PURE__ */ new Map());
    let r = n.get(s);
    r || (n.set(s, r = new Zs()), r.map = n, r.key = s), r.track();
  }
}
function Me(e, t, s, n, r, i) {
  const o = Ms.get(e);
  if (!o) {
    Rt++;
    return;
  }
  const l = (u) => {
    u && u.trigger();
  };
  if (zs(), t === "clear")
    o.forEach(l);
  else {
    const u = O(e), f = u && Js(s);
    if (u && s === "length") {
      const d = Number(n);
      o.forEach((p, m) => {
        (m === "length" || m === Mt || !Ue(m) && m >= d) && l(p);
      });
    } else
      switch ((s !== void 0 || o.has(void 0)) && l(o.get(s)), f && l(o.get(Mt)), t) {
        case "add":
          u ? f && l(o.get("length")) : (l(o.get(st)), ft(e) && l(o.get(Ps)));
          break;
        case "delete":
          u || (l(o.get(st)), ft(e) && l(o.get(Ps)));
          break;
        case "set":
          ft(e) && l(o.get(st));
          break;
      }
  }
  Ys();
}
function lt(e) {
  const t = N(e);
  return t === e ? t : (te(t, "iterate", Mt), me(e) ? t : t.map(se));
}
function as(e) {
  return te(e = N(e), "iterate", Mt), e;
}
const Ci = {
  __proto__: null,
  [Symbol.iterator]() {
    return ys(this, Symbol.iterator, se);
  },
  concat(...e) {
    return lt(this).concat(
      ...e.map((t) => O(t) ? lt(t) : t)
    );
  },
  entries() {
    return ys(this, "entries", (e) => (e[1] = se(e[1]), e));
  },
  every(e, t) {
    return Oe(this, "every", e, t, void 0, arguments);
  },
  filter(e, t) {
    return Oe(this, "filter", e, t, (s) => s.map(se), arguments);
  },
  find(e, t) {
    return Oe(this, "find", e, t, se, arguments);
  },
  findIndex(e, t) {
    return Oe(this, "findIndex", e, t, void 0, arguments);
  },
  findLast(e, t) {
    return Oe(this, "findLast", e, t, se, arguments);
  },
  findLastIndex(e, t) {
    return Oe(this, "findLastIndex", e, t, void 0, arguments);
  },
  // flat, flatMap could benefit from ARRAY_ITERATE but are not straight-forward to implement
  forEach(e, t) {
    return Oe(this, "forEach", e, t, void 0, arguments);
  },
  includes(...e) {
    return xs(this, "includes", e);
  },
  indexOf(...e) {
    return xs(this, "indexOf", e);
  },
  join(e) {
    return lt(this).join(e);
  },
  // keys() iterator only reads `length`, no optimisation required
  lastIndexOf(...e) {
    return xs(this, "lastIndexOf", e);
  },
  map(e, t) {
    return Oe(this, "map", e, t, void 0, arguments);
  },
  pop() {
    return wt(this, "pop");
  },
  push(...e) {
    return wt(this, "push", e);
  },
  reduce(e, ...t) {
    return bn(this, "reduce", e, t);
  },
  reduceRight(e, ...t) {
    return bn(this, "reduceRight", e, t);
  },
  shift() {
    return wt(this, "shift");
  },
  // slice could use ARRAY_ITERATE but also seems to beg for range tracking
  some(e, t) {
    return Oe(this, "some", e, t, void 0, arguments);
  },
  splice(...e) {
    return wt(this, "splice", e);
  },
  toReversed() {
    return lt(this).toReversed();
  },
  toSorted(e) {
    return lt(this).toSorted(e);
  },
  toSpliced(...e) {
    return lt(this).toSpliced(...e);
  },
  unshift(...e) {
    return wt(this, "unshift", e);
  },
  values() {
    return ys(this, "values", se);
  }
};
function ys(e, t, s) {
  const n = as(e), r = n[t]();
  return n !== e && !me(e) && (r._next = r.next, r.next = () => {
    const i = r._next();
    return i.value && (i.value = s(i.value)), i;
  }), r;
}
const Ei = Array.prototype;
function Oe(e, t, s, n, r, i) {
  const o = as(e), l = o !== e && !me(e), u = o[t];
  if (u !== Ei[t]) {
    const p = u.apply(e, i);
    return l ? se(p) : p;
  }
  let f = s;
  o !== e && (l ? f = function(p, m) {
    return s.call(this, se(p), m, e);
  } : s.length > 2 && (f = function(p, m) {
    return s.call(this, p, m, e);
  }));
  const d = u.call(o, f, n);
  return l && r ? r(d) : d;
}
function bn(e, t, s, n) {
  const r = as(e);
  let i = s;
  return r !== e && (me(e) ? s.length > 3 && (i = function(o, l, u) {
    return s.call(this, o, l, u, e);
  }) : i = function(o, l, u) {
    return s.call(this, o, se(l), u, e);
  }), r[t](i, ...n);
}
function xs(e, t, s) {
  const n = N(e);
  te(n, "iterate", Mt);
  const r = n[t](...s);
  return (r === -1 || r === !1) && sn(s[0]) ? (s[0] = N(s[0]), n[t](...s)) : r;
}
function wt(e, t, s = []) {
  Ke(), zs();
  const n = N(e)[t].apply(e, s);
  return Ys(), Ge(), n;
}
const $i = /* @__PURE__ */ Ks("__proto__,__v_isRef,__isVue"), ar = new Set(
  /* @__PURE__ */ Object.getOwnPropertyNames(Symbol).filter((e) => e !== "arguments" && e !== "caller").map((e) => Symbol[e]).filter(Ue)
);
function Ti(e) {
  Ue(e) || (e = String(e));
  const t = N(this);
  return te(t, "has", e), t.hasOwnProperty(e);
}
class fr {
  constructor(t = !1, s = !1) {
    this._isReadonly = t, this._isShallow = s;
  }
  get(t, s, n) {
    if (s === "__v_skip") return t.__v_skip;
    const r = this._isReadonly, i = this._isShallow;
    if (s === "__v_isReactive")
      return !r;
    if (s === "__v_isReadonly")
      return r;
    if (s === "__v_isShallow")
      return i;
    if (s === "__v_raw")
      return n === (r ? i ? Hi : gr : i ? pr : hr).get(t) || // receiver is not the reactive proxy, but has the same prototype
      // this means the receiver is a user proxy of the reactive proxy
      Object.getPrototypeOf(t) === Object.getPrototypeOf(n) ? t : void 0;
    const o = O(t);
    if (!r) {
      let u;
      if (o && (u = Ci[s]))
        return u;
      if (s === "hasOwnProperty")
        return Ti;
    }
    const l = Reflect.get(
      t,
      s,
      // if this is a proxy wrapping a ref, return methods using the raw ref
      // as receiver so that we don't have to call `toRaw` on the ref in all
      // its class methods
      ne(t) ? t : n
    );
    return (Ue(s) ? ar.has(s) : $i(s)) || (r || te(t, "get", s), i) ? l : ne(l) ? o && Js(s) ? l : l.value : J(l) ? r ? mr(l) : en(l) : l;
  }
}
class dr extends fr {
  constructor(t = !1) {
    super(!1, t);
  }
  set(t, s, n, r) {
    let i = t[s];
    if (!this._isShallow) {
      const u = rt(i);
      if (!me(n) && !rt(n) && (i = N(i), n = N(n)), !O(t) && ne(i) && !ne(n))
        return u ? !1 : (i.value = n, !0);
    }
    const o = O(t) && Js(s) ? Number(s) < t.length : k(t, s), l = Reflect.set(
      t,
      s,
      n,
      ne(t) ? t : r
    );
    return t === N(r) && (o ? Be(n, i) && Me(t, "set", s, n) : Me(t, "add", s, n)), l;
  }
  deleteProperty(t, s) {
    const n = k(t, s);
    t[s];
    const r = Reflect.deleteProperty(t, s);
    return r && n && Me(t, "delete", s, void 0), r;
  }
  has(t, s) {
    const n = Reflect.has(t, s);
    return (!Ue(s) || !ar.has(s)) && te(t, "has", s), n;
  }
  ownKeys(t) {
    return te(
      t,
      "iterate",
      O(t) ? "length" : st
    ), Reflect.ownKeys(t);
  }
}
class Oi extends fr {
  constructor(t = !1) {
    super(!0, t);
  }
  set(t, s) {
    return !0;
  }
  deleteProperty(t, s) {
    return !0;
  }
}
const Ri = /* @__PURE__ */ new dr(), Mi = /* @__PURE__ */ new Oi(), Pi = /* @__PURE__ */ new dr(!0);
const Ds = (e) => e, Vt = (e) => Reflect.getPrototypeOf(e);
function Di(e, t, s) {
  return function(...n) {
    const r = this.__v_raw, i = N(r), o = ft(i), l = e === "entries" || e === Symbol.iterator && o, u = e === "keys" && o, f = r[e](...n), d = s ? Ds : t ? Fs : se;
    return !t && te(
      i,
      "iterate",
      u ? Ps : st
    ), {
      // iterator protocol
      next() {
        const { value: p, done: m } = f.next();
        return m ? { value: p, done: m } : {
          value: l ? [d(p[0]), d(p[1])] : d(p),
          done: m
        };
      },
      // iterable protocol
      [Symbol.iterator]() {
        return this;
      }
    };
  };
}
function Kt(e) {
  return function(...t) {
    return e === "delete" ? !1 : e === "clear" ? void 0 : this;
  };
}
function Fi(e, t) {
  const s = {
    get(r) {
      const i = this.__v_raw, o = N(i), l = N(r);
      e || (Be(r, l) && te(o, "get", r), te(o, "get", l));
      const { has: u } = Vt(o), f = t ? Ds : e ? Fs : se;
      if (u.call(o, r))
        return f(i.get(r));
      if (u.call(o, l))
        return f(i.get(l));
      i !== o && i.get(r);
    },
    get size() {
      const r = this.__v_raw;
      return !e && te(N(r), "iterate", st), Reflect.get(r, "size", r);
    },
    has(r) {
      const i = this.__v_raw, o = N(i), l = N(r);
      return e || (Be(r, l) && te(o, "has", r), te(o, "has", l)), r === l ? i.has(r) : i.has(r) || i.has(l);
    },
    forEach(r, i) {
      const o = this, l = o.__v_raw, u = N(l), f = t ? Ds : e ? Fs : se;
      return !e && te(u, "iterate", st), l.forEach((d, p) => r.call(i, f(d), f(p), o));
    }
  };
  return re(
    s,
    e ? {
      add: Kt("add"),
      set: Kt("set"),
      delete: Kt("delete"),
      clear: Kt("clear")
    } : {
      add(r) {
        !t && !me(r) && !rt(r) && (r = N(r));
        const i = N(this);
        return Vt(i).has.call(i, r) || (i.add(r), Me(i, "add", r, r)), this;
      },
      set(r, i) {
        !t && !me(i) && !rt(i) && (i = N(i));
        const o = N(this), { has: l, get: u } = Vt(o);
        let f = l.call(o, r);
        f || (r = N(r), f = l.call(o, r));
        const d = u.call(o, r);
        return o.set(r, i), f ? Be(i, d) && Me(o, "set", r, i) : Me(o, "add", r, i), this;
      },
      delete(r) {
        const i = N(this), { has: o, get: l } = Vt(i);
        let u = o.call(i, r);
        u || (r = N(r), u = o.call(i, r)), l && l.call(i, r);
        const f = i.delete(r);
        return u && Me(i, "delete", r, void 0), f;
      },
      clear() {
        const r = N(this), i = r.size !== 0, o = r.clear();
        return i && Me(
          r,
          "clear",
          void 0,
          void 0
        ), o;
      }
    }
  ), [
    "keys",
    "values",
    "entries",
    Symbol.iterator
  ].forEach((r) => {
    s[r] = Di(r, e, t);
  }), s;
}
function Qs(e, t) {
  const s = Fi(e, t);
  return (n, r, i) => r === "__v_isReactive" ? !e : r === "__v_isReadonly" ? e : r === "__v_raw" ? n : Reflect.get(
    k(s, r) && r in n ? s : n,
    r,
    i
  );
}
const Ni = {
  get: /* @__PURE__ */ Qs(!1, !1)
}, ki = {
  get: /* @__PURE__ */ Qs(!1, !0)
}, Li = {
  get: /* @__PURE__ */ Qs(!0, !1)
};
const hr = /* @__PURE__ */ new WeakMap(), pr = /* @__PURE__ */ new WeakMap(), gr = /* @__PURE__ */ new WeakMap(), Hi = /* @__PURE__ */ new WeakMap();
function ji(e) {
  switch (e) {
    case "Object":
    case "Array":
      return 1;
    case "Map":
    case "Set":
    case "WeakMap":
    case "WeakSet":
      return 2;
    default:
      return 0;
  }
}
function Bi(e) {
  return e.__v_skip || !Object.isExtensible(e) ? 0 : ji(di(e));
}
function en(e) {
  return rt(e) ? e : tn(
    e,
    !1,
    Ri,
    Ni,
    hr
  );
}
function Wi(e) {
  return tn(
    e,
    !1,
    Pi,
    ki,
    pr
  );
}
function mr(e) {
  return tn(
    e,
    !0,
    Mi,
    Li,
    gr
  );
}
function tn(e, t, s, n, r) {
  if (!J(e) || e.__v_raw && !(t && e.__v_isReactive))
    return e;
  const i = r.get(e);
  if (i)
    return i;
  const o = Bi(e);
  if (o === 0)
    return e;
  const l = new Proxy(
    e,
    o === 2 ? n : s
  );
  return r.set(e, l), l;
}
function dt(e) {
  return rt(e) ? dt(e.__v_raw) : !!(e && e.__v_isReactive);
}
function rt(e) {
  return !!(e && e.__v_isReadonly);
}
function me(e) {
  return !!(e && e.__v_isShallow);
}
function sn(e) {
  return e ? !!e.__v_raw : !1;
}
function N(e) {
  const t = e && e.__v_raw;
  return t ? N(t) : e;
}
function Ui(e) {
  return !k(e, "__v_skip") && Object.isExtensible(e) && Zn(e, "__v_skip", !0), e;
}
const se = (e) => J(e) ? en(e) : e, Fs = (e) => J(e) ? mr(e) : e;
function ne(e) {
  return e ? e.__v_isRef === !0 : !1;
}
function et(e) {
  return _r(e, !1);
}
function Vi(e) {
  return _r(e, !0);
}
function _r(e, t) {
  return ne(e) ? e : new Ki(e, t);
}
class Ki {
  constructor(t, s) {
    this.dep = new Zs(), this.__v_isRef = !0, this.__v_isShallow = !1, this._rawValue = s ? t : N(t), this._value = s ? t : se(t), this.__v_isShallow = s;
  }
  get value() {
    return this.dep.track(), this._value;
  }
  set value(t) {
    const s = this._rawValue, n = this.__v_isShallow || me(t) || rt(t);
    t = n ? t : N(t), Be(t, s) && (this._rawValue = t, this._value = n ? t : se(t), this.dep.trigger());
  }
}
function He(e) {
  return ne(e) ? e.value : e;
}
const Gi = {
  get: (e, t, s) => t === "__v_raw" ? e : He(Reflect.get(e, t, s)),
  set: (e, t, s, n) => {
    const r = e[t];
    return ne(r) && !ne(s) ? (r.value = s, !0) : Reflect.set(e, t, s, n);
  }
};
function br(e) {
  return dt(e) ? e : new Proxy(e, Gi);
}
class qi {
  constructor(t, s, n) {
    this.fn = t, this.setter = s, this._value = void 0, this.dep = new Zs(this), this.__v_isRef = !0, this.deps = void 0, this.depsTail = void 0, this.flags = 16, this.globalVersion = Rt - 1, this.next = void 0, this.effect = this, this.__v_isReadonly = !s, this.isSSR = n;
  }
  /**
   * @internal
   */
  notify() {
    if (this.flags |= 16, !(this.flags & 8) && // avoid infinite self recursion
    U !== this)
      return rr(this, !0), !0;
  }
  get value() {
    const t = this.dep.track();
    return lr(this), t && (t.version = this.dep.version), this._value;
  }
  set value(t) {
    this.setter && this.setter(t);
  }
}
function Ji(e, t, s = !1) {
  let n, r;
  return M(e) ? n = e : (n = e.get, r = e.set), new qi(n, r, s);
}
const Gt = {}, Zt = /* @__PURE__ */ new WeakMap();
let Qe;
function zi(e, t = !1, s = Qe) {
  if (s) {
    let n = Zt.get(s);
    n || Zt.set(s, n = []), n.push(e);
  }
}
function Yi(e, t, s = V) {
  const { immediate: n, deep: r, once: i, scheduler: o, augmentJob: l, call: u } = s, f = ($) => r ? $ : me($) || r === !1 || r === 0 ? je($, 1) : je($);
  let d, p, m, x, R = !1, C = !1;
  if (ne(e) ? (p = () => e.value, R = me(e)) : dt(e) ? (p = () => f(e), R = !0) : O(e) ? (C = !0, R = e.some(($) => dt($) || me($)), p = () => e.map(($) => {
    if (ne($))
      return $.value;
    if (dt($))
      return f($);
    if (M($))
      return u ? u($, 2) : $();
  })) : M(e) ? t ? p = u ? () => u(e, 2) : e : p = () => {
    if (m) {
      Ke();
      try {
        m();
      } finally {
        Ge();
      }
    }
    const $ = Qe;
    Qe = d;
    try {
      return u ? u(e, 3, [x]) : e(x);
    } finally {
      Qe = $;
    }
  } : p = $e, t && r) {
    const $ = p, Q = r === !0 ? 1 / 0 : r;
    p = () => je($(), Q);
  }
  const G = Si(), D = () => {
    d.stop(), G && G.active && qs(G.effects, d);
  };
  if (i && t) {
    const $ = t;
    t = (...Q) => {
      $(...Q), D();
    };
  }
  let z = C ? new Array(e.length).fill(Gt) : Gt;
  const Y = ($) => {
    if (!(!(d.flags & 1) || !d.dirty && !$))
      if (t) {
        const Q = d.run();
        if (r || R || (C ? Q.some((Fe, ve) => Be(Fe, z[ve])) : Be(Q, z))) {
          m && m();
          const Fe = Qe;
          Qe = d;
          try {
            const ve = [
              Q,
              // pass undefined as the old value when it's changed for the first time
              z === Gt ? void 0 : C && z[0] === Gt ? [] : z,
              x
            ];
            u ? u(t, 3, ve) : (
              // @ts-expect-error
              t(...ve)
            ), z = Q;
          } finally {
            Qe = Fe;
          }
        }
      } else
        d.run();
  };
  return l && l(Y), d = new sr(p), d.scheduler = o ? () => o(Y, !1) : Y, x = ($) => zi($, !1, d), m = d.onStop = () => {
    const $ = Zt.get(d);
    if ($) {
      if (u)
        u($, 4);
      else
        for (const Q of $) Q();
      Zt.delete(d);
    }
  }, t ? n ? Y(!0) : z = d.run() : o ? o(Y.bind(null, !0), !0) : d.run(), D.pause = d.pause.bind(d), D.resume = d.resume.bind(d), D.stop = D, D;
}
function je(e, t = 1 / 0, s) {
  if (t <= 0 || !J(e) || e.__v_skip || (s = s || /* @__PURE__ */ new Set(), s.has(e)))
    return e;
  if (s.add(e), t--, ne(e))
    je(e.value, t, s);
  else if (O(e))
    for (let n = 0; n < e.length; n++)
      je(e[n], t, s);
  else if (qn(e) || ft(e))
    e.forEach((n) => {
      je(n, t, s);
    });
  else if (Yn(e)) {
    for (const n in e)
      je(e[n], t, s);
    for (const n of Object.getOwnPropertySymbols(e))
      Object.prototype.propertyIsEnumerable.call(e, n) && je(e[n], t, s);
  }
  return e;
}
/**
* @vue/runtime-core v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
function kt(e, t, s, n) {
  try {
    return n ? e(...n) : e();
  } catch (r) {
    fs(r, t, s);
  }
}
function Te(e, t, s, n) {
  if (M(e)) {
    const r = kt(e, t, s, n);
    return r && Jn(r) && r.catch((i) => {
      fs(i, t, s);
    }), r;
  }
  if (O(e)) {
    const r = [];
    for (let i = 0; i < e.length; i++)
      r.push(Te(e[i], t, s, n));
    return r;
  }
}
function fs(e, t, s, n = !0) {
  const r = t ? t.vnode : null, { errorHandler: i, throwUnhandledErrorInProduction: o } = t && t.appContext.config || V;
  if (t) {
    let l = t.parent;
    const u = t.proxy, f = `https://vuejs.org/error-reference/#runtime-${s}`;
    for (; l; ) {
      const d = l.ec;
      if (d) {
        for (let p = 0; p < d.length; p++)
          if (d[p](e, u, f) === !1)
            return;
      }
      l = l.parent;
    }
    if (i) {
      Ke(), kt(i, null, 10, [
        e,
        u,
        f
      ]), Ge();
      return;
    }
  }
  Xi(e, s, r, n, o);
}
function Xi(e, t, s, n = !0, r = !1) {
  if (r)
    throw e;
  console.error(e);
}
const le = [];
let Ae = -1;
const ht = [];
let ke = null, ct = 0;
const vr = /* @__PURE__ */ Promise.resolve();
let Qt = null;
function wr(e) {
  const t = Qt || vr;
  return e ? t.then(this ? e.bind(this) : e) : t;
}
function Zi(e) {
  let t = Ae + 1, s = le.length;
  for (; t < s; ) {
    const n = t + s >>> 1, r = le[n], i = Pt(r);
    i < e || i === e && r.flags & 2 ? t = n + 1 : s = n;
  }
  return t;
}
function nn(e) {
  if (!(e.flags & 1)) {
    const t = Pt(e), s = le[le.length - 1];
    !s || // fast path when the job id is larger than the tail
    !(e.flags & 2) && t >= Pt(s) ? le.push(e) : le.splice(Zi(t), 0, e), e.flags |= 1, yr();
  }
}
function yr() {
  Qt || (Qt = vr.then(Sr));
}
function Qi(e) {
  O(e) ? ht.push(...e) : ke && e.id === -1 ? ke.splice(ct + 1, 0, e) : e.flags & 1 || (ht.push(e), e.flags |= 1), yr();
}
function vn(e, t, s = Ae + 1) {
  for (; s < le.length; s++) {
    const n = le[s];
    if (n && n.flags & 2) {
      if (e && n.id !== e.uid)
        continue;
      le.splice(s, 1), s--, n.flags & 4 && (n.flags &= -2), n(), n.flags & 4 || (n.flags &= -2);
    }
  }
}
function xr(e) {
  if (ht.length) {
    const t = [...new Set(ht)].sort(
      (s, n) => Pt(s) - Pt(n)
    );
    if (ht.length = 0, ke) {
      ke.push(...t);
      return;
    }
    for (ke = t, ct = 0; ct < ke.length; ct++) {
      const s = ke[ct];
      s.flags & 4 && (s.flags &= -2), s.flags & 8 || s(), s.flags &= -2;
    }
    ke = null, ct = 0;
  }
}
const Pt = (e) => e.id == null ? e.flags & 2 ? -1 : 1 / 0 : e.id;
function Sr(e) {
  try {
    for (Ae = 0; Ae < le.length; Ae++) {
      const t = le[Ae];
      t && !(t.flags & 8) && (t.flags & 4 && (t.flags &= -2), kt(
        t,
        t.i,
        t.i ? 15 : 14
      ), t.flags & 4 || (t.flags &= -2));
    }
  } finally {
    for (; Ae < le.length; Ae++) {
      const t = le[Ae];
      t && (t.flags &= -2);
    }
    Ae = -1, le.length = 0, xr(), Qt = null, (le.length || ht.length) && Sr();
  }
}
let Ee = null, Ir = null;
function es(e) {
  const t = Ee;
  return Ee = e, Ir = e && e.type.__scopeId || null, t;
}
function eo(e, t = Ee, s) {
  if (!t || e._n)
    return e;
  const n = (...r) => {
    n._d && $n(-1);
    const i = es(t);
    let o;
    try {
      o = e(...r);
    } finally {
      es(i), n._d && $n(1);
    }
    return o;
  };
  return n._n = !0, n._c = !0, n._d = !0, n;
}
function Xe(e, t, s, n) {
  const r = e.dirs, i = t && t.dirs;
  for (let o = 0; o < r.length; o++) {
    const l = r[o];
    i && (l.oldValue = i[o].value);
    let u = l.dir[n];
    u && (Ke(), Te(u, s, 8, [
      e.el,
      l,
      e,
      t
    ]), Ge());
  }
}
const to = Symbol("_vte"), so = (e) => e.__isTeleport;
function rn(e, t) {
  e.shapeFlag & 6 && e.component ? (e.transition = t, rn(e.component.subTree, t)) : e.shapeFlag & 128 ? (e.ssContent.transition = t.clone(e.ssContent), e.ssFallback.transition = t.clone(e.ssFallback)) : e.transition = t;
}
/*! #__NO_SIDE_EFFECTS__ */
// @__NO_SIDE_EFFECTS__
function qe(e, t) {
  return M(e) ? (
    // #8236: extend call and options.name access are considered side-effects
    // by Rollup, so we have to wrap it in a pure-annotated IIFE.
    re({ name: e.name }, t, { setup: e })
  ) : e;
}
function Ar(e) {
  e.ids = [e.ids[0] + e.ids[2]++ + "-", 0, 0];
}
function ts(e, t, s, n, r = !1) {
  if (O(e)) {
    e.forEach(
      (R, C) => ts(
        R,
        t && (O(t) ? t[C] : t),
        s,
        n,
        r
      )
    );
    return;
  }
  if ($t(n) && !r) {
    n.shapeFlag & 512 && n.type.__asyncResolved && n.component.subTree.component && ts(e, t, s, n.component.subTree);
    return;
  }
  const i = n.shapeFlag & 4 ? un(n.component) : n.el, o = r ? null : i, { i: l, r: u } = e, f = t && t.r, d = l.refs === V ? l.refs = {} : l.refs, p = l.setupState, m = N(p), x = p === V ? () => !1 : (R) => k(m, R);
  if (f != null && f !== u && (Z(f) ? (d[f] = null, x(f) && (p[f] = null)) : ne(f) && (f.value = null)), M(u))
    kt(u, l, 12, [o, d]);
  else {
    const R = Z(u), C = ne(u);
    if (R || C) {
      const G = () => {
        if (e.f) {
          const D = R ? x(u) ? p[u] : d[u] : u.value;
          r ? O(D) && qs(D, i) : O(D) ? D.includes(i) || D.push(i) : R ? (d[u] = [i], x(u) && (p[u] = d[u])) : (u.value = [i], e.k && (d[e.k] = u.value));
        } else R ? (d[u] = o, x(u) && (p[u] = o)) : C && (u.value = o, e.k && (d[e.k] = o));
      };
      o ? (G.id = -1, de(G, s)) : G();
    }
  }
}
us().requestIdleCallback;
us().cancelIdleCallback;
const $t = (e) => !!e.type.__asyncLoader, Cr = (e) => e.type.__isKeepAlive;
function no(e, t) {
  Er(e, "a", t);
}
function ro(e, t) {
  Er(e, "da", t);
}
function Er(e, t, s = ce) {
  const n = e.__wdc || (e.__wdc = () => {
    let r = s;
    for (; r; ) {
      if (r.isDeactivated)
        return;
      r = r.parent;
    }
    return e();
  });
  if (ds(t, n, s), s) {
    let r = s.parent;
    for (; r && r.parent; )
      Cr(r.parent.vnode) && io(n, t, s, r), r = r.parent;
  }
}
function io(e, t, s, n) {
  const r = ds(
    t,
    e,
    n,
    !0
    /* prepend */
  );
  Tr(() => {
    qs(n[t], r);
  }, s);
}
function ds(e, t, s = ce, n = !1) {
  if (s) {
    const r = s[e] || (s[e] = []), i = t.__weh || (t.__weh = (...o) => {
      Ke();
      const l = Lt(s), u = Te(t, s, e, o);
      return l(), Ge(), u;
    });
    return n ? r.unshift(i) : r.push(i), i;
  }
}
const De = (e) => (t, s = ce) => {
  (!Ft || e === "sp") && ds(e, (...n) => t(...n), s);
}, oo = De("bm"), $r = De("m"), lo = De(
  "bu"
), co = De("u"), on = De(
  "bum"
), Tr = De("um"), uo = De(
  "sp"
), ao = De("rtg"), fo = De("rtc");
function Or(e, t = ce) {
  ds("ec", e, t);
}
const ho = Symbol.for("v-ndc");
function ut(e, t, s, n) {
  let r;
  const i = s, o = O(e);
  if (o || Z(e)) {
    const l = o && dt(e);
    let u = !1;
    l && (u = !me(e), e = as(e)), r = new Array(e.length);
    for (let f = 0, d = e.length; f < d; f++)
      r[f] = t(
        u ? se(e[f]) : e[f],
        f,
        void 0,
        i
      );
  } else if (typeof e == "number") {
    r = new Array(e);
    for (let l = 0; l < e; l++)
      r[l] = t(l + 1, l, void 0, i);
  } else if (J(e))
    if (e[Symbol.iterator])
      r = Array.from(
        e,
        (l, u) => t(l, u, void 0, i)
      );
    else {
      const l = Object.keys(e);
      r = new Array(l.length);
      for (let u = 0, f = l.length; u < f; u++) {
        const d = l[u];
        r[u] = t(e[d], d, u, i);
      }
    }
  else
    r = [];
  return r;
}
const Ns = (e) => e ? Zr(e) ? un(e) : Ns(e.parent) : null, Tt = (
  // Move PURE marker to new line to workaround compiler discarding it
  // due to type annotation
  /* @__PURE__ */ re(/* @__PURE__ */ Object.create(null), {
    $: (e) => e,
    $el: (e) => e.vnode.el,
    $data: (e) => e.data,
    $props: (e) => e.props,
    $attrs: (e) => e.attrs,
    $slots: (e) => e.slots,
    $refs: (e) => e.refs,
    $parent: (e) => Ns(e.parent),
    $root: (e) => Ns(e.root),
    $host: (e) => e.ce,
    $emit: (e) => e.emit,
    $options: (e) => Mr(e),
    $forceUpdate: (e) => e.f || (e.f = () => {
      nn(e.update);
    }),
    $nextTick: (e) => e.n || (e.n = wr.bind(e.proxy)),
    $watch: (e) => Fo.bind(e)
  })
), Ss = (e, t) => e !== V && !e.__isScriptSetup && k(e, t), po = {
  get({ _: e }, t) {
    if (t === "__v_skip")
      return !0;
    const { ctx: s, setupState: n, data: r, props: i, accessCache: o, type: l, appContext: u } = e;
    let f;
    if (t[0] !== "$") {
      const x = o[t];
      if (x !== void 0)
        switch (x) {
          case 1:
            return n[t];
          case 2:
            return r[t];
          case 4:
            return s[t];
          case 3:
            return i[t];
        }
      else {
        if (Ss(n, t))
          return o[t] = 1, n[t];
        if (r !== V && k(r, t))
          return o[t] = 2, r[t];
        if (
          // only cache other properties when instance has declared (thus stable)
          // props
          (f = e.propsOptions[0]) && k(f, t)
        )
          return o[t] = 3, i[t];
        if (s !== V && k(s, t))
          return o[t] = 4, s[t];
        ks && (o[t] = 0);
      }
    }
    const d = Tt[t];
    let p, m;
    if (d)
      return t === "$attrs" && te(e.attrs, "get", ""), d(e);
    if (
      // css module (injected by vue-loader)
      (p = l.__cssModules) && (p = p[t])
    )
      return p;
    if (s !== V && k(s, t))
      return o[t] = 4, s[t];
    if (
      // global properties
      m = u.config.globalProperties, k(m, t)
    )
      return m[t];
  },
  set({ _: e }, t, s) {
    const { data: n, setupState: r, ctx: i } = e;
    return Ss(r, t) ? (r[t] = s, !0) : n !== V && k(n, t) ? (n[t] = s, !0) : k(e.props, t) || t[0] === "$" && t.slice(1) in e ? !1 : (i[t] = s, !0);
  },
  has({
    _: { data: e, setupState: t, accessCache: s, ctx: n, appContext: r, propsOptions: i }
  }, o) {
    let l;
    return !!s[o] || e !== V && k(e, o) || Ss(t, o) || (l = i[0]) && k(l, o) || k(n, o) || k(Tt, o) || k(r.config.globalProperties, o);
  },
  defineProperty(e, t, s) {
    return s.get != null ? e._.accessCache[t] = 0 : k(s, "value") && this.set(e, t, s.value, null), Reflect.defineProperty(e, t, s);
  }
};
function wn(e) {
  return O(e) ? e.reduce(
    (t, s) => (t[s] = null, t),
    {}
  ) : e;
}
let ks = !0;
function go(e) {
  const t = Mr(e), s = e.proxy, n = e.ctx;
  ks = !1, t.beforeCreate && yn(t.beforeCreate, e, "bc");
  const {
    // state
    data: r,
    computed: i,
    methods: o,
    watch: l,
    provide: u,
    inject: f,
    // lifecycle
    created: d,
    beforeMount: p,
    mounted: m,
    beforeUpdate: x,
    updated: R,
    activated: C,
    deactivated: G,
    beforeDestroy: D,
    beforeUnmount: z,
    destroyed: Y,
    unmounted: $,
    render: Q,
    renderTracked: Fe,
    renderTriggered: ve,
    errorCaptured: Ne,
    serverPrefetch: Ht,
    // public API
    expose: Je,
    inheritAttrs: mt,
    // assets
    components: jt,
    directives: Bt,
    filters: gs
  } = t;
  if (f && mo(f, n, null), o)
    for (const q in o) {
      const B = o[q];
      M(B) && (n[q] = B.bind(s));
    }
  if (r) {
    const q = r.call(s, s);
    J(q) && (e.data = en(q));
  }
  if (ks = !0, i)
    for (const q in i) {
      const B = i[q], ze = M(B) ? B.bind(s, s) : M(B.get) ? B.get.bind(s, s) : $e, Wt = !M(B) && M(B.set) ? B.set.bind(s) : $e, Ye = nt({
        get: ze,
        set: Wt
      });
      Object.defineProperty(n, q, {
        enumerable: !0,
        configurable: !0,
        get: () => Ye.value,
        set: (we) => Ye.value = we
      });
    }
  if (l)
    for (const q in l)
      Rr(l[q], n, s, q);
  if (u) {
    const q = M(u) ? u.call(s) : u;
    Reflect.ownKeys(q).forEach((B) => {
      xo(B, q[B]);
    });
  }
  d && yn(d, e, "c");
  function ie(q, B) {
    O(B) ? B.forEach((ze) => q(ze.bind(s))) : B && q(B.bind(s));
  }
  if (ie(oo, p), ie($r, m), ie(lo, x), ie(co, R), ie(no, C), ie(ro, G), ie(Or, Ne), ie(fo, Fe), ie(ao, ve), ie(on, z), ie(Tr, $), ie(uo, Ht), O(Je))
    if (Je.length) {
      const q = e.exposed || (e.exposed = {});
      Je.forEach((B) => {
        Object.defineProperty(q, B, {
          get: () => s[B],
          set: (ze) => s[B] = ze
        });
      });
    } else e.exposed || (e.exposed = {});
  Q && e.render === $e && (e.render = Q), mt != null && (e.inheritAttrs = mt), jt && (e.components = jt), Bt && (e.directives = Bt), Ht && Ar(e);
}
function mo(e, t, s = $e) {
  O(e) && (e = Ls(e));
  for (const n in e) {
    const r = e[n];
    let i;
    J(r) ? "default" in r ? i = Jt(
      r.from || n,
      r.default,
      !0
    ) : i = Jt(r.from || n) : i = Jt(r), ne(i) ? Object.defineProperty(t, n, {
      enumerable: !0,
      configurable: !0,
      get: () => i.value,
      set: (o) => i.value = o
    }) : t[n] = i;
  }
}
function yn(e, t, s) {
  Te(
    O(e) ? e.map((n) => n.bind(t.proxy)) : e.bind(t.proxy),
    t,
    s
  );
}
function Rr(e, t, s, n) {
  let r = n.includes(".") ? Gr(s, n) : () => s[n];
  if (Z(e)) {
    const i = t[e];
    M(i) && zt(r, i);
  } else if (M(e))
    zt(r, e.bind(s));
  else if (J(e))
    if (O(e))
      e.forEach((i) => Rr(i, t, s, n));
    else {
      const i = M(e.handler) ? e.handler.bind(s) : t[e.handler];
      M(i) && zt(r, i, e);
    }
}
function Mr(e) {
  const t = e.type, { mixins: s, extends: n } = t, {
    mixins: r,
    optionsCache: i,
    config: { optionMergeStrategies: o }
  } = e.appContext, l = i.get(t);
  let u;
  return l ? u = l : !r.length && !s && !n ? u = t : (u = {}, r.length && r.forEach(
    (f) => ss(u, f, o, !0)
  ), ss(u, t, o)), J(t) && i.set(t, u), u;
}
function ss(e, t, s, n = !1) {
  const { mixins: r, extends: i } = t;
  i && ss(e, i, s, !0), r && r.forEach(
    (o) => ss(e, o, s, !0)
  );
  for (const o in t)
    if (!(n && o === "expose")) {
      const l = _o[o] || s && s[o];
      e[o] = l ? l(e[o], t[o]) : t[o];
    }
  return e;
}
const _o = {
  data: xn,
  props: Sn,
  emits: Sn,
  // objects
  methods: xt,
  computed: xt,
  // lifecycle
  beforeCreate: oe,
  created: oe,
  beforeMount: oe,
  mounted: oe,
  beforeUpdate: oe,
  updated: oe,
  beforeDestroy: oe,
  beforeUnmount: oe,
  destroyed: oe,
  unmounted: oe,
  activated: oe,
  deactivated: oe,
  errorCaptured: oe,
  serverPrefetch: oe,
  // assets
  components: xt,
  directives: xt,
  // watch
  watch: vo,
  // provide / inject
  provide: xn,
  inject: bo
};
function xn(e, t) {
  return t ? e ? function() {
    return re(
      M(e) ? e.call(this, this) : e,
      M(t) ? t.call(this, this) : t
    );
  } : t : e;
}
function bo(e, t) {
  return xt(Ls(e), Ls(t));
}
function Ls(e) {
  if (O(e)) {
    const t = {};
    for (let s = 0; s < e.length; s++)
      t[e[s]] = e[s];
    return t;
  }
  return e;
}
function oe(e, t) {
  return e ? [...new Set([].concat(e, t))] : t;
}
function xt(e, t) {
  return e ? re(/* @__PURE__ */ Object.create(null), e, t) : t;
}
function Sn(e, t) {
  return e ? O(e) && O(t) ? [.../* @__PURE__ */ new Set([...e, ...t])] : re(
    /* @__PURE__ */ Object.create(null),
    wn(e),
    wn(t ?? {})
  ) : t;
}
function vo(e, t) {
  if (!e) return t;
  if (!t) return e;
  const s = re(/* @__PURE__ */ Object.create(null), e);
  for (const n in t)
    s[n] = oe(e[n], t[n]);
  return s;
}
function Pr() {
  return {
    app: null,
    config: {
      isNativeTag: ai,
      performance: !1,
      globalProperties: {},
      optionMergeStrategies: {},
      errorHandler: void 0,
      warnHandler: void 0,
      compilerOptions: {}
    },
    mixins: [],
    components: {},
    directives: {},
    provides: /* @__PURE__ */ Object.create(null),
    optionsCache: /* @__PURE__ */ new WeakMap(),
    propsCache: /* @__PURE__ */ new WeakMap(),
    emitsCache: /* @__PURE__ */ new WeakMap()
  };
}
let wo = 0;
function yo(e, t) {
  return function(n, r = null) {
    M(n) || (n = re({}, n)), r != null && !J(r) && (r = null);
    const i = Pr(), o = /* @__PURE__ */ new WeakSet(), l = [];
    let u = !1;
    const f = i.app = {
      _uid: wo++,
      _component: n,
      _props: r,
      _container: null,
      _context: i,
      _instance: null,
      version: tl,
      get config() {
        return i.config;
      },
      set config(d) {
      },
      use(d, ...p) {
        return o.has(d) || (d && M(d.install) ? (o.add(d), d.install(f, ...p)) : M(d) && (o.add(d), d(f, ...p))), f;
      },
      mixin(d) {
        return i.mixins.includes(d) || i.mixins.push(d), f;
      },
      component(d, p) {
        return p ? (i.components[d] = p, f) : i.components[d];
      },
      directive(d, p) {
        return p ? (i.directives[d] = p, f) : i.directives[d];
      },
      mount(d, p, m) {
        if (!u) {
          const x = f._ceVNode || be(n, r);
          return x.appContext = i, m === !0 ? m = "svg" : m === !1 && (m = void 0), e(x, d, m), u = !0, f._container = d, d.__vue_app__ = f, un(x.component);
        }
      },
      onUnmount(d) {
        l.push(d);
      },
      unmount() {
        u && (Te(
          l,
          f._instance,
          16
        ), e(null, f._container), delete f._container.__vue_app__);
      },
      provide(d, p) {
        return i.provides[d] = p, f;
      },
      runWithContext(d) {
        const p = pt;
        pt = f;
        try {
          return d();
        } finally {
          pt = p;
        }
      }
    };
    return f;
  };
}
let pt = null;
function xo(e, t) {
  if (ce) {
    let s = ce.provides;
    const n = ce.parent && ce.parent.provides;
    n === s && (s = ce.provides = Object.create(n)), s[e] = t;
  }
}
function Jt(e, t, s = !1) {
  const n = ce || Ee;
  if (n || pt) {
    const r = pt ? pt._context.provides : n ? n.parent == null ? n.vnode.appContext && n.vnode.appContext.provides : n.parent.provides : void 0;
    if (r && e in r)
      return r[e];
    if (arguments.length > 1)
      return s && M(t) ? t.call(n && n.proxy) : t;
  }
}
const Dr = {}, Fr = () => Object.create(Dr), Nr = (e) => Object.getPrototypeOf(e) === Dr;
function So(e, t, s, n = !1) {
  const r = {}, i = Fr();
  e.propsDefaults = /* @__PURE__ */ Object.create(null), kr(e, t, r, i);
  for (const o in e.propsOptions[0])
    o in r || (r[o] = void 0);
  s ? e.props = n ? r : Wi(r) : e.type.props ? e.props = r : e.props = i, e.attrs = i;
}
function Io(e, t, s, n) {
  const {
    props: r,
    attrs: i,
    vnode: { patchFlag: o }
  } = e, l = N(r), [u] = e.propsOptions;
  let f = !1;
  if (
    // always force full diff in dev
    // - #1942 if hmr is enabled with sfc component
    // - vite#872 non-sfc component used by sfc component
    (n || o > 0) && !(o & 16)
  ) {
    if (o & 8) {
      const d = e.vnode.dynamicProps;
      for (let p = 0; p < d.length; p++) {
        let m = d[p];
        if (hs(e.emitsOptions, m))
          continue;
        const x = t[m];
        if (u)
          if (k(i, m))
            x !== i[m] && (i[m] = x, f = !0);
          else {
            const R = We(m);
            r[R] = Hs(
              u,
              l,
              R,
              x,
              e,
              !1
            );
          }
        else
          x !== i[m] && (i[m] = x, f = !0);
      }
    }
  } else {
    kr(e, t, r, i) && (f = !0);
    let d;
    for (const p in l)
      (!t || // for camelCase
      !k(t, p) && // it's possible the original props was passed in as kebab-case
      // and converted to camelCase (#955)
      ((d = ot(p)) === p || !k(t, d))) && (u ? s && // for camelCase
      (s[p] !== void 0 || // for kebab-case
      s[d] !== void 0) && (r[p] = Hs(
        u,
        l,
        p,
        void 0,
        e,
        !0
      )) : delete r[p]);
    if (i !== l)
      for (const p in i)
        (!t || !k(t, p)) && (delete i[p], f = !0);
  }
  f && Me(e.attrs, "set", "");
}
function kr(e, t, s, n) {
  const [r, i] = e.propsOptions;
  let o = !1, l;
  if (t)
    for (let u in t) {
      if (At(u))
        continue;
      const f = t[u];
      let d;
      r && k(r, d = We(u)) ? !i || !i.includes(d) ? s[d] = f : (l || (l = {}))[d] = f : hs(e.emitsOptions, u) || (!(u in n) || f !== n[u]) && (n[u] = f, o = !0);
    }
  if (i) {
    const u = N(s), f = l || V;
    for (let d = 0; d < i.length; d++) {
      const p = i[d];
      s[p] = Hs(
        r,
        u,
        p,
        f[p],
        e,
        !k(f, p)
      );
    }
  }
  return o;
}
function Hs(e, t, s, n, r, i) {
  const o = e[s];
  if (o != null) {
    const l = k(o, "default");
    if (l && n === void 0) {
      const u = o.default;
      if (o.type !== Function && !o.skipFactory && M(u)) {
        const { propsDefaults: f } = r;
        if (s in f)
          n = f[s];
        else {
          const d = Lt(r);
          n = f[s] = u.call(
            null,
            t
          ), d();
        }
      } else
        n = u;
      r.ce && r.ce._setProp(s, n);
    }
    o[
      0
      /* shouldCast */
    ] && (i && !l ? n = !1 : o[
      1
      /* shouldCastTrue */
    ] && (n === "" || n === ot(s)) && (n = !0));
  }
  return n;
}
const Ao = /* @__PURE__ */ new WeakMap();
function Lr(e, t, s = !1) {
  const n = s ? Ao : t.propsCache, r = n.get(e);
  if (r)
    return r;
  const i = e.props, o = {}, l = [];
  let u = !1;
  if (!M(e)) {
    const d = (p) => {
      u = !0;
      const [m, x] = Lr(p, t, !0);
      re(o, m), x && l.push(...x);
    };
    !s && t.mixins.length && t.mixins.forEach(d), e.extends && d(e.extends), e.mixins && e.mixins.forEach(d);
  }
  if (!i && !u)
    return J(e) && n.set(e, at), at;
  if (O(i))
    for (let d = 0; d < i.length; d++) {
      const p = We(i[d]);
      In(p) && (o[p] = V);
    }
  else if (i)
    for (const d in i) {
      const p = We(d);
      if (In(p)) {
        const m = i[d], x = o[p] = O(m) || M(m) ? { type: m } : re({}, m), R = x.type;
        let C = !1, G = !0;
        if (O(R))
          for (let D = 0; D < R.length; ++D) {
            const z = R[D], Y = M(z) && z.name;
            if (Y === "Boolean") {
              C = !0;
              break;
            } else Y === "String" && (G = !1);
          }
        else
          C = M(R) && R.name === "Boolean";
        x[
          0
          /* shouldCast */
        ] = C, x[
          1
          /* shouldCastTrue */
        ] = G, (C || k(x, "default")) && l.push(p);
      }
    }
  const f = [o, l];
  return J(e) && n.set(e, f), f;
}
function In(e) {
  return e[0] !== "$" && !At(e);
}
const Hr = (e) => e[0] === "_" || e === "$stable", ln = (e) => O(e) ? e.map(Ce) : [Ce(e)], Co = (e, t, s) => {
  if (t._n)
    return t;
  const n = eo((...r) => ln(t(...r)), s);
  return n._c = !1, n;
}, jr = (e, t, s) => {
  const n = e._ctx;
  for (const r in e) {
    if (Hr(r)) continue;
    const i = e[r];
    if (M(i))
      t[r] = Co(r, i, n);
    else if (i != null) {
      const o = ln(i);
      t[r] = () => o;
    }
  }
}, Br = (e, t) => {
  const s = ln(t);
  e.slots.default = () => s;
}, Wr = (e, t, s) => {
  for (const n in t)
    (s || n !== "_") && (e[n] = t[n]);
}, Eo = (e, t, s) => {
  const n = e.slots = Fr();
  if (e.vnode.shapeFlag & 32) {
    const r = t._;
    r ? (Wr(n, t, s), s && Zn(n, "_", r, !0)) : jr(t, n);
  } else t && Br(e, t);
}, $o = (e, t, s) => {
  const { vnode: n, slots: r } = e;
  let i = !0, o = V;
  if (n.shapeFlag & 32) {
    const l = t._;
    l ? s && l === 1 ? i = !1 : Wr(r, t, s) : (i = !t.$stable, jr(t, r)), o = t;
  } else t && (Br(e, t), o = { default: 1 });
  if (i)
    for (const l in r)
      !Hr(l) && o[l] == null && delete r[l];
}, de = Wo;
function To(e) {
  return Oo(e);
}
function Oo(e, t) {
  const s = us();
  s.__VUE__ = !0;
  const {
    insert: n,
    remove: r,
    patchProp: i,
    createElement: o,
    createText: l,
    createComment: u,
    setText: f,
    setElementText: d,
    parentNode: p,
    nextSibling: m,
    setScopeId: x = $e,
    insertStaticContent: R
  } = e, C = (c, a, h, b = null, g = null, _ = null, S = void 0, y = null, w = !!a.dynamicChildren) => {
    if (c === a)
      return;
    c && !yt(c, a) && (b = Ut(c), we(c, g, _, !0), c = null), a.patchFlag === -2 && (w = !1, a.dynamicChildren = null);
    const { type: v, ref: E, shapeFlag: I } = a;
    switch (v) {
      case ps:
        G(c, a, h, b);
        break;
      case it:
        D(c, a, h, b);
        break;
      case As:
        c == null && z(a, h, b, S);
        break;
      case ee:
        jt(
          c,
          a,
          h,
          b,
          g,
          _,
          S,
          y,
          w
        );
        break;
      default:
        I & 1 ? Q(
          c,
          a,
          h,
          b,
          g,
          _,
          S,
          y,
          w
        ) : I & 6 ? Bt(
          c,
          a,
          h,
          b,
          g,
          _,
          S,
          y,
          w
        ) : (I & 64 || I & 128) && v.process(
          c,
          a,
          h,
          b,
          g,
          _,
          S,
          y,
          w,
          bt
        );
    }
    E != null && g && ts(E, c && c.ref, _, a || c, !a);
  }, G = (c, a, h, b) => {
    if (c == null)
      n(
        a.el = l(a.children),
        h,
        b
      );
    else {
      const g = a.el = c.el;
      a.children !== c.children && f(g, a.children);
    }
  }, D = (c, a, h, b) => {
    c == null ? n(
      a.el = u(a.children || ""),
      h,
      b
    ) : a.el = c.el;
  }, z = (c, a, h, b) => {
    [c.el, c.anchor] = R(
      c.children,
      a,
      h,
      b,
      c.el,
      c.anchor
    );
  }, Y = ({ el: c, anchor: a }, h, b) => {
    let g;
    for (; c && c !== a; )
      g = m(c), n(c, h, b), c = g;
    n(a, h, b);
  }, $ = ({ el: c, anchor: a }) => {
    let h;
    for (; c && c !== a; )
      h = m(c), r(c), c = h;
    r(a);
  }, Q = (c, a, h, b, g, _, S, y, w) => {
    a.type === "svg" ? S = "svg" : a.type === "math" && (S = "mathml"), c == null ? Fe(
      a,
      h,
      b,
      g,
      _,
      S,
      y,
      w
    ) : Ht(
      c,
      a,
      g,
      _,
      S,
      y,
      w
    );
  }, Fe = (c, a, h, b, g, _, S, y) => {
    let w, v;
    const { props: E, shapeFlag: I, transition: A, dirs: T } = c;
    if (w = c.el = o(
      c.type,
      _,
      E && E.is,
      E
    ), I & 8 ? d(w, c.children) : I & 16 && Ne(
      c.children,
      w,
      null,
      b,
      g,
      Is(c, _),
      S,
      y
    ), T && Xe(c, null, b, "created"), ve(w, c, c.scopeId, S, b), E) {
      for (const W in E)
        W !== "value" && !At(W) && i(w, W, null, E[W], _, b);
      "value" in E && i(w, "value", null, E.value, _), (v = E.onVnodeBeforeMount) && Ie(v, b, c);
    }
    T && Xe(c, null, b, "beforeMount");
    const P = Ro(g, A);
    P && A.beforeEnter(w), n(w, a, h), ((v = E && E.onVnodeMounted) || P || T) && de(() => {
      v && Ie(v, b, c), P && A.enter(w), T && Xe(c, null, b, "mounted");
    }, g);
  }, ve = (c, a, h, b, g) => {
    if (h && x(c, h), b)
      for (let _ = 0; _ < b.length; _++)
        x(c, b[_]);
    if (g) {
      let _ = g.subTree;
      if (a === _ || Jr(_.type) && (_.ssContent === a || _.ssFallback === a)) {
        const S = g.vnode;
        ve(
          c,
          S,
          S.scopeId,
          S.slotScopeIds,
          g.parent
        );
      }
    }
  }, Ne = (c, a, h, b, g, _, S, y, w = 0) => {
    for (let v = w; v < c.length; v++) {
      const E = c[v] = y ? Le(c[v]) : Ce(c[v]);
      C(
        null,
        E,
        a,
        h,
        b,
        g,
        _,
        S,
        y
      );
    }
  }, Ht = (c, a, h, b, g, _, S) => {
    const y = a.el = c.el;
    let { patchFlag: w, dynamicChildren: v, dirs: E } = a;
    w |= c.patchFlag & 16;
    const I = c.props || V, A = a.props || V;
    let T;
    if (h && Ze(h, !1), (T = A.onVnodeBeforeUpdate) && Ie(T, h, a, c), E && Xe(a, c, h, "beforeUpdate"), h && Ze(h, !0), (I.innerHTML && A.innerHTML == null || I.textContent && A.textContent == null) && d(y, ""), v ? Je(
      c.dynamicChildren,
      v,
      y,
      h,
      b,
      Is(a, g),
      _
    ) : S || B(
      c,
      a,
      y,
      null,
      h,
      b,
      Is(a, g),
      _,
      !1
    ), w > 0) {
      if (w & 16)
        mt(y, I, A, h, g);
      else if (w & 2 && I.class !== A.class && i(y, "class", null, A.class, g), w & 4 && i(y, "style", I.style, A.style, g), w & 8) {
        const P = a.dynamicProps;
        for (let W = 0; W < P.length; W++) {
          const H = P[W], ae = I[H], ue = A[H];
          (ue !== ae || H === "value") && i(y, H, ae, ue, g, h);
        }
      }
      w & 1 && c.children !== a.children && d(y, a.children);
    } else !S && v == null && mt(y, I, A, h, g);
    ((T = A.onVnodeUpdated) || E) && de(() => {
      T && Ie(T, h, a, c), E && Xe(a, c, h, "updated");
    }, b);
  }, Je = (c, a, h, b, g, _, S) => {
    for (let y = 0; y < a.length; y++) {
      const w = c[y], v = a[y], E = (
        // oldVNode may be an errored async setup() component inside Suspense
        // which will not have a mounted element
        w.el && // - In the case of a Fragment, we need to provide the actual parent
        // of the Fragment itself so it can move its children.
        (w.type === ee || // - In the case of different nodes, there is going to be a replacement
        // which also requires the correct parent container
        !yt(w, v) || // - In the case of a component, it could contain anything.
        w.shapeFlag & 70) ? p(w.el) : (
          // In other cases, the parent container is not actually used so we
          // just pass the block element here to avoid a DOM parentNode call.
          h
        )
      );
      C(
        w,
        v,
        E,
        null,
        b,
        g,
        _,
        S,
        !0
      );
    }
  }, mt = (c, a, h, b, g) => {
    if (a !== h) {
      if (a !== V)
        for (const _ in a)
          !At(_) && !(_ in h) && i(
            c,
            _,
            a[_],
            null,
            g,
            b
          );
      for (const _ in h) {
        if (At(_)) continue;
        const S = h[_], y = a[_];
        S !== y && _ !== "value" && i(c, _, y, S, g, b);
      }
      "value" in h && i(c, "value", a.value, h.value, g);
    }
  }, jt = (c, a, h, b, g, _, S, y, w) => {
    const v = a.el = c ? c.el : l(""), E = a.anchor = c ? c.anchor : l("");
    let { patchFlag: I, dynamicChildren: A, slotScopeIds: T } = a;
    T && (y = y ? y.concat(T) : T), c == null ? (n(v, h, b), n(E, h, b), Ne(
      // #10007
      // such fragment like `<></>` will be compiled into
      // a fragment which doesn't have a children.
      // In this case fallback to an empty array
      a.children || [],
      h,
      E,
      g,
      _,
      S,
      y,
      w
    )) : I > 0 && I & 64 && A && // #2715 the previous fragment could've been a BAILed one as a result
    // of renderSlot() with no valid children
    c.dynamicChildren ? (Je(
      c.dynamicChildren,
      A,
      h,
      g,
      _,
      S,
      y
    ), // #2080 if the stable fragment has a key, it's a <template v-for> that may
    //  get moved around. Make sure all root level vnodes inherit el.
    // #2134 or if it's a component root, it may also get moved around
    // as the component is being moved.
    (a.key != null || g && a === g.subTree) && Ur(
      c,
      a,
      !0
      /* shallow */
    )) : B(
      c,
      a,
      h,
      E,
      g,
      _,
      S,
      y,
      w
    );
  }, Bt = (c, a, h, b, g, _, S, y, w) => {
    a.slotScopeIds = y, c == null ? a.shapeFlag & 512 ? g.ctx.activate(
      a,
      h,
      b,
      S,
      w
    ) : gs(
      a,
      h,
      b,
      g,
      _,
      S,
      w
    ) : fn(c, a, w);
  }, gs = (c, a, h, b, g, _, S) => {
    const y = c.component = zo(
      c,
      b,
      g
    );
    if (Cr(c) && (y.ctx.renderer = bt), Yo(y, !1, S), y.asyncDep) {
      if (g && g.registerDep(y, ie, S), !c.el) {
        const w = y.subTree = be(it);
        D(null, w, a, h);
      }
    } else
      ie(
        y,
        c,
        a,
        h,
        g,
        _,
        S
      );
  }, fn = (c, a, h) => {
    const b = a.component = c.component;
    if (jo(c, a, h))
      if (b.asyncDep && !b.asyncResolved) {
        q(b, a, h);
        return;
      } else
        b.next = a, b.update();
    else
      a.el = c.el, b.vnode = a;
  }, ie = (c, a, h, b, g, _, S) => {
    const y = () => {
      if (c.isMounted) {
        let { next: I, bu: A, u: T, parent: P, vnode: W } = c;
        {
          const xe = Vr(c);
          if (xe) {
            I && (I.el = W.el, q(c, I, S)), xe.asyncDep.then(() => {
              c.isUnmounted || y();
            });
            return;
          }
        }
        let H = I, ae;
        Ze(c, !1), I ? (I.el = W.el, q(c, I, S)) : I = W, A && bs(A), (ae = I.props && I.props.onVnodeBeforeUpdate) && Ie(ae, P, I, W), Ze(c, !0);
        const ue = Cn(c), ye = c.subTree;
        c.subTree = ue, C(
          ye,
          ue,
          // parent may have changed if it's in a teleport
          p(ye.el),
          // anchor may have changed if it's in a fragment
          Ut(ye),
          c,
          g,
          _
        ), I.el = ue.el, H === null && Bo(c, ue.el), T && de(T, g), (ae = I.props && I.props.onVnodeUpdated) && de(
          () => Ie(ae, P, I, W),
          g
        );
      } else {
        let I;
        const { el: A, props: T } = a, { bm: P, m: W, parent: H, root: ae, type: ue } = c, ye = $t(a);
        Ze(c, !1), P && bs(P), !ye && (I = T && T.onVnodeBeforeMount) && Ie(I, H, a), Ze(c, !0);
        {
          ae.ce && ae.ce._injectChildStyle(ue);
          const xe = c.subTree = Cn(c);
          C(
            null,
            xe,
            h,
            b,
            c,
            g,
            _
          ), a.el = xe.el;
        }
        if (W && de(W, g), !ye && (I = T && T.onVnodeMounted)) {
          const xe = a;
          de(
            () => Ie(I, H, xe),
            g
          );
        }
        (a.shapeFlag & 256 || H && $t(H.vnode) && H.vnode.shapeFlag & 256) && c.a && de(c.a, g), c.isMounted = !0, a = h = b = null;
      }
    };
    c.scope.on();
    const w = c.effect = new sr(y);
    c.scope.off();
    const v = c.update = w.run.bind(w), E = c.job = w.runIfDirty.bind(w);
    E.i = c, E.id = c.uid, w.scheduler = () => nn(E), Ze(c, !0), v();
  }, q = (c, a, h) => {
    a.component = c;
    const b = c.vnode.props;
    c.vnode = a, c.next = null, Io(c, a.props, b, h), $o(c, a.children, h), Ke(), vn(c), Ge();
  }, B = (c, a, h, b, g, _, S, y, w = !1) => {
    const v = c && c.children, E = c ? c.shapeFlag : 0, I = a.children, { patchFlag: A, shapeFlag: T } = a;
    if (A > 0) {
      if (A & 128) {
        Wt(
          v,
          I,
          h,
          b,
          g,
          _,
          S,
          y,
          w
        );
        return;
      } else if (A & 256) {
        ze(
          v,
          I,
          h,
          b,
          g,
          _,
          S,
          y,
          w
        );
        return;
      }
    }
    T & 8 ? (E & 16 && _t(v, g, _), I !== v && d(h, I)) : E & 16 ? T & 16 ? Wt(
      v,
      I,
      h,
      b,
      g,
      _,
      S,
      y,
      w
    ) : _t(v, g, _, !0) : (E & 8 && d(h, ""), T & 16 && Ne(
      I,
      h,
      b,
      g,
      _,
      S,
      y,
      w
    ));
  }, ze = (c, a, h, b, g, _, S, y, w) => {
    c = c || at, a = a || at;
    const v = c.length, E = a.length, I = Math.min(v, E);
    let A;
    for (A = 0; A < I; A++) {
      const T = a[A] = w ? Le(a[A]) : Ce(a[A]);
      C(
        c[A],
        T,
        h,
        null,
        g,
        _,
        S,
        y,
        w
      );
    }
    v > E ? _t(
      c,
      g,
      _,
      !0,
      !1,
      I
    ) : Ne(
      a,
      h,
      b,
      g,
      _,
      S,
      y,
      w,
      I
    );
  }, Wt = (c, a, h, b, g, _, S, y, w) => {
    let v = 0;
    const E = a.length;
    let I = c.length - 1, A = E - 1;
    for (; v <= I && v <= A; ) {
      const T = c[v], P = a[v] = w ? Le(a[v]) : Ce(a[v]);
      if (yt(T, P))
        C(
          T,
          P,
          h,
          null,
          g,
          _,
          S,
          y,
          w
        );
      else
        break;
      v++;
    }
    for (; v <= I && v <= A; ) {
      const T = c[I], P = a[A] = w ? Le(a[A]) : Ce(a[A]);
      if (yt(T, P))
        C(
          T,
          P,
          h,
          null,
          g,
          _,
          S,
          y,
          w
        );
      else
        break;
      I--, A--;
    }
    if (v > I) {
      if (v <= A) {
        const T = A + 1, P = T < E ? a[T].el : b;
        for (; v <= A; )
          C(
            null,
            a[v] = w ? Le(a[v]) : Ce(a[v]),
            h,
            P,
            g,
            _,
            S,
            y,
            w
          ), v++;
      }
    } else if (v > A)
      for (; v <= I; )
        we(c[v], g, _, !0), v++;
    else {
      const T = v, P = v, W = /* @__PURE__ */ new Map();
      for (v = P; v <= A; v++) {
        const fe = a[v] = w ? Le(a[v]) : Ce(a[v]);
        fe.key != null && W.set(fe.key, v);
      }
      let H, ae = 0;
      const ue = A - P + 1;
      let ye = !1, xe = 0;
      const vt = new Array(ue);
      for (v = 0; v < ue; v++) vt[v] = 0;
      for (v = T; v <= I; v++) {
        const fe = c[v];
        if (ae >= ue) {
          we(fe, g, _, !0);
          continue;
        }
        let Se;
        if (fe.key != null)
          Se = W.get(fe.key);
        else
          for (H = P; H <= A; H++)
            if (vt[H - P] === 0 && yt(fe, a[H])) {
              Se = H;
              break;
            }
        Se === void 0 ? we(fe, g, _, !0) : (vt[Se - P] = v + 1, Se >= xe ? xe = Se : ye = !0, C(
          fe,
          a[Se],
          h,
          null,
          g,
          _,
          S,
          y,
          w
        ), ae++);
      }
      const pn = ye ? Mo(vt) : at;
      for (H = pn.length - 1, v = ue - 1; v >= 0; v--) {
        const fe = P + v, Se = a[fe], gn = fe + 1 < E ? a[fe + 1].el : b;
        vt[v] === 0 ? C(
          null,
          Se,
          h,
          gn,
          g,
          _,
          S,
          y,
          w
        ) : ye && (H < 0 || v !== pn[H] ? Ye(Se, h, gn, 2) : H--);
      }
    }
  }, Ye = (c, a, h, b, g = null) => {
    const { el: _, type: S, transition: y, children: w, shapeFlag: v } = c;
    if (v & 6) {
      Ye(c.component.subTree, a, h, b);
      return;
    }
    if (v & 128) {
      c.suspense.move(a, h, b);
      return;
    }
    if (v & 64) {
      S.move(c, a, h, bt);
      return;
    }
    if (S === ee) {
      n(_, a, h);
      for (let I = 0; I < w.length; I++)
        Ye(w[I], a, h, b);
      n(c.anchor, a, h);
      return;
    }
    if (S === As) {
      Y(c, a, h);
      return;
    }
    if (b !== 2 && v & 1 && y)
      if (b === 0)
        y.beforeEnter(_), n(_, a, h), de(() => y.enter(_), g);
      else {
        const { leave: I, delayLeave: A, afterLeave: T } = y, P = () => n(_, a, h), W = () => {
          I(_, () => {
            P(), T && T();
          });
        };
        A ? A(_, P, W) : W();
      }
    else
      n(_, a, h);
  }, we = (c, a, h, b = !1, g = !1) => {
    const {
      type: _,
      props: S,
      ref: y,
      children: w,
      dynamicChildren: v,
      shapeFlag: E,
      patchFlag: I,
      dirs: A,
      cacheIndex: T
    } = c;
    if (I === -2 && (g = !1), y != null && ts(y, null, h, c, !0), T != null && (a.renderCache[T] = void 0), E & 256) {
      a.ctx.deactivate(c);
      return;
    }
    const P = E & 1 && A, W = !$t(c);
    let H;
    if (W && (H = S && S.onVnodeBeforeUnmount) && Ie(H, a, c), E & 6)
      li(c.component, h, b);
    else {
      if (E & 128) {
        c.suspense.unmount(h, b);
        return;
      }
      P && Xe(c, null, a, "beforeUnmount"), E & 64 ? c.type.remove(
        c,
        a,
        h,
        bt,
        b
      ) : v && // #5154
      // when v-once is used inside a block, setBlockTracking(-1) marks the
      // parent block with hasOnce: true
      // so that it doesn't take the fast path during unmount - otherwise
      // components nested in v-once are never unmounted.
      !v.hasOnce && // #1153: fast path should not be taken for non-stable (v-for) fragments
      (_ !== ee || I > 0 && I & 64) ? _t(
        v,
        a,
        h,
        !1,
        !0
      ) : (_ === ee && I & 384 || !g && E & 16) && _t(w, a, h), b && dn(c);
    }
    (W && (H = S && S.onVnodeUnmounted) || P) && de(() => {
      H && Ie(H, a, c), P && Xe(c, null, a, "unmounted");
    }, h);
  }, dn = (c) => {
    const { type: a, el: h, anchor: b, transition: g } = c;
    if (a === ee) {
      oi(h, b);
      return;
    }
    if (a === As) {
      $(c);
      return;
    }
    const _ = () => {
      r(h), g && !g.persisted && g.afterLeave && g.afterLeave();
    };
    if (c.shapeFlag & 1 && g && !g.persisted) {
      const { leave: S, delayLeave: y } = g, w = () => S(h, _);
      y ? y(c.el, _, w) : w();
    } else
      _();
  }, oi = (c, a) => {
    let h;
    for (; c !== a; )
      h = m(c), r(c), c = h;
    r(a);
  }, li = (c, a, h) => {
    const { bum: b, scope: g, job: _, subTree: S, um: y, m: w, a: v } = c;
    An(w), An(v), b && bs(b), g.stop(), _ && (_.flags |= 8, we(S, c, a, h)), y && de(y, a), de(() => {
      c.isUnmounted = !0;
    }, a), a && a.pendingBranch && !a.isUnmounted && c.asyncDep && !c.asyncResolved && c.suspenseId === a.pendingId && (a.deps--, a.deps === 0 && a.resolve());
  }, _t = (c, a, h, b = !1, g = !1, _ = 0) => {
    for (let S = _; S < c.length; S++)
      we(c[S], a, h, b, g);
  }, Ut = (c) => {
    if (c.shapeFlag & 6)
      return Ut(c.component.subTree);
    if (c.shapeFlag & 128)
      return c.suspense.next();
    const a = m(c.anchor || c.el), h = a && a[to];
    return h ? m(h) : a;
  };
  let ms = !1;
  const hn = (c, a, h) => {
    c == null ? a._vnode && we(a._vnode, null, null, !0) : C(
      a._vnode || null,
      c,
      a,
      null,
      null,
      null,
      h
    ), a._vnode = c, ms || (ms = !0, vn(), xr(), ms = !1);
  }, bt = {
    p: C,
    um: we,
    m: Ye,
    r: dn,
    mt: gs,
    mc: Ne,
    pc: B,
    pbc: Je,
    n: Ut,
    o: e
  };
  return {
    render: hn,
    hydrate: void 0,
    createApp: yo(hn)
  };
}
function Is({ type: e, props: t }, s) {
  return s === "svg" && e === "foreignObject" || s === "mathml" && e === "annotation-xml" && t && t.encoding && t.encoding.includes("html") ? void 0 : s;
}
function Ze({ effect: e, job: t }, s) {
  s ? (e.flags |= 32, t.flags |= 4) : (e.flags &= -33, t.flags &= -5);
}
function Ro(e, t) {
  return (!e || e && !e.pendingBranch) && t && !t.persisted;
}
function Ur(e, t, s = !1) {
  const n = e.children, r = t.children;
  if (O(n) && O(r))
    for (let i = 0; i < n.length; i++) {
      const o = n[i];
      let l = r[i];
      l.shapeFlag & 1 && !l.dynamicChildren && ((l.patchFlag <= 0 || l.patchFlag === 32) && (l = r[i] = Le(r[i]), l.el = o.el), !s && l.patchFlag !== -2 && Ur(o, l)), l.type === ps && (l.el = o.el);
    }
}
function Mo(e) {
  const t = e.slice(), s = [0];
  let n, r, i, o, l;
  const u = e.length;
  for (n = 0; n < u; n++) {
    const f = e[n];
    if (f !== 0) {
      if (r = s[s.length - 1], e[r] < f) {
        t[n] = r, s.push(n);
        continue;
      }
      for (i = 0, o = s.length - 1; i < o; )
        l = i + o >> 1, e[s[l]] < f ? i = l + 1 : o = l;
      f < e[s[i]] && (i > 0 && (t[n] = s[i - 1]), s[i] = n);
    }
  }
  for (i = s.length, o = s[i - 1]; i-- > 0; )
    s[i] = o, o = t[o];
  return s;
}
function Vr(e) {
  const t = e.subTree.component;
  if (t)
    return t.asyncDep && !t.asyncResolved ? t : Vr(t);
}
function An(e) {
  if (e)
    for (let t = 0; t < e.length; t++)
      e[t].flags |= 8;
}
const Po = Symbol.for("v-scx"), Do = () => Jt(Po);
function zt(e, t, s) {
  return Kr(e, t, s);
}
function Kr(e, t, s = V) {
  const { immediate: n, deep: r, flush: i, once: o } = s, l = re({}, s), u = t && n || !t && i !== "post";
  let f;
  if (Ft) {
    if (i === "sync") {
      const x = Do();
      f = x.__watcherHandles || (x.__watcherHandles = []);
    } else if (!u) {
      const x = () => {
      };
      return x.stop = $e, x.resume = $e, x.pause = $e, x;
    }
  }
  const d = ce;
  l.call = (x, R, C) => Te(x, d, R, C);
  let p = !1;
  i === "post" ? l.scheduler = (x) => {
    de(x, d && d.suspense);
  } : i !== "sync" && (p = !0, l.scheduler = (x, R) => {
    R ? x() : nn(x);
  }), l.augmentJob = (x) => {
    t && (x.flags |= 4), p && (x.flags |= 2, d && (x.id = d.uid, x.i = d));
  };
  const m = Yi(e, t, l);
  return Ft && (f ? f.push(m) : u && m()), m;
}
function Fo(e, t, s) {
  const n = this.proxy, r = Z(e) ? e.includes(".") ? Gr(n, e) : () => n[e] : e.bind(n, n);
  let i;
  M(t) ? i = t : (i = t.handler, s = t);
  const o = Lt(this), l = Kr(r, i.bind(n), s);
  return o(), l;
}
function Gr(e, t) {
  const s = t.split(".");
  return () => {
    let n = e;
    for (let r = 0; r < s.length && n; r++)
      n = n[s[r]];
    return n;
  };
}
const No = (e, t) => t === "modelValue" || t === "model-value" ? e.modelModifiers : e[`${t}Modifiers`] || e[`${We(t)}Modifiers`] || e[`${ot(t)}Modifiers`];
function ko(e, t, ...s) {
  if (e.isUnmounted) return;
  const n = e.vnode.props || V;
  let r = s;
  const i = t.startsWith("update:"), o = i && No(n, t.slice(7));
  o && (o.trim && (r = s.map((d) => Z(d) ? d.trim() : d)), o.number && (r = s.map(gi)));
  let l, u = n[l = _s(t)] || // also try camelCase event handler (#2249)
  n[l = _s(We(t))];
  !u && i && (u = n[l = _s(ot(t))]), u && Te(
    u,
    e,
    6,
    r
  );
  const f = n[l + "Once"];
  if (f) {
    if (!e.emitted)
      e.emitted = {};
    else if (e.emitted[l])
      return;
    e.emitted[l] = !0, Te(
      f,
      e,
      6,
      r
    );
  }
}
function qr(e, t, s = !1) {
  const n = t.emitsCache, r = n.get(e);
  if (r !== void 0)
    return r;
  const i = e.emits;
  let o = {}, l = !1;
  if (!M(e)) {
    const u = (f) => {
      const d = qr(f, t, !0);
      d && (l = !0, re(o, d));
    };
    !s && t.mixins.length && t.mixins.forEach(u), e.extends && u(e.extends), e.mixins && e.mixins.forEach(u);
  }
  return !i && !l ? (J(e) && n.set(e, null), null) : (O(i) ? i.forEach((u) => o[u] = null) : re(o, i), J(e) && n.set(e, o), o);
}
function hs(e, t) {
  return !e || !os(t) ? !1 : (t = t.slice(2).replace(/Once$/, ""), k(e, t[0].toLowerCase() + t.slice(1)) || k(e, ot(t)) || k(e, t));
}
function Cn(e) {
  const {
    type: t,
    vnode: s,
    proxy: n,
    withProxy: r,
    propsOptions: [i],
    slots: o,
    attrs: l,
    emit: u,
    render: f,
    renderCache: d,
    props: p,
    data: m,
    setupState: x,
    ctx: R,
    inheritAttrs: C
  } = e, G = es(e);
  let D, z;
  try {
    if (s.shapeFlag & 4) {
      const $ = r || n, Q = $;
      D = Ce(
        f.call(
          Q,
          $,
          d,
          p,
          x,
          m,
          R
        )
      ), z = l;
    } else {
      const $ = t;
      D = Ce(
        $.length > 1 ? $(
          p,
          { attrs: l, slots: o, emit: u }
        ) : $(
          p,
          null
        )
      ), z = t.props ? l : Lo(l);
    }
  } catch ($) {
    Ot.length = 0, fs($, e, 1), D = be(it);
  }
  let Y = D;
  if (z && C !== !1) {
    const $ = Object.keys(z), { shapeFlag: Q } = Y;
    $.length && Q & 7 && (i && $.some(Gs) && (z = Ho(
      z,
      i
    )), Y = gt(Y, z, !1, !0));
  }
  return s.dirs && (Y = gt(Y, null, !1, !0), Y.dirs = Y.dirs ? Y.dirs.concat(s.dirs) : s.dirs), s.transition && rn(Y, s.transition), D = Y, es(G), D;
}
const Lo = (e) => {
  let t;
  for (const s in e)
    (s === "class" || s === "style" || os(s)) && ((t || (t = {}))[s] = e[s]);
  return t;
}, Ho = (e, t) => {
  const s = {};
  for (const n in e)
    (!Gs(n) || !(n.slice(9) in t)) && (s[n] = e[n]);
  return s;
};
function jo(e, t, s) {
  const { props: n, children: r, component: i } = e, { props: o, children: l, patchFlag: u } = t, f = i.emitsOptions;
  if (t.dirs || t.transition)
    return !0;
  if (s && u >= 0) {
    if (u & 1024)
      return !0;
    if (u & 16)
      return n ? En(n, o, f) : !!o;
    if (u & 8) {
      const d = t.dynamicProps;
      for (let p = 0; p < d.length; p++) {
        const m = d[p];
        if (o[m] !== n[m] && !hs(f, m))
          return !0;
      }
    }
  } else
    return (r || l) && (!l || !l.$stable) ? !0 : n === o ? !1 : n ? o ? En(n, o, f) : !0 : !!o;
  return !1;
}
function En(e, t, s) {
  const n = Object.keys(t);
  if (n.length !== Object.keys(e).length)
    return !0;
  for (let r = 0; r < n.length; r++) {
    const i = n[r];
    if (t[i] !== e[i] && !hs(s, i))
      return !0;
  }
  return !1;
}
function Bo({ vnode: e, parent: t }, s) {
  for (; t; ) {
    const n = t.subTree;
    if (n.suspense && n.suspense.activeBranch === e && (n.el = e.el), n === e)
      (e = t.vnode).el = s, t = t.parent;
    else
      break;
  }
}
const Jr = (e) => e.__isSuspense;
function Wo(e, t) {
  t && t.pendingBranch ? O(e) ? t.effects.push(...e) : t.effects.push(e) : Qi(e);
}
const ee = Symbol.for("v-fgt"), ps = Symbol.for("v-txt"), it = Symbol.for("v-cmt"), As = Symbol.for("v-stc"), Ot = [];
let ge = null;
function F(e = !1) {
  Ot.push(ge = e ? null : []);
}
function Uo() {
  Ot.pop(), ge = Ot[Ot.length - 1] || null;
}
let Dt = 1;
function $n(e, t = !1) {
  Dt += e, e < 0 && ge && t && (ge.hasOnce = !0);
}
function zr(e) {
  return e.dynamicChildren = Dt > 0 ? ge || at : null, Uo(), Dt > 0 && ge && ge.push(e), e;
}
function K(e, t, s, n, r, i) {
  return zr(
    L(
      e,
      t,
      s,
      n,
      r,
      i,
      !0
    )
  );
}
function tt(e, t, s, n, r) {
  return zr(
    be(
      e,
      t,
      s,
      n,
      r,
      !0
    )
  );
}
function Yr(e) {
  return e ? e.__v_isVNode === !0 : !1;
}
function yt(e, t) {
  return e.type === t.type && e.key === t.key;
}
const Xr = ({ key: e }) => e ?? null, Yt = ({
  ref: e,
  ref_key: t,
  ref_for: s
}) => (typeof e == "number" && (e = "" + e), e != null ? Z(e) || ne(e) || M(e) ? { i: Ee, r: e, k: t, f: !!s } : e : null);
function L(e, t = null, s = null, n = 0, r = null, i = e === ee ? 0 : 1, o = !1, l = !1) {
  const u = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e,
    props: t,
    key: t && Xr(t),
    ref: t && Yt(t),
    scopeId: Ir,
    slotScopeIds: null,
    children: s,
    component: null,
    suspense: null,
    ssContent: null,
    ssFallback: null,
    dirs: null,
    transition: null,
    el: null,
    anchor: null,
    target: null,
    targetStart: null,
    targetAnchor: null,
    staticCount: 0,
    shapeFlag: i,
    patchFlag: n,
    dynamicProps: r,
    dynamicChildren: null,
    appContext: null,
    ctx: Ee
  };
  return l ? (cn(u, s), i & 128 && e.normalize(u)) : s && (u.shapeFlag |= Z(s) ? 8 : 16), Dt > 0 && // avoid a block node from tracking itself
  !o && // has current parent block
  ge && // presence of a patch flag indicates this node needs patching on updates.
  // component nodes also should always be patched, because even if the
  // component doesn't need to update, it needs to persist the instance on to
  // the next vnode so that it can be properly unmounted later.
  (u.patchFlag > 0 || i & 6) && // the EVENTS flag is only for hydration and if it is the only flag, the
  // vnode should not be considered dynamic due to handler caching.
  u.patchFlag !== 32 && ge.push(u), u;
}
const be = Vo;
function Vo(e, t = null, s = null, n = 0, r = null, i = !1) {
  if ((!e || e === ho) && (e = it), Yr(e)) {
    const l = gt(
      e,
      t,
      !0
      /* mergeRef: true */
    );
    return s && cn(l, s), Dt > 0 && !i && ge && (l.shapeFlag & 6 ? ge[ge.indexOf(e)] = l : ge.push(l)), l.patchFlag = -2, l;
  }
  if (el(e) && (e = e.__vccOpts), t) {
    t = Ko(t);
    let { class: l, style: u } = t;
    l && !Z(l) && (t.class = Ve(l)), J(u) && (sn(u) && !O(u) && (u = re({}, u)), t.style = pe(u));
  }
  const o = Z(e) ? 1 : Jr(e) ? 128 : so(e) ? 64 : J(e) ? 4 : M(e) ? 2 : 0;
  return L(
    e,
    t,
    s,
    n,
    r,
    o,
    i,
    !0
  );
}
function Ko(e) {
  return e ? sn(e) || Nr(e) ? re({}, e) : e : null;
}
function gt(e, t, s = !1, n = !1) {
  const { props: r, ref: i, patchFlag: o, children: l, transition: u } = e, f = t ? Go(r || {}, t) : r, d = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e.type,
    props: f,
    key: f && Xr(f),
    ref: t && t.ref ? (
      // #2078 in the case of <component :is="vnode" ref="extra"/>
      // if the vnode itself already has a ref, cloneVNode will need to merge
      // the refs so the single vnode can be set on multiple refs
      s && i ? O(i) ? i.concat(Yt(t)) : [i, Yt(t)] : Yt(t)
    ) : i,
    scopeId: e.scopeId,
    slotScopeIds: e.slotScopeIds,
    children: l,
    target: e.target,
    targetStart: e.targetStart,
    targetAnchor: e.targetAnchor,
    staticCount: e.staticCount,
    shapeFlag: e.shapeFlag,
    // if the vnode is cloned with extra props, we can no longer assume its
    // existing patch flag to be reliable and need to add the FULL_PROPS flag.
    // note: preserve flag for fragments since they use the flag for children
    // fast paths only.
    patchFlag: t && e.type !== ee ? o === -1 ? 16 : o | 16 : o,
    dynamicProps: e.dynamicProps,
    dynamicChildren: e.dynamicChildren,
    appContext: e.appContext,
    dirs: e.dirs,
    transition: u,
    // These should technically only be non-null on mounted VNodes. However,
    // they *should* be copied for kept-alive vnodes. So we just always copy
    // them since them being non-null during a mount doesn't affect the logic as
    // they will simply be overwritten.
    component: e.component,
    suspense: e.suspense,
    ssContent: e.ssContent && gt(e.ssContent),
    ssFallback: e.ssFallback && gt(e.ssFallback),
    el: e.el,
    anchor: e.anchor,
    ctx: e.ctx,
    ce: e.ce
  };
  return u && n && rn(
    d,
    u.clone(d)
  ), d;
}
function St(e = " ", t = 0) {
  return be(ps, null, e, t);
}
function Pe(e = "", t = !1) {
  return t ? (F(), tt(it, null, e)) : be(it, null, e);
}
function Ce(e) {
  return e == null || typeof e == "boolean" ? be(it) : O(e) ? be(
    ee,
    null,
    // #3666, avoid reference pollution when reusing vnode
    e.slice()
  ) : Yr(e) ? Le(e) : be(ps, null, String(e));
}
function Le(e) {
  return e.el === null && e.patchFlag !== -1 || e.memo ? e : gt(e);
}
function cn(e, t) {
  let s = 0;
  const { shapeFlag: n } = e;
  if (t == null)
    t = null;
  else if (O(t))
    s = 16;
  else if (typeof t == "object")
    if (n & 65) {
      const r = t.default;
      r && (r._c && (r._d = !1), cn(e, r()), r._c && (r._d = !0));
      return;
    } else {
      s = 32;
      const r = t._;
      !r && !Nr(t) ? t._ctx = Ee : r === 3 && Ee && (Ee.slots._ === 1 ? t._ = 1 : (t._ = 2, e.patchFlag |= 1024));
    }
  else M(t) ? (t = { default: t, _ctx: Ee }, s = 32) : (t = String(t), n & 64 ? (s = 16, t = [St(t)]) : s = 8);
  e.children = t, e.shapeFlag |= s;
}
function Go(...e) {
  const t = {};
  for (let s = 0; s < e.length; s++) {
    const n = e[s];
    for (const r in n)
      if (r === "class")
        t.class !== n.class && (t.class = Ve([t.class, n.class]));
      else if (r === "style")
        t.style = pe([t.style, n.style]);
      else if (os(r)) {
        const i = t[r], o = n[r];
        o && i !== o && !(O(i) && i.includes(o)) && (t[r] = i ? [].concat(i, o) : o);
      } else r !== "" && (t[r] = n[r]);
  }
  return t;
}
function Ie(e, t, s, n = null) {
  Te(e, t, 7, [
    s,
    n
  ]);
}
const qo = Pr();
let Jo = 0;
function zo(e, t, s) {
  const n = e.type, r = (t ? t.appContext : e.appContext) || qo, i = {
    uid: Jo++,
    vnode: e,
    type: n,
    parent: t,
    appContext: r,
    root: null,
    // to be immediately set
    next: null,
    subTree: null,
    // will be set synchronously right after creation
    effect: null,
    update: null,
    // will be set synchronously right after creation
    job: null,
    scope: new xi(
      !0
      /* detached */
    ),
    render: null,
    proxy: null,
    exposed: null,
    exposeProxy: null,
    withProxy: null,
    provides: t ? t.provides : Object.create(r.provides),
    ids: t ? t.ids : ["", 0, 0],
    accessCache: null,
    renderCache: [],
    // local resolved assets
    components: null,
    directives: null,
    // resolved props and emits options
    propsOptions: Lr(n, r),
    emitsOptions: qr(n, r),
    // emit
    emit: null,
    // to be set immediately
    emitted: null,
    // props default value
    propsDefaults: V,
    // inheritAttrs
    inheritAttrs: n.inheritAttrs,
    // state
    ctx: V,
    data: V,
    props: V,
    attrs: V,
    slots: V,
    refs: V,
    setupState: V,
    setupContext: null,
    // suspense related
    suspense: s,
    suspenseId: s ? s.pendingId : 0,
    asyncDep: null,
    asyncResolved: !1,
    // lifecycle hooks
    // not using enums here because it results in computed properties
    isMounted: !1,
    isUnmounted: !1,
    isDeactivated: !1,
    bc: null,
    c: null,
    bm: null,
    m: null,
    bu: null,
    u: null,
    um: null,
    bum: null,
    da: null,
    a: null,
    rtg: null,
    rtc: null,
    ec: null,
    sp: null
  };
  return i.ctx = { _: i }, i.root = t ? t.root : i, i.emit = ko.bind(null, i), e.ce && e.ce(i), i;
}
let ce = null, ns, js;
{
  const e = us(), t = (s, n) => {
    let r;
    return (r = e[s]) || (r = e[s] = []), r.push(n), (i) => {
      r.length > 1 ? r.forEach((o) => o(i)) : r[0](i);
    };
  };
  ns = t(
    "__VUE_INSTANCE_SETTERS__",
    (s) => ce = s
  ), js = t(
    "__VUE_SSR_SETTERS__",
    (s) => Ft = s
  );
}
const Lt = (e) => {
  const t = ce;
  return ns(e), e.scope.on(), () => {
    e.scope.off(), ns(t);
  };
}, Tn = () => {
  ce && ce.scope.off(), ns(null);
};
function Zr(e) {
  return e.vnode.shapeFlag & 4;
}
let Ft = !1;
function Yo(e, t = !1, s = !1) {
  t && js(t);
  const { props: n, children: r } = e.vnode, i = Zr(e);
  So(e, n, i, t), Eo(e, r, s);
  const o = i ? Xo(e, t) : void 0;
  return t && js(!1), o;
}
function Xo(e, t) {
  const s = e.type;
  e.accessCache = /* @__PURE__ */ Object.create(null), e.proxy = new Proxy(e.ctx, po);
  const { setup: n } = s;
  if (n) {
    Ke();
    const r = e.setupContext = n.length > 1 ? Qo(e) : null, i = Lt(e), o = kt(
      n,
      e,
      0,
      [
        e.props,
        r
      ]
    ), l = Jn(o);
    if (Ge(), i(), (l || e.sp) && !$t(e) && Ar(e), l) {
      if (o.then(Tn, Tn), t)
        return o.then((u) => {
          On(e, u);
        }).catch((u) => {
          fs(u, e, 0);
        });
      e.asyncDep = o;
    } else
      On(e, o);
  } else
    Qr(e);
}
function On(e, t, s) {
  M(t) ? e.type.__ssrInlineRender ? e.ssrRender = t : e.render = t : J(t) && (e.setupState = br(t)), Qr(e);
}
function Qr(e, t, s) {
  const n = e.type;
  e.render || (e.render = n.render || $e);
  {
    const r = Lt(e);
    Ke();
    try {
      go(e);
    } finally {
      Ge(), r();
    }
  }
}
const Zo = {
  get(e, t) {
    return te(e, "get", ""), e[t];
  }
};
function Qo(e) {
  const t = (s) => {
    e.exposed = s || {};
  };
  return {
    attrs: new Proxy(e.attrs, Zo),
    slots: e.slots,
    emit: e.emit,
    expose: t
  };
}
function un(e) {
  return e.exposed ? e.exposeProxy || (e.exposeProxy = new Proxy(br(Ui(e.exposed)), {
    get(t, s) {
      if (s in t)
        return t[s];
      if (s in Tt)
        return Tt[s](e);
    },
    has(t, s) {
      return s in t || s in Tt;
    }
  })) : e.proxy;
}
function el(e) {
  return M(e) && "__vccOpts" in e;
}
const nt = (e, t) => Ji(e, t, Ft), tl = "3.5.13";
/**
* @vue/runtime-dom v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
let Bs;
const Rn = typeof window < "u" && window.trustedTypes;
if (Rn)
  try {
    Bs = /* @__PURE__ */ Rn.createPolicy("vue", {
      createHTML: (e) => e
    });
  } catch {
  }
const ei = Bs ? (e) => Bs.createHTML(e) : (e) => e, sl = "http://www.w3.org/2000/svg", nl = "http://www.w3.org/1998/Math/MathML", Re = typeof document < "u" ? document : null, Mn = Re && /* @__PURE__ */ Re.createElement("template"), rl = {
  insert: (e, t, s) => {
    t.insertBefore(e, s || null);
  },
  remove: (e) => {
    const t = e.parentNode;
    t && t.removeChild(e);
  },
  createElement: (e, t, s, n) => {
    const r = t === "svg" ? Re.createElementNS(sl, e) : t === "mathml" ? Re.createElementNS(nl, e) : s ? Re.createElement(e, { is: s }) : Re.createElement(e);
    return e === "select" && n && n.multiple != null && r.setAttribute("multiple", n.multiple), r;
  },
  createText: (e) => Re.createTextNode(e),
  createComment: (e) => Re.createComment(e),
  setText: (e, t) => {
    e.nodeValue = t;
  },
  setElementText: (e, t) => {
    e.textContent = t;
  },
  parentNode: (e) => e.parentNode,
  nextSibling: (e) => e.nextSibling,
  querySelector: (e) => Re.querySelector(e),
  setScopeId(e, t) {
    e.setAttribute(t, "");
  },
  // __UNSAFE__
  // Reason: innerHTML.
  // Static content here can only come from compiled templates.
  // As long as the user only uses trusted templates, this is safe.
  insertStaticContent(e, t, s, n, r, i) {
    const o = s ? s.previousSibling : t.lastChild;
    if (r && (r === i || r.nextSibling))
      for (; t.insertBefore(r.cloneNode(!0), s), !(r === i || !(r = r.nextSibling)); )
        ;
    else {
      Mn.innerHTML = ei(
        n === "svg" ? `<svg>${e}</svg>` : n === "mathml" ? `<math>${e}</math>` : e
      );
      const l = Mn.content;
      if (n === "svg" || n === "mathml") {
        const u = l.firstChild;
        for (; u.firstChild; )
          l.appendChild(u.firstChild);
        l.removeChild(u);
      }
      t.insertBefore(l, s);
    }
    return [
      // first
      o ? o.nextSibling : t.firstChild,
      // last
      s ? s.previousSibling : t.lastChild
    ];
  }
}, il = Symbol("_vtc");
function ol(e, t, s) {
  const n = e[il];
  n && (t = (t ? [t, ...n] : [...n]).join(" ")), t == null ? e.removeAttribute("class") : s ? e.setAttribute("class", t) : e.className = t;
}
const Pn = Symbol("_vod"), ll = Symbol("_vsh"), cl = Symbol(""), ul = /(^|;)\s*display\s*:/;
function al(e, t, s) {
  const n = e.style, r = Z(s);
  let i = !1;
  if (s && !r) {
    if (t)
      if (Z(t))
        for (const o of t.split(";")) {
          const l = o.slice(0, o.indexOf(":")).trim();
          s[l] == null && Xt(n, l, "");
        }
      else
        for (const o in t)
          s[o] == null && Xt(n, o, "");
    for (const o in s)
      o === "display" && (i = !0), Xt(n, o, s[o]);
  } else if (r) {
    if (t !== s) {
      const o = n[cl];
      o && (s += ";" + o), n.cssText = s, i = ul.test(s);
    }
  } else t && e.removeAttribute("style");
  Pn in e && (e[Pn] = i ? n.display : "", e[ll] && (n.display = "none"));
}
const Dn = /\s*!important$/;
function Xt(e, t, s) {
  if (O(s))
    s.forEach((n) => Xt(e, t, n));
  else if (s == null && (s = ""), t.startsWith("--"))
    e.setProperty(t, s);
  else {
    const n = fl(e, t);
    Dn.test(s) ? e.setProperty(
      ot(n),
      s.replace(Dn, ""),
      "important"
    ) : e[n] = s;
  }
}
const Fn = ["Webkit", "Moz", "ms"], Cs = {};
function fl(e, t) {
  const s = Cs[t];
  if (s)
    return s;
  let n = We(t);
  if (n !== "filter" && n in e)
    return Cs[t] = n;
  n = Xn(n);
  for (let r = 0; r < Fn.length; r++) {
    const i = Fn[r] + n;
    if (i in e)
      return Cs[t] = i;
  }
  return t;
}
const Nn = "http://www.w3.org/1999/xlink";
function kn(e, t, s, n, r, i = yi(t)) {
  n && t.startsWith("xlink:") ? s == null ? e.removeAttributeNS(Nn, t.slice(6, t.length)) : e.setAttributeNS(Nn, t, s) : s == null || i && !Qn(s) ? e.removeAttribute(t) : e.setAttribute(
    t,
    i ? "" : Ue(s) ? String(s) : s
  );
}
function Ln(e, t, s, n, r) {
  if (t === "innerHTML" || t === "textContent") {
    s != null && (e[t] = t === "innerHTML" ? ei(s) : s);
    return;
  }
  const i = e.tagName;
  if (t === "value" && i !== "PROGRESS" && // custom elements may use _value internally
  !i.includes("-")) {
    const l = i === "OPTION" ? e.getAttribute("value") || "" : e.value, u = s == null ? (
      // #11647: value should be set as empty string for null and undefined,
      // but <input type="checkbox"> should be set as 'on'.
      e.type === "checkbox" ? "on" : ""
    ) : String(s);
    (l !== u || !("_value" in e)) && (e.value = u), s == null && e.removeAttribute(t), e._value = s;
    return;
  }
  let o = !1;
  if (s === "" || s == null) {
    const l = typeof e[t];
    l === "boolean" ? s = Qn(s) : s == null && l === "string" ? (s = "", o = !0) : l === "number" && (s = 0, o = !0);
  }
  try {
    e[t] = s;
  } catch {
  }
  o && e.removeAttribute(r || t);
}
function dl(e, t, s, n) {
  e.addEventListener(t, s, n);
}
function hl(e, t, s, n) {
  e.removeEventListener(t, s, n);
}
const Hn = Symbol("_vei");
function pl(e, t, s, n, r = null) {
  const i = e[Hn] || (e[Hn] = {}), o = i[t];
  if (n && o)
    o.value = n;
  else {
    const [l, u] = gl(t);
    if (n) {
      const f = i[t] = bl(
        n,
        r
      );
      dl(e, l, f, u);
    } else o && (hl(e, l, o, u), i[t] = void 0);
  }
}
const jn = /(?:Once|Passive|Capture)$/;
function gl(e) {
  let t;
  if (jn.test(e)) {
    t = {};
    let n;
    for (; n = e.match(jn); )
      e = e.slice(0, e.length - n[0].length), t[n[0].toLowerCase()] = !0;
  }
  return [e[2] === ":" ? e.slice(3) : ot(e.slice(2)), t];
}
let Es = 0;
const ml = /* @__PURE__ */ Promise.resolve(), _l = () => Es || (ml.then(() => Es = 0), Es = Date.now());
function bl(e, t) {
  const s = (n) => {
    if (!n._vts)
      n._vts = Date.now();
    else if (n._vts <= s.attached)
      return;
    Te(
      vl(n, s.value),
      t,
      5,
      [n]
    );
  };
  return s.value = e, s.attached = _l(), s;
}
function vl(e, t) {
  if (O(t)) {
    const s = e.stopImmediatePropagation;
    return e.stopImmediatePropagation = () => {
      s.call(e), e._stopped = !0;
    }, t.map(
      (n) => (r) => !r._stopped && n && n(r)
    );
  } else
    return t;
}
const Bn = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && // lowercase letter
e.charCodeAt(2) > 96 && e.charCodeAt(2) < 123, wl = (e, t, s, n, r, i) => {
  const o = r === "svg";
  t === "class" ? ol(e, n, o) : t === "style" ? al(e, s, n) : os(t) ? Gs(t) || pl(e, t, s, n, i) : (t[0] === "." ? (t = t.slice(1), !0) : t[0] === "^" ? (t = t.slice(1), !1) : yl(e, t, n, o)) ? (Ln(e, t, n), !e.tagName.includes("-") && (t === "value" || t === "checked" || t === "selected") && kn(e, t, n, o, i, t !== "value")) : /* #11081 force set props for possible async custom element */ e._isVueCE && (/[A-Z]/.test(t) || !Z(n)) ? Ln(e, We(t), n, i, t) : (t === "true-value" ? e._trueValue = n : t === "false-value" && (e._falseValue = n), kn(e, t, n, o));
};
function yl(e, t, s, n) {
  if (n)
    return !!(t === "innerHTML" || t === "textContent" || t in e && Bn(t) && M(s));
  if (t === "spellcheck" || t === "draggable" || t === "translate" || t === "form" || t === "list" && e.tagName === "INPUT" || t === "type" && e.tagName === "TEXTAREA")
    return !1;
  if (t === "width" || t === "height") {
    const r = e.tagName;
    if (r === "IMG" || r === "VIDEO" || r === "CANVAS" || r === "SOURCE")
      return !1;
  }
  return Bn(t) && Z(s) ? !1 : t in e;
}
const xl = /* @__PURE__ */ re({ patchProp: wl }, rl);
let Wn;
function Sl() {
  return Wn || (Wn = To(xl));
}
const Il = (...e) => {
  const t = Sl().createApp(...e), { mount: s } = t;
  return t.mount = (n) => {
    const r = Cl(n);
    if (!r) return;
    const i = t._component;
    !M(i) && !i.render && !i.template && (i.template = r.innerHTML), r.nodeType === 1 && (r.textContent = "");
    const o = s(r, !1, Al(r));
    return r instanceof Element && (r.removeAttribute("v-cloak"), r.setAttribute("data-v-app", "")), o;
  }, t;
};
function Al(e) {
  if (e instanceof SVGElement)
    return "svg";
  if (typeof MathMLElement == "function" && e instanceof MathMLElement)
    return "mathml";
}
function Cl(e) {
  return Z(e) ? document.querySelector(e) : e;
}
const El = /* @__PURE__ */ new Set();
function $s(e) {
  return e.executionHost !== null && El.has(e.executionHost.trim().toLowerCase());
}
function $l(e) {
  var t;
  return !!((t = e.executionHost) != null && t.trim());
}
function Tl(e, t, s) {
  return e.logs.filter((n) => {
    if (n.cursor <= s.get(n.runId)) return !1;
    if (t.mode === "all") return !0;
    if (n.runId !== t.runId) return !1;
    const r = e.runs[n.runId];
    return (n.phaseId && (r == null ? void 0 : r.instanceOfPhase[n.phaseId]) || n.instanceId || n.phaseId) === t.instanceId;
  });
}
function Ol(e, t, s) {
  s.set(t, Math.max(s.get(t), e.maxCursor));
}
const Ws = "@runner", Un = 5e3;
function Rl() {
  return { runs: {}, logs: [], seen: {}, maxCursor: 0 };
}
function ti(e) {
  return e.outcome !== null || e.abandoned;
}
function Ml(e) {
  return Object.values(e.phases).sort((t, s) => t.order - s.order);
}
function qt(e) {
  e.visible = Ml(e).map((t) => t.instanceId);
}
function Pl(e, t, s) {
  e.visible = e.visible.map((n) => n === t ? s : n);
  for (const n of e.arrows)
    n.from === t && (n.from = s), n.to === t && (n.to = s);
}
const Dl = /* @__PURE__ */ new Set([
  "phase_start",
  "bound",
  "progress",
  "tool_call",
  "tool_result",
  "message",
  "log"
]);
function Vn(e) {
  return {
    runId: e.run_id,
    adwName: e.adw_name,
    status: e.status,
    startedAt: e.started_at,
    endedAt: e.ended_at,
    phases: {},
    instanceOfPhase: {},
    arrows: [],
    visible: [],
    executionHost: e.execution_host ?? null
  };
}
function si(e, t) {
  return {
    instanceId: t,
    runId: e.run_id,
    phaseId: "",
    name: e.phase_name || t,
    attempt: e.attempt,
    className: "",
    purpose: "",
    order: e.cursor,
    constructed: !1,
    started: !1,
    outcome: null,
    abandoned: !1,
    startedAt: 0,
    endedAt: 0,
    lastProgressAt: 0,
    waitDeadlineAt: null,
    waitReason: "",
    cleanup: "",
    error: ""
  };
}
function Fl(e, t) {
  return t.phase_id && e.instanceOfPhase[t.phase_id] ? e.instanceOfPhase[t.phase_id] : t.instance_id || t.phase_id;
}
function Nl(e, t) {
  const s = t.instance_id, n = e.phases[t.phase_id], r = e.phases[s] ?? si(t, s);
  return n && n !== r && (r.started = r.started || n.started, r.startedAt = r.startedAt || n.startedAt, r.lastProgressAt = Math.max(
    r.lastProgressAt,
    n.lastProgressAt
  ), r.outcome = r.outcome ?? n.outcome, delete e.phases[t.phase_id], Pl(e, t.phase_id, s)), e.phases[s] = r, e.instanceOfPhase[t.phase_id] = s, r.phaseId = t.phase_id, r;
}
function rs(e, t, s, n, r, i) {
  e.arrows.push({
    id: t.event_id,
    cursor: t.cursor,
    at: Date.parse(t.recorded_at) || 0,
    kind: t.kind,
    from: s,
    to: n,
    text: r,
    dashed: i
  });
}
function kl(e, t, s) {
  if (t.kind === "progress") {
    t.message && rs(e, t, s, s, t.message, !1);
    return;
  }
  if (t.kind !== "tool_call" && t.kind !== "tool_result" && t.kind !== "message")
    return;
  const n = t.kind === "message" && t.source_instance && t.target_instance;
  rs(
    e,
    t,
    n ? t.source_instance : s,
    n ? t.target_instance : s,
    t.message,
    t.kind === "tool_result"
  );
}
function Ll(e, t) {
  if (!e || !t) return "";
  const s = Math.max(0, t - e);
  return s < 1e3 ? `${Math.round(s)} ms` : `${(s / 1e3).toFixed(1)}s`;
}
function Hl(e, t) {
  var i;
  const s = Date.parse(t.recorded_at) || 0, n = Fl(e, t);
  if (!n) return;
  let r;
  if (t.kind === "bound" ? r = Nl(e, t) : ((i = e.phases)[n] ?? (i[n] = si(t, n)), r = e.phases[n]), t.attempt !== null && t.attempt !== void 0 && (r.attempt = t.attempt), kl(e, t, r.instanceId), t.kind === "constructed" ? (r.constructed = !0, r.className = t.message) : t.kind === "purpose" ? r.purpose = t.message : t.kind === "cleanup" ? (r.cleanup = t.message, !r.started && r.outcome === null && (r.abandoned = !0)) : t.kind === "error" && (r.error = t.message), r.outcome !== null || r.abandoned) {
    qt(e);
    return;
  }
  if (t.kind === "phase_end" && t.status && t.status !== "running") {
    r.outcome = t.status, r.endedAt = s, r.started = !0, rs(
      e,
      t,
      r.instanceId,
      Ws,
      [t.status, Ll(r.startedAt, s), r.error].filter(Boolean).join(" · "),
      !0
    ), qt(e);
    return;
  }
  if (t.kind === "waiting" ? (r.waitDeadlineAt = t.deadline_at ? Date.parse(t.deadline_at) : null, r.waitReason = t.message, r.lastProgressAt = s) : Dl.has(t.kind) && (r.waitDeadlineAt = null, r.waitReason = "", r.lastProgressAt = s), (t.kind === "phase_start" || t.kind === "bound") && !r.started) {
    r.started = !0, r.startedAt = s, t.kind === "phase_start" && (r.phaseId = t.phase_id), rs(e, t, Ws, r.instanceId, r.name, !1), qt(e);
    return;
  }
  qt(e);
}
function jl(e) {
  const t = [e.run_id, e.phase_name, e.kind].filter(Boolean).join(" ");
  return `${e.recorded_at} [${t}] ${e.message}`;
}
function Bl(e, t) {
  var i, o, l, u;
  const s = t.events.filter((f) => !e.seen[f.event_id]), n = t.runs.some((f) => {
    const d = e.runs[f.run_id];
    return !d || d.status !== f.status || d.endedAt !== f.ended_at;
  });
  if (s.length === 0 && !n) return e;
  const r = structuredClone(e);
  for (const f of t.runs) {
    (i = r.runs)[o = f.run_id] ?? (i[o] = Vn(f));
    const d = r.runs[f.run_id];
    d.status = f.status, d.endedAt = f.ended_at, d.executionHost = f.execution_host ?? d.executionHost;
  }
  for (const f of s.sort((d, p) => d.cursor - p.cursor)) {
    r.seen[f.event_id] = !0, r.maxCursor = Math.max(r.maxCursor, f.cursor), (l = r.runs)[u = f.run_id] ?? (l[u] = Vn({
      run_id: f.run_id,
      adw_name: f.adw_name,
      status: "running",
      started_at: f.recorded_at,
      ended_at: null,
      execution_host: f.execution_host ?? null
    }));
    const d = r.runs[f.run_id];
    Hl(d, f), r.logs.push({
      cursor: f.cursor,
      eventId: f.event_id,
      runId: f.run_id,
      phaseId: f.phase_id,
      instanceId: f.instance_id,
      recordedAt: f.recorded_at,
      kind: f.kind,
      text: jl(f)
    });
  }
  return r.logs.sort((f, d) => f.cursor - d.cursor), r.logs.length > Un && r.logs.splice(0, r.logs.length - Un), r;
}
function ni(e) {
  return [
    e.adw_id,
    e.task_id,
    e.bridge_task_id,
    e.request_id
  ].filter(Boolean);
}
function Wl(e) {
  return [...new Set(e.map((t) => t.agent).filter(Boolean))].sort();
}
function Ul(e, t) {
  return !(t.agent && e.agent !== t.agent || t.runId && !ni(e).includes(t.runId));
}
function Vl(e, t) {
  return {
    key: `${t}:${e.at}:${e.kind}:${e.source}`,
    at: e.at,
    machine: e.machine,
    agent: e.agent,
    kind: e.kind,
    state: e.state,
    text: e.message,
    ids: ni(e).join(" · ")
  };
}
function Kl(e, t) {
  return e.filter((s) => Ul(s, t)).map((s, n) => Vl(s, n));
}
function Gl(e) {
  for (let t = e.length - 1; t >= 0; t -= 1)
    if (e[t].kind === "status") return e[t].state;
  return "";
}
const ql = {
  idle: "Idle -- no ADW run recorded yet",
  live: "Live",
  completed: "Completed",
  pinned: "Pinned after failure"
}, ri = {
  waiting: "Waiting",
  running: "Running",
  stalled: "Stalled",
  fail: "Fail",
  pass: "Pass"
};
function Us(e, t) {
  if (!e) return "";
  const s = Math.max(0, Math.round((t - e) / 1e3));
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
}
function Jl(e, t, s, n, r, i) {
  let o = "waiting", l = "";
  if (e.outcome === "pass" || e.outcome === "fail")
    o = e.outcome, l = [Us(e.startedAt, e.endedAt), e.error].filter(Boolean).join(" -- ");
  else if (e.abandoned)
    l = "never executed";
  else if (!e.started)
    l = "constructed, not started";
  else if (t.status !== "running")
    o = "stalled", l = t.status === "interrupted" ? "process ended without recording an outcome; no cleanup recorded" : `run ended (${t.status}) without an outcome for this phase`;
  else {
    const u = r.evaluate(
      {
        started: e.started,
        terminal: ti(e),
        lastProgressAt: e.lastProgressAt,
        waitDeadlineAt: e.waitDeadlineAt,
        waitReason: e.waitReason
      },
      s,
      n
    );
    o = u ? "stalled" : e.waitDeadlineAt !== null ? "waiting" : "running", l = [
      Us(e.startedAt, s),
      (u == null ? void 0 : u.reason) ?? e.waitReason
    ].filter(Boolean).join(" -- ");
  }
  return {
    instanceId: e.instanceId,
    name: e.name,
    attempt: e.attempt,
    status: o,
    statusLabel: ri[o],
    detail: l,
    purpose: e.purpose,
    selected: i
  };
}
const zl = {
  running: "running",
  success: "pass",
  fail: "fail",
  interrupted: "stalled"
};
function Yl(e, t) {
  const s = zl[e.status] ?? "waiting", n = Date.parse(e.startedAt) || 0, r = e.endedAt && Date.parse(e.endedAt) || t;
  return {
    instanceId: Ws,
    kind: "runner",
    name: e.adwName,
    attempt: null,
    status: s,
    statusLabel: ri[s],
    detail: Us(n, r),
    purpose: `ADW run ${e.runId}: starts each phase and receives its outcome`,
    selected: !1
  };
}
function Xl(e, t) {
  if (!e || !t) return "";
  const s = Math.max(0, t - e);
  return s >= 1e4 ? `+${(s / 1e3).toFixed(1)} s` : `+${s} ms`;
}
function Zl(e, t, s, n, r) {
  var p;
  if (!e) return { runId: "", columns: [], rows: [] };
  const i = e.visible.map((m) => e.phases[m]).filter(Boolean).map((m) => ({
    ...Jl(
      m,
      e,
      t,
      s,
      n,
      m.instanceId === r
    ),
    kind: "phase"
  }));
  if (i.length === 0) return { runId: e.runId, columns: [], rows: [] };
  const o = [Yl(e, t), ...i], l = new Map(
    o.map((m, x) => [m.instanceId, x])
  ), u = Date.parse(e.startedAt) || (((p = e.arrows[0]) == null ? void 0 : p.at) ?? 0), d = e.arrows.filter((m) => l.has(m.from) && l.has(m.to)).sort((m, x) => m.cursor - x.cursor).map((m) => ({
    id: m.id,
    from: l.get(m.from),
    to: l.get(m.to),
    text: m.text,
    dashed: m.dashed,
    kind: m.kind,
    elapsed: Xl(u, m.at)
  }));
  for (const m of o) {
    if (m.kind === "runner") {
      m.activeFrom = d.length ? 0 : null, m.activeTo = e.status === "running" ? null : d.length - 1;
      continue;
    }
    const x = l.get(m.instanceId), R = d.findIndex((D) => D.to === x || D.from === x), C = d.findIndex(
      (D) => D.kind === "phase_end" && D.from === x
    ), G = e.phases[m.instanceId];
    m.activeFrom = G != null && G.started && R >= 0 ? R : null, m.activeTo = C >= 0 ? C : null;
  }
  return { runId: e.runId, columns: o, rows: d };
}
function Ql(e) {
  const t = e.replace(/\.py$/, "").replace(/^adw_/, "").replace(/^(interface|op)_/, "").replace(/_/g, " ").trim();
  return t ? t[0].toUpperCase() + t.slice(1) : "An ADW";
}
function ec(e) {
  if (!e) return "No ADW has run yet -- the next one started will show here";
  const t = Ql(e.adwName), s = e.visible.map((f) => e.phases[f]).filter(Boolean), n = s.length, i = s.filter((f) => f.started && !ti(f)).at(-1), o = s.find((f) => f.outcome === "fail"), l = (f) => `step ${s.indexOf(f) + 1} of ${n}, ${f.name.replace(/_/g, " ")}`, u = (f) => `${f} step${f === 1 ? "" : "s"}`;
  switch (e.status) {
    case "running":
      return i ? `Running now: ${t} -- ${l(i)}` : n === 0 ? `Running now: ${t} -- starting up` : `Running now: ${t} -- between steps, ${s.filter((f) => f.outcome).length} of ${n} done`;
    case "success":
      return `Finished: ${t} -- all ${u(n)} passed`;
    case "fail":
      return o ? `Failed: ${t} -- stopped at ${l(o)}` : `Failed: ${t} -- after ${u(n)}`;
    case "interrupted":
      return i ? `Stopped: ${t} -- its process ended during ${l(i)}` : `Stopped: ${t} -- its process ended without finishing`;
    default:
      return `${t} -- ${u(n)}`;
  }
}
function tc(e, t, s, n) {
  var i;
  const r = s.mode === "phase" ? (i = n.runs[s.runId]) == null ? void 0 : i.phases[s.instanceId] : void 0;
  return {
    headline: ec(e),
    modeLabel: ql[t],
    filterLabel: s.mode === "all" ? "All events" : `Run ${s.runId} -- phase ${(r == null ? void 0 : r.name) ?? s.instanceId} (${s.instanceId}${r != null && r.attempt ? `, attempt ${r.attempt}` : ""})`,
    clearLabel: e ? `Clear displayed logs for ${e.runId}` : "Clear displayed logs",
    clearDisabledReason: e ? "" : "No ADW run is selected, so there is nothing run-scoped to clear."
  };
}
class sc {
  constructor(t) {
    j(this, "state", Rl());
    j(this, "selected", { runId: null, pinReleased: !1 });
    j(this, "filter", { mode: "all" });
    j(this, "connection", { status: "connecting" });
    j(this, "timeoutSeconds", 120);
    j(this, "lastDelayMs", null);
    j(this, "renderError", "");
    j(this, "dadsComputerOnly", !1);
    j(this, "supervisorEvents", []);
    j(this, "supervisorGaps", []);
    j(this, "supervisorError", "");
    j(this, "supervisorMachine", "");
    j(this, "supervisorAgent", "");
    j(this, "supervisorCorrelate", !1);
    j(this, "unsubscribeSupervisor", null);
    j(this, "tick", null);
    j(this, "unsubscribe", null);
    j(this, "listeners", /* @__PURE__ */ new Set());
    this.deps = t;
  }
  start() {
    var s, n;
    this.unsubscribe = this.deps.source.subscribe({
      onPage: (r) => this.onPage(r),
      onConnection: (r) => {
        this.connection = r, this.publish();
      }
    }), this.deps.source.start(), this.unsubscribeSupervisor = ((s = this.deps.supervisor) == null ? void 0 : s.subscribe({
      onPage: (r) => this.onSupervisorPage(r),
      onConnection: (r) => {
        this.supervisorError = r.status === "disconnected" || r.status === "degraded" ? r.reason : "", this.publish();
      }
    })) ?? null, (n = this.deps.supervisor) == null || n.start();
    const t = () => {
      this.publish(), this.tick = this.deps.timer.set(t, this.deps.tickMs ?? 1e3);
    };
    this.tick = this.deps.timer.set(t, this.deps.tickMs ?? 1e3);
  }
  /** The view came into sight: catch up now rather than on the slow cadence. */
  wake() {
    var t;
    this.deps.source.wake(), (t = this.deps.supervisor) == null || t.wake();
  }
  dispose() {
    var t, s, n;
    this.deps.source.stop(), (t = this.unsubscribe) == null || t.call(this), (s = this.deps.supervisor) == null || s.stop(), (n = this.unsubscribeSupervisor) == null || n.call(this), this.deps.timer.clear(this.tick), this.deps.legacy.setVisible(!0), this.listeners.clear();
  }
  subscribe(t) {
    return this.listeners.add(t), t(this.view()), () => {
      this.listeners.delete(t);
    };
  }
  selectPhase(t) {
    this.selected.runId && (this.filter = { mode: "phase", runId: this.selected.runId, instanceId: t }, this.publish());
  }
  allEvents() {
    this.filter = { mode: "all" }, this.publish();
  }
  followLive() {
    this.follow(this.deps.selection.followLive(this.selected, this.runs())), this.publish();
  }
  toggleDadsComputerOnly() {
    this.dadsComputerOnly = !this.dadsComputerOnly;
    const t = this.selected.runId ? this.state.runs[this.selected.runId] : void 0;
    this.dadsComputerOnly && t && !$s(t) && (this.selected = { runId: null, pinReleased: !1 }, this.filter = { mode: "all" }), this.follow(this.deps.selection.select(this.selected, this.runs())), this.publish();
  }
  /** Point the supervisor pane at another machine. Never touches the run's own events. */
  selectSupervisorMachine(t) {
    var s;
    t !== this.supervisorMachine && (this.supervisorMachine = t, this.supervisorEvents = [], this.supervisorGaps = [], this.supervisorAgent = "", (s = this.deps.supervisor) == null || s.setMachine(t), this.publish());
  }
  selectSupervisorAgent(t) {
    this.supervisorAgent = t, this.publish();
  }
  /** Show only the records that carry the selected run's id. Off by default. */
  toggleSupervisorCorrelation() {
    this.supervisorCorrelate = !this.supervisorCorrelate, this.publish();
  }
  /** Clears the run's terminal view only; supervisor and audit records are never removed. */
  clearSelectedRun() {
    this.selected.runId && (Ol(this.state, this.selected.runId, this.deps.cleared), this.publish());
  }
  reportRenderError(t) {
    this.renderError = t, this.publish();
  }
  runs() {
    return Object.values(this.state.runs).filter((t) => !this.dadsComputerOnly || $s(t)).map((t) => ({
      runId: t.runId,
      status: t.status,
      startedAt: t.startedAt
    }));
  }
  onSupervisorPage(t) {
    var s, n;
    (n = (s = this.deps.clock).align) == null || n.call(s, t.server_now), this.supervisorEvents = t.supervisor_events, this.supervisorGaps = t.gaps, this.publish();
  }
  supervisorView(t) {
    const s = this.supervisorCorrelate && t !== null, n = Kl(this.supervisorEvents, {
      agent: this.supervisorAgent,
      runId: s ? t : null
    });
    return {
      available: this.deps.supervisor !== void 0,
      machine: this.supervisorMachine,
      machines: this.deps.machines ?? [""],
      agents: Wl(this.supervisorEvents),
      agent: this.supervisorAgent,
      correlate: this.supervisorCorrelate,
      correlateLabel: t ? `Only records for run ${t}` : "Only records for the selected run (no run selected)",
      lines: n,
      total: this.supervisorEvents.length,
      gaps: this.supervisorGaps,
      error: this.supervisorError,
      awake: Gl(this.supervisorEvents)
    };
  }
  follow(t) {
    t.runId !== this.selected.runId && (this.filter = { mode: "all" }), this.selected = t;
  }
  onPage(t) {
    var n, r;
    (r = (n = this.deps.clock).align) == null || r.call(n, t.server_now), this.timeoutSeconds = t.stall_timeout_seconds;
    const s = this.state;
    if (this.state = Bl(this.state, t), !t.bootstrap && this.state !== s && t.events.length > 0) {
      const i = Date.parse(
        t.events[t.events.length - 1].recorded_at
      );
      Number.isNaN(i) || (this.lastDelayMs = Math.max(0, this.deps.clock.now() - i));
    }
    this.follow(this.deps.selection.select(this.selected, this.runs())), this.publish();
  }
  view() {
    const t = this.selected.runId ? this.state.runs[this.selected.runId] : void 0, s = this.deps.selection.mode(this.selected, this.runs()), n = this.filter.mode === "phase" && this.filter.runId === (t == null ? void 0 : t.runId) ? this.filter.instanceId : null, r = this.deps.renderer.render(
      Zl(
        t,
        this.deps.clock.now(),
        this.timeoutSeconds * 1e3,
        this.deps.stall,
        n
      )
    ), i = Object.values(this.state.runs), o = this.dadsComputerOnly ? i.filter($s) : i;
    return {
      runId: (t == null ? void 0 : t.runId) ?? null,
      adwName: (t == null ? void 0 : t.adwName) ?? "",
      runStatus: (t == null ? void 0 : t.status) ?? null,
      mode: s,
      diagram: r.model,
      lines: Tl(this.state, this.filter, this.deps.cleared),
      phaseSelected: this.filter.mode === "phase",
      connection: this.connection,
      renderError: r.error || this.renderError,
      stallTimeoutSeconds: this.timeoutSeconds,
      lastDelayMs: this.lastDelayMs,
      dadsComputerOnly: this.dadsComputerOnly,
      dadsComputerFilterAvailable: i.some($l),
      dadsComputerVisibleRuns: o.length,
      supervisor: this.supervisorView((t == null ? void 0 : t.runId) ?? null),
      ...tc(t, s, this.filter, this.state)
    };
  }
  publish() {
    this.deps.legacy.setVisible(this.filter.mode === "all");
    const t = this.view();
    for (const s of this.listeners) s(t);
  }
}
class nc {
  constructor(t) {
    this.runId = t;
  }
  select() {
    return { runId: this.runId, pinReleased: !0 };
  }
  followLive() {
    return this.select();
  }
  mode(t, s) {
    const n = s.find((r) => r.runId === t.runId);
    return n ? n.status === "running" ? "live" : "completed" : "idle";
  }
}
function Ts(e) {
  return `${Math.max(0, Math.round(e / 1e3))}s`;
}
class rc {
  evaluate(t, s, n) {
    if (!t.started || t.terminal) return null;
    if (t.waitDeadlineAt !== null) {
      const i = s - t.waitDeadlineAt;
      return i > 0 ? {
        reason: `wait deadline passed ${Ts(i)} ago: ${t.waitReason}`
      } : null;
    }
    const r = s - t.lastProgressAt;
    return r > n ? {
      reason: `no progress for ${Ts(r)} (timeout ${Ts(n)})`
    } : null;
  }
}
class ic {
  async getJSON(t) {
    const s = await fetch(t, { cache: "no-store" });
    if (!s.ok) throw new Error(`HTTP ${s.status} from ${t}`);
    return s.json();
  }
}
class oc {
  set(t, s) {
    return window.setTimeout(t, s);
  }
  clear(t) {
    window.clearTimeout(t);
  }
}
class lc {
  constructor() {
    j(this, "offset", 0);
  }
  align(t) {
    const s = Date.parse(t);
    Number.isNaN(s) || (this.offset = s - Date.now());
  }
  now() {
    return Date.now() + this.offset;
  }
}
class cc {
  setVisible() {
  }
}
class uc {
  get() {
    return 0;
  }
  set() {
  }
}
class ac {
  constructor(t, s, n) {
    j(this, "listeners", /* @__PURE__ */ new Set());
    j(this, "cursor", null);
    j(this, "handle", null);
    j(this, "running", !1);
    j(this, "inflight", !1);
    j(this, "failures", 0);
    this.http = t, this.timer = s, this.options = n;
  }
  subscribe(t) {
    return this.listeners.add(t), () => {
      this.listeners.delete(t);
    };
  }
  start() {
    this.running || (this.running = !0, this.emit({ status: "connecting" }), this.poll());
  }
  stop() {
    this.running = !1, this.timer.clear(this.handle), this.handle = null;
  }
  wake() {
    !this.running || this.inflight || (this.timer.clear(this.handle), this.poll());
  }
  emit(t) {
    for (const s of this.listeners) s.onConnection(t);
  }
  schedule() {
    if (!this.running) return;
    const t = this.failures > 0 ? Math.min(
      this.options.retryStepMs * this.failures,
      this.options.retryMaxMs
    ) : this.options.isActive() ? this.options.activeMs : this.options.idleMs;
    this.handle = this.timer.set(() => void this.poll(), t);
  }
  async poll() {
    if (!(this.inflight || !this.running)) {
      this.inflight = !0;
      try {
        const t = this.cursor === null ? this.options.url : `${this.options.url}${this.options.url.includes("?") ? "&" : "?"}after=${this.cursor}`, s = await this.http.getJSON(t);
        if (!this.running) return;
        if (this.failures = 0, s.ok) {
          this.cursor = Math.max(this.cursor ?? 0, s.cursor), this.emit({ status: "connected" });
          for (const n of this.listeners) n.onPage(s);
        } else
          this.emit({
            status: "degraded",
            reason: s.error || "the feed could not read the trace database"
          });
      } catch (t) {
        this.failures += 1, this.emit({
          status: "disconnected",
          attempts: this.failures,
          reason: t instanceof Error ? t.message : String(t)
        });
      } finally {
        this.inflight = !1, this.schedule();
      }
    }
  }
}
class fc {
  constructor() {
    j(this, "lastGood", { runId: "", columns: [], rows: [] });
  }
  render(t) {
    try {
      const s = /* @__PURE__ */ new Set();
      for (const n of t.columns) {
        if (!n.instanceId || s.has(n.instanceId))
          throw new Error(
            `duplicate or empty phase instance id "${n.instanceId}"`
          );
        s.add(n.instanceId);
      }
      for (const n of t.rows)
        if (!t.columns[n.from] || !t.columns[n.to])
          throw new Error(
            `arrow ${n.id} points at a column that is not on screen`
          );
      return this.lastGood = t, { model: t, error: "" };
    } catch (s) {
      return {
        model: this.lastGood,
        error: s instanceof Error ? s.message : String(s)
      };
    }
  }
}
const dc = { class: "adwdbg-log" }, hc = { class: "adwdbg-log-head" }, pc = { class: "adwdbg-log-label" }, gc = {
  key: 0,
  class: "adwdbg-log-empty"
}, mc = ["data-kind", "data-run"], _c = /* @__PURE__ */ qe({
  __name: "LogPane",
  props: {
    lines: {},
    label: {},
    tall: { type: Boolean }
  },
  setup(e) {
    const t = e, s = et(null), n = et(!0);
    function r() {
      const i = s.value;
      i && (n.value = i.scrollHeight - i.scrollTop - i.clientHeight <= 8);
    }
    return zt(() => t.lines.length, async () => {
      n.value && (await wr(), s.value && (s.value.scrollTop = s.value.scrollHeight));
    }, { immediate: !0 }), (i, o) => (F(), K("div", dc, [
      L("div", hc, [
        L("span", pc, X(i.label), 1),
        L("span", null, X(i.lines.length) + " line" + X(i.lines.length === 1 ? "" : "s") + X(n.value ? "" : " · paused (scroll to bottom to follow)"), 1)
      ]),
      L("div", {
        ref_key: "host",
        ref: s,
        class: Ve(["adwdbg-log-lines", { "adwdbg-log-tall": i.tall }]),
        role: "log",
        onScroll: r
      }, [
        i.lines.length === 0 ? (F(), K("div", gc, "No ADW events to show.")) : Pe("", !0),
        (F(!0), K(ee, null, ut(i.lines, (l) => (F(), K("div", {
          key: l.eventId,
          class: "adwdbg-log-line",
          "data-kind": l.kind,
          "data-run": l.runId
        }, X(l.text), 9, mc))), 128))
      ], 34)
    ]));
  }
}), It = 78, bc = 170, Nt = 40, an = 22, Os = 11;
function Vs(e, t) {
  return (e + 0.5) / Math.max(1, t) * 100;
}
function vc(e) {
  return 100 / Math.max(1, e);
}
function is(e) {
  return an + e * Nt + Nt * 0.62;
}
function ii(e) {
  return an * 2 + Math.max(1, e) * Nt;
}
function wc(e, t, s) {
  const n = is(e) - Os, r = t === null ? ii(s) - an / 2 : is(Math.max(e, t)) + Os;
  return { top: n, height: Math.max(Os * 2, r - n) };
}
function yc(e, t) {
  return e === t ? "self" : e < t ? "right" : "left";
}
const xc = ["data-status"], Sc = /* @__PURE__ */ qe({
  __name: "ActivationBar",
  props: {
    from: {},
    to: {},
    rows: {},
    status: {}
  },
  setup(e) {
    const t = e, s = nt(() => wc(t.from, t.to, t.rows));
    return (n, r) => (F(), K("span", {
      class: Ve(["sd-bar", { "sd-bar-open": n.to === null }]),
      "data-status": n.status,
      style: pe({ top: `${s.value.top}px`, height: `${s.value.height}px` })
    }, null, 14, xc));
  }
}), Ic = ["data-lifeline"], Ac = /* @__PURE__ */ qe({
  __name: "Lifeline",
  props: {
    column: {},
    centre: {},
    rows: {}
  },
  setup(e) {
    return (t, s) => (F(), K("div", {
      class: "sd-lifeline-track",
      "data-lifeline": t.column.instanceId,
      style: pe({ left: `${t.centre}%` })
    }, [
      s[0] || (s[0] = L("span", { class: "sd-lifeline" }, null, -1)),
      t.column.activeFrom !== null && t.column.activeFrom !== void 0 ? (F(), tt(Sc, {
        key: 0,
        from: t.column.activeFrom,
        to: t.column.activeTo ?? null,
        rows: t.rows,
        status: t.column.status
      }, null, 8, ["from", "to", "rows", "status"])) : Pe("", !0)
    ], 12, Ic));
  }
}), Cc = ["data-kind", "data-row"], Ec = ["title"], $c = { class: "sd-label-text" }, Tc = /* @__PURE__ */ qe({
  __name: "MessageArrow",
  props: {
    row: {},
    index: {},
    count: {}
  },
  setup(e) {
    const t = e, s = nt(() => yc(t.row.from, t.row.to)), n = nt(() => {
      const r = `${is(t.index) - Nt * 0.62}px`, i = `${Nt}px`, o = Vs(t.row.from, t.count);
      if (s.value === "self") {
        const u = t.row.from === t.count - 1 ? 0.46 : 0.92;
        return { top: r, height: i, left: `${o}%`, width: `${vc(t.count) * u}%` };
      }
      const l = Vs(t.row.to, t.count);
      return { top: r, height: i, left: `${Math.min(o, l)}%`, width: `${Math.abs(l - o)}%` };
    });
    return (r, i) => (F(), K("div", {
      class: Ve(["sd-message", [`sd-${s.value}`, { "sd-dashed": r.row.dashed }]]),
      "data-kind": r.row.kind,
      "data-row": r.index,
      style: pe(n.value)
    }, [
      L("div", {
        class: "sd-label",
        title: r.row.text
      }, [
        L("span", $c, X(r.row.text), 1)
      ], 8, Ec),
      i[0] || (i[0] = L("div", { class: "sd-line" }, [
        L("span", { class: "sd-head" })
      ], -1))
    ], 14, Cc));
  }
}), Oc = ["data-status", "data-instance", "data-edge", "data-participant", "title", "aria-pressed"], Rc = { class: "sd-name" }, Mc = { class: "sd-status" }, Kn = /* @__PURE__ */ qe({
  __name: "ParticipantBox",
  props: {
    column: {},
    edge: {}
  },
  emits: ["select"],
  setup(e, { emit: t }) {
    const s = e, n = t;
    function r() {
      return [s.column.purpose, s.column.detail, s.column.instanceId].filter(Boolean).join(`
`);
    }
    return (i, o) => (F(), K("button", {
      type: "button",
      class: Ve(["sd-box", { "sd-selected": i.column.selected, "sd-runner": i.column.kind === "runner" }]),
      "data-status": i.column.status,
      "data-instance": i.column.instanceId,
      "data-edge": i.edge,
      "data-participant": i.column.kind ?? "phase",
      title: r(),
      "aria-pressed": i.column.selected,
      onClick: o[0] || (o[0] = (l) => n("select", i.column))
    }, [
      L("span", Rc, [
        St(X(i.column.name), 1),
        i.column.attempt && i.column.attempt > 1 ? (F(), K(ee, { key: 0 }, [
          St(" · attempt " + X(i.column.attempt), 1)
        ], 64)) : Pe("", !0)
      ]),
      L("span", Mc, [
        St(X(i.column.statusLabel), 1),
        i.column.detail ? (F(), K(ee, { key: 0 }, [
          St(" · " + X(i.column.detail), 1)
        ], 64)) : Pe("", !0)
      ])
    ], 10, Oc));
  }
}), Pc = /* @__PURE__ */ qe({
  __name: "TimeAxis",
  props: {
    rows: {}
  },
  setup(e) {
    return (t, s) => (F(), K("div", {
      class: "sd-axis",
      style: pe({ width: `${He(It)}px` }),
      "aria-hidden": "true"
    }, [
      (F(!0), K(ee, null, ut(t.rows, (n, r) => (F(), K("span", {
        key: n.id,
        class: "sd-tick",
        style: pe({ top: `${He(is)(r)}px` })
      }, X(n.elapsed), 5))), 128))
    ], 4));
  }
}), Dc = { class: "sd" }, Fc = { class: "sd-tools" }, Nc = { class: "sd-zoom-value" }, kc = { class: "sd-hint" }, Lc = { class: "sd-frozen" }, Hc = /* @__PURE__ */ qe({
  __name: "SequenceDiagram",
  props: {
    model: {},
    hint: { default: "Click a phase box to filter the events below; click the ADW box for all events." }
  },
  emits: ["phase-click", "runner-click"],
  setup(e, { emit: t }) {
    const s = e, n = t, r = et(1), i = et(null), o = et(null), l = et(!1);
    let u = null;
    $r(() => {
      typeof IntersectionObserver > "u" || !i.value || !o.value || (u = new IntersectionObserver(([x]) => {
        l.value = x.isIntersecting;
      }, { root: i.value }), u.observe(o.value));
    }), on(() => u == null ? void 0 : u.disconnect());
    const f = nt(() => Math.max(1, s.model.columns.length)), d = nt(() => s.model.rows.length), p = nt(() => `${It + f.value * bc}px`);
    function m(x) {
      x.kind === "runner" ? n("runner-click") : n("phase-click", x.instanceId);
    }
    return (x, R) => (F(), K("div", Dc, [
      L("div", Fc, [
        L("button", {
          type: "button",
          class: "sd-zoom",
          "aria-label": "Zoom out",
          onClick: R[0] || (R[0] = (C) => r.value = Math.max(0.4, r.value - 0.1))
        }, "-"),
        L("span", Nc, X(Math.round(r.value * 100)) + "%", 1),
        L("button", {
          type: "button",
          class: "sd-zoom",
          "aria-label": "Zoom in",
          onClick: R[1] || (R[1] = (C) => r.value = Math.min(2, r.value + 0.1))
        }, "+"),
        L("button", {
          type: "button",
          class: "sd-zoom",
          onClick: R[2] || (R[2] = (C) => r.value = 1)
        }, "Reset"),
        L("span", kc, X(x.hint), 1)
      ]),
      L("div", {
        ref_key: "scroller",
        ref: i,
        class: "sd-scroll"
      }, [
        L("div", {
          class: "sd-canvas",
          style: pe({ zoom: r.value, minWidth: p.value })
        }, [
          L("div", Lc, [
            L("div", {
              class: Ve(["sd-titles sd-titles-top", { "sd-pinned": !l.value }]),
              style: pe({ paddingLeft: `${He(It)}px` })
            }, [
              (F(!0), K(ee, null, ut(x.model.columns, (C) => (F(), tt(Kn, {
                key: C.instanceId,
                column: C,
                edge: "top",
                onSelect: m
              }, null, 8, ["column"]))), 128))
            ], 6),
            L("div", {
              class: "sd-body",
              style: pe({ height: `${He(ii)(d.value)}px` })
            }, [
              be(Pc, {
                rows: x.model.rows
              }, null, 8, ["rows"]),
              L("div", {
                class: "sd-plot",
                style: pe({ left: `${He(It)}px` })
              }, [
                (F(!0), K(ee, null, ut(x.model.columns, (C, G) => (F(), tt(Ac, {
                  key: C.instanceId,
                  column: C,
                  centre: He(Vs)(G, f.value),
                  rows: d.value
                }, null, 8, ["column", "centre", "rows"]))), 128)),
                (F(!0), K(ee, null, ut(x.model.rows, (C, G) => (F(), tt(Tc, {
                  key: C.id,
                  row: C,
                  index: G,
                  count: f.value
                }, null, 8, ["row", "index", "count"]))), 128))
              ], 4)
            ], 4)
          ]),
          L("div", {
            ref_key: "bottomRow",
            ref: o,
            class: "sd-titles sd-titles-bottom",
            style: pe({ marginLeft: `${He(It)}px` })
          }, [
            (F(!0), K(ee, null, ut(x.model.columns, (C) => (F(), tt(Kn, {
              key: C.instanceId,
              column: C,
              edge: "bottom",
              onSelect: m
            }, null, 8, ["column"]))), 128))
          ], 4)
        ], 4)
      ], 512)
    ]));
  }
}), jc = {
  key: 0,
  class: "adwseq",
  "aria-label": "ADW run sequence diagram"
}, Bc = { class: "adwseq-head" }, Wc = { "data-field": "headline" }, Uc = ["data-run-status"], Vc = {
  key: 0,
  class: "adwdbg-warn",
  "data-warning": "connection",
  role: "status"
}, Kc = {
  key: 1,
  class: "adwdbg-warn",
  "data-warning": "feed",
  role: "status"
}, Gc = {
  key: 2,
  class: "adwdbg-warn",
  "data-warning": "render",
  role: "alert"
}, qc = { class: "adwseq-stage" }, Jc = {
  key: 1,
  class: "adwdbg-idle",
  "data-field": "idle"
}, zc = ["aria-label"], Gn = "@all", Yc = /* @__PURE__ */ qe({
  __name: "RunSequencePanel",
  props: {
    controller: {}
  },
  setup(e) {
    const t = e, s = Vi(null), n = et(null), r = t.controller.subscribe((l) => {
      s.value = l;
    });
    on(r), Or((l) => (t.controller.reportRenderError(l instanceof Error ? l.message : String(l)), !1));
    function i(l) {
      if (n.value === l) {
        n.value = null, t.controller.allEvents();
        return;
      }
      n.value = l, l === Gn ? t.controller.allEvents() : t.controller.selectPhase(l);
    }
    function o() {
      n.value && i(n.value);
    }
    return (l, u) => s.value ? (F(), K("section", jc, [
      L("header", Bc, [
        L("strong", Wc, X(s.value.headline), 1),
        s.value.runStatus ? (F(), K("span", {
          key: 0,
          class: "adwdbg-chip",
          "data-run-status": s.value.runStatus,
          "data-field": "status"
        }, X(s.value.runStatus), 9, Uc)) : Pe("", !0)
      ]),
      s.value.connection.status === "disconnected" ? (F(), K("p", Vc, " Event feed disconnected (attempt " + X(s.value.connection.attempts) + "): " + X(s.value.connection.reason) + ". Showing the last events received. ", 1)) : s.value.connection.status === "degraded" ? (F(), K("p", Kc, " The ADW trace cannot be read: " + X(s.value.connection.reason), 1)) : Pe("", !0),
      s.value.renderError ? (F(), K("p", Gc, " Diagram could not be redrawn (" + X(s.value.renderError) + "). Showing the last good diagram. ", 1)) : Pe("", !0),
      L("div", qc, [
        s.value.diagram.columns.length ? (F(), tt(Hc, {
          key: 0,
          model: s.value.diagram,
          hint: "Click a phase to open its console; click it again to close.",
          onPhaseClick: u[0] || (u[0] = (f) => i(f)),
          onRunnerClick: u[1] || (u[1] = (f) => i(Gn))
        }, null, 8, ["model"])) : (F(), K("p", Jc, X(s.value.connection.status === "connecting" ? "Loading the run…" : "This run has not started a step yet."), 1)),
        n.value ? (F(), K("div", {
          key: 2,
          class: "adwseq-popup",
          "data-field": "popup",
          role: "dialog",
          "aria-label": s.value.filterLabel
        }, [
          L("button", {
            type: "button",
            class: "adwseq-close",
            "aria-label": "Close console",
            onClick: u[2] || (u[2] = (f) => o())
          }, "×"),
          be(_c, {
            lines: s.value.lines,
            label: s.value.filterLabel,
            tall: !1
          }, null, 8, ["lines", "label"])
        ], 8, zc)) : Pe("", !0)
      ])
    ])) : Pe("", !0);
  }
});
function Qc(e, t) {
  const s = new oc();
  let n = !0;
  const r = new sc({
    source: new ac(new ic(), s, {
      url: t.url,
      activeMs: 1500,
      idleMs: 15e3,
      retryStepMs: 2e3,
      retryMaxMs: 15e3,
      isActive: () => n && document.visibilityState !== "hidden"
    }),
    selection: new nc(t.runId),
    stall: new rc(),
    renderer: new fc(),
    cleared: new uc(),
    legacy: new cc(),
    clock: new lc(),
    timer: s
  }), i = r.subscribe((l) => {
    n = l.runStatus === "running" || l.runStatus === null;
  }), o = Il(Yc, { controller: r });
  return o.mount(e), r.start(), {
    controller: r,
    unmount() {
      i(), r.dispose(), o.unmount();
    }
  };
}
export {
  Qc as mountRunSequence
};
