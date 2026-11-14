var ii = Object.defineProperty;
var oi = (e, t, s) => t in e ? ii(e, t, { enumerable: !0, configurable: !0, writable: !0, value: s }) : e[t] = s;
var X = (e, t, s) => oi(e, typeof t != "symbol" ? t + "" : t, s);
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
const K = {}, ut = [], Re = () => {
}, li = () => !1, is = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && // uppercase letter
(e.charCodeAt(2) > 122 || e.charCodeAt(2) < 97), Gs = (e) => e.startsWith("onUpdate:"), re = Object.assign, qs = (e, t) => {
  const s = e.indexOf(t);
  s > -1 && e.splice(s, 1);
}, ci = Object.prototype.hasOwnProperty, L = (e, t) => ci.call(e, t), R = Array.isArray, ft = (e) => os(e) === "[object Map]", Gn = (e) => os(e) === "[object Set]", M = (e) => typeof e == "function", Q = (e) => typeof e == "string", Ue = (e) => typeof e == "symbol", q = (e) => e !== null && typeof e == "object", qn = (e) => (q(e) || M(e)) && M(e.then) && M(e.catch), Jn = Object.prototype.toString, os = (e) => Jn.call(e), ai = (e) => os(e).slice(8, -1), zn = (e) => os(e) === "[object Object]", Js = (e) => Q(e) && e !== "NaN" && e[0] !== "-" && "" + parseInt(e, 10) === e, It = /* @__PURE__ */ Ks(
  // the leading comma is intentional so empty string "" is also included
  ",key,ref,ref_for,ref_key,onVnodeBeforeMount,onVnodeMounted,onVnodeBeforeUpdate,onVnodeUpdated,onVnodeBeforeUnmount,onVnodeUnmounted"
), ls = (e) => {
  const t = /* @__PURE__ */ Object.create(null);
  return (s) => t[s] || (t[s] = e(s));
}, ui = /-(\w)/g, We = ls(
  (e) => e.replace(ui, (t, s) => s ? s.toUpperCase() : "")
), fi = /\B([A-Z])/g, ot = ls(
  (e) => e.replace(fi, "-$1").toLowerCase()
), Yn = ls((e) => e.charAt(0).toUpperCase() + e.slice(1)), ms = ls(
  (e) => e ? `on${Yn(e)}` : ""
), Be = (e, t) => !Object.is(e, t), _s = (e, ...t) => {
  for (let s = 0; s < e.length; s++)
    e[s](...t);
}, Xn = (e, t, s, n = !1) => {
  Object.defineProperty(e, t, {
    configurable: !0,
    enumerable: !1,
    writable: n,
    value: s
  });
}, di = (e) => {
  const t = parseFloat(e);
  return isNaN(t) ? e : t;
};
let gn;
const cs = () => gn || (gn = typeof globalThis < "u" ? globalThis : typeof self < "u" ? self : typeof window < "u" ? window : typeof global < "u" ? global : {});
function pe(e) {
  if (R(e)) {
    const t = {};
    for (let s = 0; s < e.length; s++) {
      const n = e[s], r = Q(n) ? mi(n) : pe(n);
      if (r)
        for (const i in r)
          t[i] = r[i];
    }
    return t;
  } else if (Q(e) || q(e))
    return e;
}
const hi = /;(?![^(]*\))/g, pi = /:([^]+)/, gi = /\/\*[^]*?\*\//g;
function mi(e) {
  const t = {};
  return e.replace(gi, "").split(hi).forEach((s) => {
    if (s) {
      const n = s.split(pi);
      n.length > 1 && (t[n[0].trim()] = n[1].trim());
    }
  }), t;
}
function lt(e) {
  let t = "";
  if (Q(e))
    t = e;
  else if (R(e))
    for (let s = 0; s < e.length; s++) {
      const n = lt(e[s]);
      n && (t += n + " ");
    }
  else if (q(e))
    for (const s in e)
      e[s] && (t += s + " ");
  return t.trim();
}
const _i = "itemscope,allowfullscreen,formnovalidate,ismap,nomodule,novalidate,readonly", bi = /* @__PURE__ */ Ks(_i);
function Zn(e) {
  return !!e || e === "";
}
const Qn = (e) => !!(e && e.__v_isRef === !0), j = (e) => Q(e) ? e : e == null ? "" : R(e) || q(e) && (e.toString === Jn || !M(e.toString)) ? Qn(e) ? j(e.value) : JSON.stringify(e, er, 2) : String(e), er = (e, t) => Qn(t) ? er(e, t.value) : ft(t) ? {
  [`Map(${t.size})`]: [...t.entries()].reduce(
    (s, [n, r], i) => (s[bs(n, i) + " =>"] = r, s),
    {}
  )
} : Gn(t) ? {
  [`Set(${t.size})`]: [...t.values()].map((s) => bs(s))
} : Ue(t) ? bs(t) : q(t) && !R(t) && !zn(t) ? String(t) : t, bs = (e, t = "") => {
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
class wi {
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
function yi() {
  return he;
}
let V;
const ws = /* @__PURE__ */ new WeakSet();
class tr {
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
    this.flags & 2 && !(this.flags & 32) || this.flags & 8 || nr(this);
  }
  run() {
    if (!(this.flags & 1))
      return this.fn();
    this.flags |= 2, mn(this), rr(this);
    const t = V, s = _e;
    V = this, _e = !0;
    try {
      return this.fn();
    } finally {
      ir(this), V = t, _e = s, this.flags &= -3;
    }
  }
  stop() {
    if (this.flags & 1) {
      for (let t = this.deps; t; t = t.nextDep)
        Xs(t);
      this.deps = this.depsTail = void 0, mn(this), this.onStop && this.onStop(), this.flags &= -2;
    }
  }
  trigger() {
    this.flags & 64 ? ws.add(this) : this.scheduler ? this.scheduler() : this.runIfDirty();
  }
  /**
   * @internal
   */
  runIfDirty() {
    Ms(this) && this.run();
  }
  get dirty() {
    return Ms(this);
  }
}
let sr = 0, At, Ct;
function nr(e, t = !1) {
  if (e.flags |= 8, t) {
    e.next = Ct, Ct = e;
    return;
  }
  e.next = At, At = e;
}
function zs() {
  sr++;
}
function Ys() {
  if (--sr > 0)
    return;
  if (Ct) {
    let t = Ct;
    for (Ct = void 0; t; ) {
      const s = t.next;
      t.next = void 0, t.flags &= -9, t = s;
    }
  }
  let e;
  for (; At; ) {
    let t = At;
    for (At = void 0; t; ) {
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
function rr(e) {
  for (let t = e.deps; t; t = t.nextDep)
    t.version = -1, t.prevActiveLink = t.dep.activeLink, t.dep.activeLink = t;
}
function ir(e) {
  let t, s = e.depsTail, n = s;
  for (; n; ) {
    const r = n.prevDep;
    n.version === -1 ? (n === s && (s = r), Xs(n), vi(n)) : t = n, n.dep.activeLink = n.prevActiveLink, n.prevActiveLink = void 0, n = r;
  }
  e.deps = t, e.depsTail = s;
}
function Ms(e) {
  for (let t = e.deps; t; t = t.nextDep)
    if (t.dep.version !== t.version || t.dep.computed && (or(t.dep.computed) || t.dep.version !== t.version))
      return !0;
  return !!e._dirty;
}
function or(e) {
  if (e.flags & 4 && !(e.flags & 16) || (e.flags &= -17, e.globalVersion === Mt))
    return;
  e.globalVersion = Mt;
  const t = e.dep;
  if (e.flags |= 2, t.version > 0 && !e.isSSR && e.deps && !Ms(e)) {
    e.flags &= -3;
    return;
  }
  const s = V, n = _e;
  V = e, _e = !0;
  try {
    rr(e);
    const r = e.fn(e._value);
    (t.version === 0 || Be(r, e._value)) && (e._value = r, t.version++);
  } catch (r) {
    throw t.version++, r;
  } finally {
    V = s, _e = n, ir(e), e.flags &= -3;
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
function vi(e) {
  const { prevDep: t, nextDep: s } = e;
  t && (t.nextDep = s, e.prevDep = void 0), s && (s.prevDep = t, e.nextDep = void 0);
}
let _e = !0;
const lr = [];
function Ve() {
  lr.push(_e), _e = !1;
}
function Ke() {
  const e = lr.pop();
  _e = e === void 0 ? !0 : e;
}
function mn(e) {
  const { cleanup: t } = e;
  if (e.cleanup = void 0, t) {
    const s = V;
    V = void 0;
    try {
      t();
    } finally {
      V = s;
    }
  }
}
let Mt = 0;
class xi {
  constructor(t, s) {
    this.sub = t, this.dep = s, this.version = s.version, this.nextDep = this.prevDep = this.nextSub = this.prevSub = this.prevActiveLink = void 0;
  }
}
class Zs {
  constructor(t) {
    this.computed = t, this.version = 0, this.activeLink = void 0, this.subs = void 0, this.map = void 0, this.key = void 0, this.sc = 0;
  }
  track(t) {
    if (!V || !_e || V === this.computed)
      return;
    let s = this.activeLink;
    if (s === void 0 || s.sub !== V)
      s = this.activeLink = new xi(V, this), V.deps ? (s.prevDep = V.depsTail, V.depsTail.nextDep = s, V.depsTail = s) : V.deps = V.depsTail = s, cr(s);
    else if (s.version === -1 && (s.version = this.version, s.nextDep)) {
      const n = s.nextDep;
      n.prevDep = s.prevDep, s.prevDep && (s.prevDep.nextDep = n), s.prevDep = V.depsTail, s.nextDep = void 0, V.depsTail.nextDep = s, V.depsTail = s, V.deps === s && (V.deps = n);
    }
    return s;
  }
  trigger(t) {
    this.version++, Mt++, this.notify(t);
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
function cr(e) {
  if (e.dep.sc++, e.sub.flags & 4) {
    const t = e.dep.computed;
    if (t && !e.dep.subs) {
      t.flags |= 20;
      for (let n = t.deps; n; n = n.nextDep)
        cr(n);
    }
    const s = e.dep.subs;
    s !== e && (e.prevSub = s, s && (s.nextSub = e)), e.dep.subs = e;
  }
}
const Ps = /* @__PURE__ */ new WeakMap(), st = Symbol(
  ""
), $s = Symbol(
  ""
), Pt = Symbol(
  ""
);
function te(e, t, s) {
  if (_e && V) {
    let n = Ps.get(e);
    n || Ps.set(e, n = /* @__PURE__ */ new Map());
    let r = n.get(s);
    r || (n.set(s, r = new Zs()), r.map = n, r.key = s), r.track();
  }
}
function Oe(e, t, s, n, r, i) {
  const o = Ps.get(e);
  if (!o) {
    Mt++;
    return;
  }
  const l = (a) => {
    a && a.trigger();
  };
  if (zs(), t === "clear")
    o.forEach(l);
  else {
    const a = R(e), d = a && Js(s);
    if (a && s === "length") {
      const f = Number(n);
      o.forEach((p, m) => {
        (m === "length" || m === Pt || !Ue(m) && m >= f) && l(p);
      });
    } else
      switch ((s !== void 0 || o.has(void 0)) && l(o.get(s)), d && l(o.get(Pt)), t) {
        case "add":
          a ? d && l(o.get("length")) : (l(o.get(st)), ft(e) && l(o.get($s)));
          break;
        case "delete":
          a || (l(o.get(st)), ft(e) && l(o.get($s)));
          break;
        case "set":
          ft(e) && l(o.get(st));
          break;
      }
  }
  Ys();
}
function ct(e) {
  const t = N(e);
  return t === e ? t : (te(t, "iterate", Pt), me(e) ? t : t.map(se));
}
function as(e) {
  return te(e = N(e), "iterate", Pt), e;
}
const Si = {
  __proto__: null,
  [Symbol.iterator]() {
    return ys(this, Symbol.iterator, se);
  },
  concat(...e) {
    return ct(this).concat(
      ...e.map((t) => R(t) ? ct(t) : t)
    );
  },
  entries() {
    return ys(this, "entries", (e) => (e[1] = se(e[1]), e));
  },
  every(e, t) {
    return Pe(this, "every", e, t, void 0, arguments);
  },
  filter(e, t) {
    return Pe(this, "filter", e, t, (s) => s.map(se), arguments);
  },
  find(e, t) {
    return Pe(this, "find", e, t, se, arguments);
  },
  findIndex(e, t) {
    return Pe(this, "findIndex", e, t, void 0, arguments);
  },
  findLast(e, t) {
    return Pe(this, "findLast", e, t, se, arguments);
  },
  findLastIndex(e, t) {
    return Pe(this, "findLastIndex", e, t, void 0, arguments);
  },
  // flat, flatMap could benefit from ARRAY_ITERATE but are not straight-forward to implement
  forEach(e, t) {
    return Pe(this, "forEach", e, t, void 0, arguments);
  },
  includes(...e) {
    return vs(this, "includes", e);
  },
  indexOf(...e) {
    return vs(this, "indexOf", e);
  },
  join(e) {
    return ct(this).join(e);
  },
  // keys() iterator only reads `length`, no optimisation required
  lastIndexOf(...e) {
    return vs(this, "lastIndexOf", e);
  },
  map(e, t) {
    return Pe(this, "map", e, t, void 0, arguments);
  },
  pop() {
    return yt(this, "pop");
  },
  push(...e) {
    return yt(this, "push", e);
  },
  reduce(e, ...t) {
    return _n(this, "reduce", e, t);
  },
  reduceRight(e, ...t) {
    return _n(this, "reduceRight", e, t);
  },
  shift() {
    return yt(this, "shift");
  },
  // slice could use ARRAY_ITERATE but also seems to beg for range tracking
  some(e, t) {
    return Pe(this, "some", e, t, void 0, arguments);
  },
  splice(...e) {
    return yt(this, "splice", e);
  },
  toReversed() {
    return ct(this).toReversed();
  },
  toSorted(e) {
    return ct(this).toSorted(e);
  },
  toSpliced(...e) {
    return ct(this).toSpliced(...e);
  },
  unshift(...e) {
    return yt(this, "unshift", e);
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
const Ii = Array.prototype;
function Pe(e, t, s, n, r, i) {
  const o = as(e), l = o !== e && !me(e), a = o[t];
  if (a !== Ii[t]) {
    const p = a.apply(e, i);
    return l ? se(p) : p;
  }
  let d = s;
  o !== e && (l ? d = function(p, m) {
    return s.call(this, se(p), m, e);
  } : s.length > 2 && (d = function(p, m) {
    return s.call(this, p, m, e);
  }));
  const f = a.call(o, d, n);
  return l && r ? r(f) : f;
}
function _n(e, t, s, n) {
  const r = as(e);
  let i = s;
  return r !== e && (me(e) ? s.length > 3 && (i = function(o, l, a) {
    return s.call(this, o, l, a, e);
  }) : i = function(o, l, a) {
    return s.call(this, o, se(l), a, e);
  }), r[t](i, ...n);
}
function vs(e, t, s) {
  const n = N(e);
  te(n, "iterate", Pt);
  const r = n[t](...s);
  return (r === -1 || r === !1) && sn(s[0]) ? (s[0] = N(s[0]), n[t](...s)) : r;
}
function yt(e, t, s = []) {
  Ve(), zs();
  const n = N(e)[t].apply(e, s);
  return Ys(), Ke(), n;
}
const Ai = /* @__PURE__ */ Ks("__proto__,__v_isRef,__isVue"), ar = new Set(
  /* @__PURE__ */ Object.getOwnPropertyNames(Symbol).filter((e) => e !== "arguments" && e !== "caller").map((e) => Symbol[e]).filter(Ue)
);
function Ci(e) {
  Ue(e) || (e = String(e));
  const t = N(this);
  return te(t, "has", e), t.hasOwnProperty(e);
}
class ur {
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
      return n === (r ? i ? ki : pr : i ? hr : dr).get(t) || // receiver is not the reactive proxy, but has the same prototype
      // this means the receiver is a user proxy of the reactive proxy
      Object.getPrototypeOf(t) === Object.getPrototypeOf(n) ? t : void 0;
    const o = R(t);
    if (!r) {
      let a;
      if (o && (a = Si[s]))
        return a;
      if (s === "hasOwnProperty")
        return Ci;
    }
    const l = Reflect.get(
      t,
      s,
      // if this is a proxy wrapping a ref, return methods using the raw ref
      // as receiver so that we don't have to call `toRaw` on the ref in all
      // its class methods
      ne(t) ? t : n
    );
    return (Ue(s) ? ar.has(s) : Ai(s)) || (r || te(t, "get", s), i) ? l : ne(l) ? o && Js(s) ? l : l.value : q(l) ? r ? gr(l) : en(l) : l;
  }
}
class fr extends ur {
  constructor(t = !1) {
    super(!1, t);
  }
  set(t, s, n, r) {
    let i = t[s];
    if (!this._isShallow) {
      const a = rt(i);
      if (!me(n) && !rt(n) && (i = N(i), n = N(n)), !R(t) && ne(i) && !ne(n))
        return a ? !1 : (i.value = n, !0);
    }
    const o = R(t) && Js(s) ? Number(s) < t.length : L(t, s), l = Reflect.set(
      t,
      s,
      n,
      ne(t) ? t : r
    );
    return t === N(r) && (o ? Be(n, i) && Oe(t, "set", s, n) : Oe(t, "add", s, n)), l;
  }
  deleteProperty(t, s) {
    const n = L(t, s);
    t[s];
    const r = Reflect.deleteProperty(t, s);
    return r && n && Oe(t, "delete", s, void 0), r;
  }
  has(t, s) {
    const n = Reflect.has(t, s);
    return (!Ue(s) || !ar.has(s)) && te(t, "has", s), n;
  }
  ownKeys(t) {
    return te(
      t,
      "iterate",
      R(t) ? "length" : st
    ), Reflect.ownKeys(t);
  }
}
class Ei extends ur {
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
const Ti = /* @__PURE__ */ new fr(), Ri = /* @__PURE__ */ new Ei(), Mi = /* @__PURE__ */ new fr(!0);
const Os = (e) => e, Ut = (e) => Reflect.getPrototypeOf(e);
function Pi(e, t, s) {
  return function(...n) {
    const r = this.__v_raw, i = N(r), o = ft(i), l = e === "entries" || e === Symbol.iterator && o, a = e === "keys" && o, d = r[e](...n), f = s ? Os : t ? Ds : se;
    return !t && te(
      i,
      "iterate",
      a ? $s : st
    ), {
      // iterator protocol
      next() {
        const { value: p, done: m } = d.next();
        return m ? { value: p, done: m } : {
          value: l ? [f(p[0]), f(p[1])] : f(p),
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
function Vt(e) {
  return function(...t) {
    return e === "delete" ? !1 : e === "clear" ? void 0 : this;
  };
}
function $i(e, t) {
  const s = {
    get(r) {
      const i = this.__v_raw, o = N(i), l = N(r);
      e || (Be(r, l) && te(o, "get", r), te(o, "get", l));
      const { has: a } = Ut(o), d = t ? Os : e ? Ds : se;
      if (a.call(o, r))
        return d(i.get(r));
      if (a.call(o, l))
        return d(i.get(l));
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
      const o = this, l = o.__v_raw, a = N(l), d = t ? Os : e ? Ds : se;
      return !e && te(a, "iterate", st), l.forEach((f, p) => r.call(i, d(f), d(p), o));
    }
  };
  return re(
    s,
    e ? {
      add: Vt("add"),
      set: Vt("set"),
      delete: Vt("delete"),
      clear: Vt("clear")
    } : {
      add(r) {
        !t && !me(r) && !rt(r) && (r = N(r));
        const i = N(this);
        return Ut(i).has.call(i, r) || (i.add(r), Oe(i, "add", r, r)), this;
      },
      set(r, i) {
        !t && !me(i) && !rt(i) && (i = N(i));
        const o = N(this), { has: l, get: a } = Ut(o);
        let d = l.call(o, r);
        d || (r = N(r), d = l.call(o, r));
        const f = a.call(o, r);
        return o.set(r, i), d ? Be(i, f) && Oe(o, "set", r, i) : Oe(o, "add", r, i), this;
      },
      delete(r) {
        const i = N(this), { has: o, get: l } = Ut(i);
        let a = o.call(i, r);
        a || (r = N(r), a = o.call(i, r)), l && l.call(i, r);
        const d = i.delete(r);
        return a && Oe(i, "delete", r, void 0), d;
      },
      clear() {
        const r = N(this), i = r.size !== 0, o = r.clear();
        return i && Oe(
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
    s[r] = Pi(r, e, t);
  }), s;
}
function Qs(e, t) {
  const s = $i(e, t);
  return (n, r, i) => r === "__v_isReactive" ? !e : r === "__v_isReadonly" ? e : r === "__v_raw" ? n : Reflect.get(
    L(s, r) && r in n ? s : n,
    r,
    i
  );
}
const Oi = {
  get: /* @__PURE__ */ Qs(!1, !1)
}, Di = {
  get: /* @__PURE__ */ Qs(!1, !0)
}, Fi = {
  get: /* @__PURE__ */ Qs(!0, !1)
};
const dr = /* @__PURE__ */ new WeakMap(), hr = /* @__PURE__ */ new WeakMap(), pr = /* @__PURE__ */ new WeakMap(), ki = /* @__PURE__ */ new WeakMap();
function Ni(e) {
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
function Li(e) {
  return e.__v_skip || !Object.isExtensible(e) ? 0 : Ni(ai(e));
}
function en(e) {
  return rt(e) ? e : tn(
    e,
    !1,
    Ti,
    Oi,
    dr
  );
}
function Hi(e) {
  return tn(
    e,
    !1,
    Mi,
    Di,
    hr
  );
}
function gr(e) {
  return tn(
    e,
    !0,
    Ri,
    Fi,
    pr
  );
}
function tn(e, t, s, n, r) {
  if (!q(e) || e.__v_raw && !(t && e.__v_isReactive))
    return e;
  const i = r.get(e);
  if (i)
    return i;
  const o = Li(e);
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
function ji(e) {
  return !L(e, "__v_skip") && Object.isExtensible(e) && Xn(e, "__v_skip", !0), e;
}
const se = (e) => q(e) ? en(e) : e, Ds = (e) => q(e) ? gr(e) : e;
function ne(e) {
  return e ? e.__v_isRef === !0 : !1;
}
function Fs(e) {
  return mr(e, !1);
}
function Bi(e) {
  return mr(e, !0);
}
function mr(e, t) {
  return ne(e) ? e : new Wi(e, t);
}
class Wi {
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
const Ui = {
  get: (e, t, s) => t === "__v_raw" ? e : He(Reflect.get(e, t, s)),
  set: (e, t, s, n) => {
    const r = e[t];
    return ne(r) && !ne(s) ? (r.value = s, !0) : Reflect.set(e, t, s, n);
  }
};
function _r(e) {
  return dt(e) ? e : new Proxy(e, Ui);
}
class Vi {
  constructor(t, s, n) {
    this.fn = t, this.setter = s, this._value = void 0, this.dep = new Zs(this), this.__v_isRef = !0, this.deps = void 0, this.depsTail = void 0, this.flags = 16, this.globalVersion = Mt - 1, this.next = void 0, this.effect = this, this.__v_isReadonly = !s, this.isSSR = n;
  }
  /**
   * @internal
   */
  notify() {
    if (this.flags |= 16, !(this.flags & 8) && // avoid infinite self recursion
    V !== this)
      return nr(this, !0), !0;
  }
  get value() {
    const t = this.dep.track();
    return or(this), t && (t.version = this.dep.version), this._value;
  }
  set value(t) {
    this.setter && this.setter(t);
  }
}
function Ki(e, t, s = !1) {
  let n, r;
  return M(e) ? n = e : (n = e.get, r = e.set), new Vi(n, r, s);
}
const Kt = {}, Xt = /* @__PURE__ */ new WeakMap();
let Ze;
function Gi(e, t = !1, s = Ze) {
  if (s) {
    let n = Xt.get(s);
    n || Xt.set(s, n = []), n.push(e);
  }
}
function qi(e, t, s = K) {
  const { immediate: n, deep: r, once: i, scheduler: o, augmentJob: l, call: a } = s, d = (E) => r ? E : me(E) || r === !1 || r === 0 ? je(E, 1) : je(E);
  let f, p, m, I, O = !1, $ = !1;
  if (ne(e) ? (p = () => e.value, O = me(e)) : dt(e) ? (p = () => d(e), O = !0) : R(e) ? ($ = !0, O = e.some((E) => dt(E) || me(E)), p = () => e.map((E) => {
    if (ne(E))
      return E.value;
    if (dt(E))
      return d(E);
    if (M(E))
      return a ? a(E, 2) : E();
  })) : M(e) ? t ? p = a ? () => a(e, 2) : e : p = () => {
    if (m) {
      Ve();
      try {
        m();
      } finally {
        Ke();
      }
    }
    const E = Ze;
    Ze = f;
    try {
      return a ? a(e, 3, [I]) : e(I);
    } finally {
      Ze = E;
    }
  } : p = Re, t && r) {
    const E = p, ee = r === !0 ? 1 / 0 : r;
    p = () => je(E(), ee);
  }
  const Y = yi(), k = () => {
    f.stop(), Y && Y.active && qs(Y.effects, f);
  };
  if (i && t) {
    const E = t;
    t = (...ee) => {
      E(...ee), k();
    };
  }
  let J = $ ? new Array(e.length).fill(Kt) : Kt;
  const z = (E) => {
    if (!(!(f.flags & 1) || !f.dirty && !E))
      if (t) {
        const ee = f.run();
        if (r || O || ($ ? ee.some((Fe, we) => Be(Fe, J[we])) : Be(ee, J))) {
          m && m();
          const Fe = Ze;
          Ze = f;
          try {
            const we = [
              ee,
              // pass undefined as the old value when it's changed for the first time
              J === Kt ? void 0 : $ && J[0] === Kt ? [] : J,
              I
            ];
            a ? a(t, 3, we) : (
              // @ts-expect-error
              t(...we)
            ), J = ee;
          } finally {
            Ze = Fe;
          }
        }
      } else
        f.run();
  };
  return l && l(z), f = new tr(p), f.scheduler = o ? () => o(z, !1) : z, I = (E) => Gi(E, !1, f), m = f.onStop = () => {
    const E = Xt.get(f);
    if (E) {
      if (a)
        a(E, 4);
      else
        for (const ee of E) ee();
      Xt.delete(f);
    }
  }, t ? n ? z(!0) : J = f.run() : o ? o(z.bind(null, !0), !0) : f.run(), k.pause = f.pause.bind(f), k.resume = f.resume.bind(f), k.stop = k, k;
}
function je(e, t = 1 / 0, s) {
  if (t <= 0 || !q(e) || e.__v_skip || (s = s || /* @__PURE__ */ new Set(), s.has(e)))
    return e;
  if (s.add(e), t--, ne(e))
    je(e.value, t, s);
  else if (R(e))
    for (let n = 0; n < e.length; n++)
      je(e[n], t, s);
  else if (Gn(e) || ft(e))
    e.forEach((n) => {
      je(n, t, s);
    });
  else if (zn(e)) {
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
    us(r, t, s);
  }
}
function Me(e, t, s, n) {
  if (M(e)) {
    const r = kt(e, t, s, n);
    return r && qn(r) && r.catch((i) => {
      us(i, t, s);
    }), r;
  }
  if (R(e)) {
    const r = [];
    for (let i = 0; i < e.length; i++)
      r.push(Me(e[i], t, s, n));
    return r;
  }
}
function us(e, t, s, n = !0) {
  const r = t ? t.vnode : null, { errorHandler: i, throwUnhandledErrorInProduction: o } = t && t.appContext.config || K;
  if (t) {
    let l = t.parent;
    const a = t.proxy, d = `https://vuejs.org/error-reference/#runtime-${s}`;
    for (; l; ) {
      const f = l.ec;
      if (f) {
        for (let p = 0; p < f.length; p++)
          if (f[p](e, a, d) === !1)
            return;
      }
      l = l.parent;
    }
    if (i) {
      Ve(), kt(i, null, 10, [
        e,
        a,
        d
      ]), Ke();
      return;
    }
  }
  Ji(e, s, r, n, o);
}
function Ji(e, t, s, n = !0, r = !1) {
  if (r)
    throw e;
  console.error(e);
}
const le = [];
let Ae = -1;
const ht = [];
let Ne = null, at = 0;
const br = /* @__PURE__ */ Promise.resolve();
let Zt = null;
function wr(e) {
  const t = Zt || br;
  return e ? t.then(this ? e.bind(this) : e) : t;
}
function zi(e) {
  let t = Ae + 1, s = le.length;
  for (; t < s; ) {
    const n = t + s >>> 1, r = le[n], i = $t(r);
    i < e || i === e && r.flags & 2 ? t = n + 1 : s = n;
  }
  return t;
}
function nn(e) {
  if (!(e.flags & 1)) {
    const t = $t(e), s = le[le.length - 1];
    !s || // fast path when the job id is larger than the tail
    !(e.flags & 2) && t >= $t(s) ? le.push(e) : le.splice(zi(t), 0, e), e.flags |= 1, yr();
  }
}
function yr() {
  Zt || (Zt = br.then(xr));
}
function Yi(e) {
  R(e) ? ht.push(...e) : Ne && e.id === -1 ? Ne.splice(at + 1, 0, e) : e.flags & 1 || (ht.push(e), e.flags |= 1), yr();
}
function bn(e, t, s = Ae + 1) {
  for (; s < le.length; s++) {
    const n = le[s];
    if (n && n.flags & 2) {
      if (e && n.id !== e.uid)
        continue;
      le.splice(s, 1), s--, n.flags & 4 && (n.flags &= -2), n(), n.flags & 4 || (n.flags &= -2);
    }
  }
}
function vr(e) {
  if (ht.length) {
    const t = [...new Set(ht)].sort(
      (s, n) => $t(s) - $t(n)
    );
    if (ht.length = 0, Ne) {
      Ne.push(...t);
      return;
    }
    for (Ne = t, at = 0; at < Ne.length; at++) {
      const s = Ne[at];
      s.flags & 4 && (s.flags &= -2), s.flags & 8 || s(), s.flags &= -2;
    }
    Ne = null, at = 0;
  }
}
const $t = (e) => e.id == null ? e.flags & 2 ? -1 : 1 / 0 : e.id;
function xr(e) {
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
    Ae = -1, le.length = 0, vr(), Zt = null, (le.length || ht.length) && xr();
  }
}
let Te = null, Sr = null;
function Qt(e) {
  const t = Te;
  return Te = e, Sr = e && e.type.__scopeId || null, t;
}
function Xi(e, t = Te, s) {
  if (!t || e._n)
    return e;
  const n = (...r) => {
    n._d && En(-1);
    const i = Qt(t);
    let o;
    try {
      o = e(...r);
    } finally {
      Qt(i), n._d && En(1);
    }
    return o;
  };
  return n._n = !0, n._c = !0, n._d = !0, n;
}
function Ye(e, t, s, n) {
  const r = e.dirs, i = t && t.dirs;
  for (let o = 0; o < r.length; o++) {
    const l = r[o];
    i && (l.oldValue = i[o].value);
    let a = l.dir[n];
    a && (Ve(), Me(a, s, 8, [
      e.el,
      l,
      e,
      t
    ]), Ke());
  }
}
const Zi = Symbol("_vte"), Qi = (e) => e.__isTeleport;
function rn(e, t) {
  e.shapeFlag & 6 && e.component ? (e.transition = t, rn(e.component.subTree, t)) : e.shapeFlag & 128 ? (e.ssContent.transition = t.clone(e.ssContent), e.ssFallback.transition = t.clone(e.ssFallback)) : e.transition = t;
}
/*! #__NO_SIDE_EFFECTS__ */
// @__NO_SIDE_EFFECTS__
function Ge(e, t) {
  return M(e) ? (
    // #8236: extend call and options.name access are considered side-effects
    // by Rollup, so we have to wrap it in a pure-annotated IIFE.
    re({ name: e.name }, t, { setup: e })
  ) : e;
}
function Ir(e) {
  e.ids = [e.ids[0] + e.ids[2]++ + "-", 0, 0];
}
function es(e, t, s, n, r = !1) {
  if (R(e)) {
    e.forEach(
      (O, $) => es(
        O,
        t && (R(t) ? t[$] : t),
        s,
        n,
        r
      )
    );
    return;
  }
  if (Et(n) && !r) {
    n.shapeFlag & 512 && n.type.__asyncResolved && n.component.subTree.component && es(e, t, s, n.component.subTree);
    return;
  }
  const i = n.shapeFlag & 4 ? cn(n.component) : n.el, o = r ? null : i, { i: l, r: a } = e, d = t && t.r, f = l.refs === K ? l.refs = {} : l.refs, p = l.setupState, m = N(p), I = p === K ? () => !1 : (O) => L(m, O);
  if (d != null && d !== a && (Q(d) ? (f[d] = null, I(d) && (p[d] = null)) : ne(d) && (d.value = null)), M(a))
    kt(a, l, 12, [o, f]);
  else {
    const O = Q(a), $ = ne(a);
    if (O || $) {
      const Y = () => {
        if (e.f) {
          const k = O ? I(a) ? p[a] : f[a] : a.value;
          r ? R(k) && qs(k, i) : R(k) ? k.includes(i) || k.push(i) : O ? (f[a] = [i], I(a) && (p[a] = f[a])) : (a.value = [i], e.k && (f[e.k] = a.value));
        } else O ? (f[a] = o, I(a) && (p[a] = o)) : $ && (a.value = o, e.k && (f[e.k] = o));
      };
      o ? (Y.id = -1, de(Y, s)) : Y();
    }
  }
}
cs().requestIdleCallback;
cs().cancelIdleCallback;
const Et = (e) => !!e.type.__asyncLoader, Ar = (e) => e.type.__isKeepAlive;
function eo(e, t) {
  Cr(e, "a", t);
}
function to(e, t) {
  Cr(e, "da", t);
}
function Cr(e, t, s = ce) {
  const n = e.__wdc || (e.__wdc = () => {
    let r = s;
    for (; r; ) {
      if (r.isDeactivated)
        return;
      r = r.parent;
    }
    return e();
  });
  if (fs(t, n, s), s) {
    let r = s.parent;
    for (; r && r.parent; )
      Ar(r.parent.vnode) && so(n, t, s, r), r = r.parent;
  }
}
function so(e, t, s, n) {
  const r = fs(
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
function fs(e, t, s = ce, n = !1) {
  if (s) {
    const r = s[e] || (s[e] = []), i = t.__weh || (t.__weh = (...o) => {
      Ve();
      const l = Nt(s), a = Me(t, s, e, o);
      return l(), Ke(), a;
    });
    return n ? r.unshift(i) : r.push(i), i;
  }
}
const De = (e) => (t, s = ce) => {
  (!Dt || e === "sp") && fs(e, (...n) => t(...n), s);
}, no = De("bm"), ro = De("m"), io = De(
  "bu"
), oo = De("u"), Er = De(
  "bum"
), Tr = De("um"), lo = De(
  "sp"
), co = De("rtg"), ao = De("rtc");
function Rr(e, t = ce) {
  fs("ec", e, t);
}
const uo = Symbol.for("v-ndc");
function Qe(e, t, s, n) {
  let r;
  const i = s, o = R(e);
  if (o || Q(e)) {
    const l = o && dt(e);
    let a = !1;
    l && (a = !me(e), e = as(e)), r = new Array(e.length);
    for (let d = 0, f = e.length; d < f; d++)
      r[d] = t(
        a ? se(e[d]) : e[d],
        d,
        void 0,
        i
      );
  } else if (typeof e == "number") {
    r = new Array(e);
    for (let l = 0; l < e; l++)
      r[l] = t(l + 1, l, void 0, i);
  } else if (q(e))
    if (e[Symbol.iterator])
      r = Array.from(
        e,
        (l, a) => t(l, a, void 0, i)
      );
    else {
      const l = Object.keys(e);
      r = new Array(l.length);
      for (let a = 0, d = l.length; a < d; a++) {
        const f = l[a];
        r[a] = t(e[f], f, a, i);
      }
    }
  else
    r = [];
  return r;
}
const ks = (e) => e ? Xr(e) ? cn(e) : ks(e.parent) : null, Tt = (
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
    $parent: (e) => ks(e.parent),
    $root: (e) => ks(e.root),
    $host: (e) => e.ce,
    $emit: (e) => e.emit,
    $options: (e) => Pr(e),
    $forceUpdate: (e) => e.f || (e.f = () => {
      nn(e.update);
    }),
    $nextTick: (e) => e.n || (e.n = wr.bind(e.proxy)),
    $watch: (e) => Oo.bind(e)
  })
), xs = (e, t) => e !== K && !e.__isScriptSetup && L(e, t), fo = {
  get({ _: e }, t) {
    if (t === "__v_skip")
      return !0;
    const { ctx: s, setupState: n, data: r, props: i, accessCache: o, type: l, appContext: a } = e;
    let d;
    if (t[0] !== "$") {
      const I = o[t];
      if (I !== void 0)
        switch (I) {
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
        if (xs(n, t))
          return o[t] = 1, n[t];
        if (r !== K && L(r, t))
          return o[t] = 2, r[t];
        if (
          // only cache other properties when instance has declared (thus stable)
          // props
          (d = e.propsOptions[0]) && L(d, t)
        )
          return o[t] = 3, i[t];
        if (s !== K && L(s, t))
          return o[t] = 4, s[t];
        Ns && (o[t] = 0);
      }
    }
    const f = Tt[t];
    let p, m;
    if (f)
      return t === "$attrs" && te(e.attrs, "get", ""), f(e);
    if (
      // css module (injected by vue-loader)
      (p = l.__cssModules) && (p = p[t])
    )
      return p;
    if (s !== K && L(s, t))
      return o[t] = 4, s[t];
    if (
      // global properties
      m = a.config.globalProperties, L(m, t)
    )
      return m[t];
  },
  set({ _: e }, t, s) {
    const { data: n, setupState: r, ctx: i } = e;
    return xs(r, t) ? (r[t] = s, !0) : n !== K && L(n, t) ? (n[t] = s, !0) : L(e.props, t) || t[0] === "$" && t.slice(1) in e ? !1 : (i[t] = s, !0);
  },
  has({
    _: { data: e, setupState: t, accessCache: s, ctx: n, appContext: r, propsOptions: i }
  }, o) {
    let l;
    return !!s[o] || e !== K && L(e, o) || xs(t, o) || (l = i[0]) && L(l, o) || L(n, o) || L(Tt, o) || L(r.config.globalProperties, o);
  },
  defineProperty(e, t, s) {
    return s.get != null ? e._.accessCache[t] = 0 : L(s, "value") && this.set(e, t, s.value, null), Reflect.defineProperty(e, t, s);
  }
};
function wn(e) {
  return R(e) ? e.reduce(
    (t, s) => (t[s] = null, t),
    {}
  ) : e;
}
let Ns = !0;
function ho(e) {
  const t = Pr(e), s = e.proxy, n = e.ctx;
  Ns = !1, t.beforeCreate && yn(t.beforeCreate, e, "bc");
  const {
    // state
    data: r,
    computed: i,
    methods: o,
    watch: l,
    provide: a,
    inject: d,
    // lifecycle
    created: f,
    beforeMount: p,
    mounted: m,
    beforeUpdate: I,
    updated: O,
    activated: $,
    deactivated: Y,
    beforeDestroy: k,
    beforeUnmount: J,
    destroyed: z,
    unmounted: E,
    render: ee,
    renderTracked: Fe,
    renderTriggered: we,
    errorCaptured: ke,
    serverPrefetch: Lt,
    // public API
    expose: qe,
    inheritAttrs: mt,
    // assets
    components: Ht,
    directives: jt,
    filters: ps
  } = t;
  if (d && po(d, n, null), o)
    for (const G in o) {
      const W = o[G];
      M(W) && (n[G] = W.bind(s));
    }
  if (r) {
    const G = r.call(s, s);
    q(G) && (e.data = en(G));
  }
  if (Ns = !0, i)
    for (const G in i) {
      const W = i[G], Je = M(W) ? W.bind(s, s) : M(W.get) ? W.get.bind(s, s) : Re, Bt = !M(W) && M(W.set) ? W.set.bind(s) : Re, ze = nt({
        get: Je,
        set: Bt
      });
      Object.defineProperty(n, G, {
        enumerable: !0,
        configurable: !0,
        get: () => ze.value,
        set: (ye) => ze.value = ye
      });
    }
  if (l)
    for (const G in l)
      Mr(l[G], n, s, G);
  if (a) {
    const G = M(a) ? a.call(s) : a;
    Reflect.ownKeys(G).forEach((W) => {
      yo(W, G[W]);
    });
  }
  f && yn(f, e, "c");
  function ie(G, W) {
    R(W) ? W.forEach((Je) => G(Je.bind(s))) : W && G(W.bind(s));
  }
  if (ie(no, p), ie(ro, m), ie(io, I), ie(oo, O), ie(eo, $), ie(to, Y), ie(Rr, ke), ie(ao, Fe), ie(co, we), ie(Er, J), ie(Tr, E), ie(lo, Lt), R(qe))
    if (qe.length) {
      const G = e.exposed || (e.exposed = {});
      qe.forEach((W) => {
        Object.defineProperty(G, W, {
          get: () => s[W],
          set: (Je) => s[W] = Je
        });
      });
    } else e.exposed || (e.exposed = {});
  ee && e.render === Re && (e.render = ee), mt != null && (e.inheritAttrs = mt), Ht && (e.components = Ht), jt && (e.directives = jt), Lt && Ir(e);
}
function po(e, t, s = Re) {
  R(e) && (e = Ls(e));
  for (const n in e) {
    const r = e[n];
    let i;
    q(r) ? "default" in r ? i = qt(
      r.from || n,
      r.default,
      !0
    ) : i = qt(r.from || n) : i = qt(r), ne(i) ? Object.defineProperty(t, n, {
      enumerable: !0,
      configurable: !0,
      get: () => i.value,
      set: (o) => i.value = o
    }) : t[n] = i;
  }
}
function yn(e, t, s) {
  Me(
    R(e) ? e.map((n) => n.bind(t.proxy)) : e.bind(t.proxy),
    t,
    s
  );
}
function Mr(e, t, s, n) {
  let r = n.includes(".") ? Kr(s, n) : () => s[n];
  if (Q(e)) {
    const i = t[e];
    M(i) && Jt(r, i);
  } else if (M(e))
    Jt(r, e.bind(s));
  else if (q(e))
    if (R(e))
      e.forEach((i) => Mr(i, t, s, n));
    else {
      const i = M(e.handler) ? e.handler.bind(s) : t[e.handler];
      M(i) && Jt(r, i, e);
    }
}
function Pr(e) {
  const t = e.type, { mixins: s, extends: n } = t, {
    mixins: r,
    optionsCache: i,
    config: { optionMergeStrategies: o }
  } = e.appContext, l = i.get(t);
  let a;
  return l ? a = l : !r.length && !s && !n ? a = t : (a = {}, r.length && r.forEach(
    (d) => ts(a, d, o, !0)
  ), ts(a, t, o)), q(t) && i.set(t, a), a;
}
function ts(e, t, s, n = !1) {
  const { mixins: r, extends: i } = t;
  i && ts(e, i, s, !0), r && r.forEach(
    (o) => ts(e, o, s, !0)
  );
  for (const o in t)
    if (!(n && o === "expose")) {
      const l = go[o] || s && s[o];
      e[o] = l ? l(e[o], t[o]) : t[o];
    }
  return e;
}
const go = {
  data: vn,
  props: xn,
  emits: xn,
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
  watch: _o,
  // provide / inject
  provide: vn,
  inject: mo
};
function vn(e, t) {
  return t ? e ? function() {
    return re(
      M(e) ? e.call(this, this) : e,
      M(t) ? t.call(this, this) : t
    );
  } : t : e;
}
function mo(e, t) {
  return xt(Ls(e), Ls(t));
}
function Ls(e) {
  if (R(e)) {
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
function xn(e, t) {
  return e ? R(e) && R(t) ? [.../* @__PURE__ */ new Set([...e, ...t])] : re(
    /* @__PURE__ */ Object.create(null),
    wn(e),
    wn(t ?? {})
  ) : t;
}
function _o(e, t) {
  if (!e) return t;
  if (!t) return e;
  const s = re(/* @__PURE__ */ Object.create(null), e);
  for (const n in t)
    s[n] = oe(e[n], t[n]);
  return s;
}
function $r() {
  return {
    app: null,
    config: {
      isNativeTag: li,
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
let bo = 0;
function wo(e, t) {
  return function(n, r = null) {
    M(n) || (n = re({}, n)), r != null && !q(r) && (r = null);
    const i = $r(), o = /* @__PURE__ */ new WeakSet(), l = [];
    let a = !1;
    const d = i.app = {
      _uid: bo++,
      _component: n,
      _props: r,
      _container: null,
      _context: i,
      _instance: null,
      version: Qo,
      get config() {
        return i.config;
      },
      set config(f) {
      },
      use(f, ...p) {
        return o.has(f) || (f && M(f.install) ? (o.add(f), f.install(d, ...p)) : M(f) && (o.add(f), f(d, ...p))), d;
      },
      mixin(f) {
        return i.mixins.includes(f) || i.mixins.push(f), d;
      },
      component(f, p) {
        return p ? (i.components[f] = p, d) : i.components[f];
      },
      directive(f, p) {
        return p ? (i.directives[f] = p, d) : i.directives[f];
      },
      mount(f, p, m) {
        if (!a) {
          const I = d._ceVNode || be(n, r);
          return I.appContext = i, m === !0 ? m = "svg" : m === !1 && (m = void 0), e(I, f, m), a = !0, d._container = f, f.__vue_app__ = d, cn(I.component);
        }
      },
      onUnmount(f) {
        l.push(f);
      },
      unmount() {
        a && (Me(
          l,
          d._instance,
          16
        ), e(null, d._container), delete d._container.__vue_app__);
      },
      provide(f, p) {
        return i.provides[f] = p, d;
      },
      runWithContext(f) {
        const p = pt;
        pt = d;
        try {
          return f();
        } finally {
          pt = p;
        }
      }
    };
    return d;
  };
}
let pt = null;
function yo(e, t) {
  if (ce) {
    let s = ce.provides;
    const n = ce.parent && ce.parent.provides;
    n === s && (s = ce.provides = Object.create(n)), s[e] = t;
  }
}
function qt(e, t, s = !1) {
  const n = ce || Te;
  if (n || pt) {
    const r = pt ? pt._context.provides : n ? n.parent == null ? n.vnode.appContext && n.vnode.appContext.provides : n.parent.provides : void 0;
    if (r && e in r)
      return r[e];
    if (arguments.length > 1)
      return s && M(t) ? t.call(n && n.proxy) : t;
  }
}
const Or = {}, Dr = () => Object.create(Or), Fr = (e) => Object.getPrototypeOf(e) === Or;
function vo(e, t, s, n = !1) {
  const r = {}, i = Dr();
  e.propsDefaults = /* @__PURE__ */ Object.create(null), kr(e, t, r, i);
  for (const o in e.propsOptions[0])
    o in r || (r[o] = void 0);
  s ? e.props = n ? r : Hi(r) : e.type.props ? e.props = r : e.props = i, e.attrs = i;
}
function xo(e, t, s, n) {
  const {
    props: r,
    attrs: i,
    vnode: { patchFlag: o }
  } = e, l = N(r), [a] = e.propsOptions;
  let d = !1;
  if (
    // always force full diff in dev
    // - #1942 if hmr is enabled with sfc component
    // - vite#872 non-sfc component used by sfc component
    (n || o > 0) && !(o & 16)
  ) {
    if (o & 8) {
      const f = e.vnode.dynamicProps;
      for (let p = 0; p < f.length; p++) {
        let m = f[p];
        if (ds(e.emitsOptions, m))
          continue;
        const I = t[m];
        if (a)
          if (L(i, m))
            I !== i[m] && (i[m] = I, d = !0);
          else {
            const O = We(m);
            r[O] = Hs(
              a,
              l,
              O,
              I,
              e,
              !1
            );
          }
        else
          I !== i[m] && (i[m] = I, d = !0);
      }
    }
  } else {
    kr(e, t, r, i) && (d = !0);
    let f;
    for (const p in l)
      (!t || // for camelCase
      !L(t, p) && // it's possible the original props was passed in as kebab-case
      // and converted to camelCase (#955)
      ((f = ot(p)) === p || !L(t, f))) && (a ? s && // for camelCase
      (s[p] !== void 0 || // for kebab-case
      s[f] !== void 0) && (r[p] = Hs(
        a,
        l,
        p,
        void 0,
        e,
        !0
      )) : delete r[p]);
    if (i !== l)
      for (const p in i)
        (!t || !L(t, p)) && (delete i[p], d = !0);
  }
  d && Oe(e.attrs, "set", "");
}
function kr(e, t, s, n) {
  const [r, i] = e.propsOptions;
  let o = !1, l;
  if (t)
    for (let a in t) {
      if (It(a))
        continue;
      const d = t[a];
      let f;
      r && L(r, f = We(a)) ? !i || !i.includes(f) ? s[f] = d : (l || (l = {}))[f] = d : ds(e.emitsOptions, a) || (!(a in n) || d !== n[a]) && (n[a] = d, o = !0);
    }
  if (i) {
    const a = N(s), d = l || K;
    for (let f = 0; f < i.length; f++) {
      const p = i[f];
      s[p] = Hs(
        r,
        a,
        p,
        d[p],
        e,
        !L(d, p)
      );
    }
  }
  return o;
}
function Hs(e, t, s, n, r, i) {
  const o = e[s];
  if (o != null) {
    const l = L(o, "default");
    if (l && n === void 0) {
      const a = o.default;
      if (o.type !== Function && !o.skipFactory && M(a)) {
        const { propsDefaults: d } = r;
        if (s in d)
          n = d[s];
        else {
          const f = Nt(r);
          n = d[s] = a.call(
            null,
            t
          ), f();
        }
      } else
        n = a;
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
const So = /* @__PURE__ */ new WeakMap();
function Nr(e, t, s = !1) {
  const n = s ? So : t.propsCache, r = n.get(e);
  if (r)
    return r;
  const i = e.props, o = {}, l = [];
  let a = !1;
  if (!M(e)) {
    const f = (p) => {
      a = !0;
      const [m, I] = Nr(p, t, !0);
      re(o, m), I && l.push(...I);
    };
    !s && t.mixins.length && t.mixins.forEach(f), e.extends && f(e.extends), e.mixins && e.mixins.forEach(f);
  }
  if (!i && !a)
    return q(e) && n.set(e, ut), ut;
  if (R(i))
    for (let f = 0; f < i.length; f++) {
      const p = We(i[f]);
      Sn(p) && (o[p] = K);
    }
  else if (i)
    for (const f in i) {
      const p = We(f);
      if (Sn(p)) {
        const m = i[f], I = o[p] = R(m) || M(m) ? { type: m } : re({}, m), O = I.type;
        let $ = !1, Y = !0;
        if (R(O))
          for (let k = 0; k < O.length; ++k) {
            const J = O[k], z = M(J) && J.name;
            if (z === "Boolean") {
              $ = !0;
              break;
            } else z === "String" && (Y = !1);
          }
        else
          $ = M(O) && O.name === "Boolean";
        I[
          0
          /* shouldCast */
        ] = $, I[
          1
          /* shouldCastTrue */
        ] = Y, ($ || L(I, "default")) && l.push(p);
      }
    }
  const d = [o, l];
  return q(e) && n.set(e, d), d;
}
function Sn(e) {
  return e[0] !== "$" && !It(e);
}
const Lr = (e) => e[0] === "_" || e === "$stable", on = (e) => R(e) ? e.map(Ee) : [Ee(e)], Io = (e, t, s) => {
  if (t._n)
    return t;
  const n = Xi((...r) => on(t(...r)), s);
  return n._c = !1, n;
}, Hr = (e, t, s) => {
  const n = e._ctx;
  for (const r in e) {
    if (Lr(r)) continue;
    const i = e[r];
    if (M(i))
      t[r] = Io(r, i, n);
    else if (i != null) {
      const o = on(i);
      t[r] = () => o;
    }
  }
}, jr = (e, t) => {
  const s = on(t);
  e.slots.default = () => s;
}, Br = (e, t, s) => {
  for (const n in t)
    (s || n !== "_") && (e[n] = t[n]);
}, Ao = (e, t, s) => {
  const n = e.slots = Dr();
  if (e.vnode.shapeFlag & 32) {
    const r = t._;
    r ? (Br(n, t, s), s && Xn(n, "_", r, !0)) : Hr(t, n);
  } else t && jr(e, t);
}, Co = (e, t, s) => {
  const { vnode: n, slots: r } = e;
  let i = !0, o = K;
  if (n.shapeFlag & 32) {
    const l = t._;
    l ? s && l === 1 ? i = !1 : Br(r, t, s) : (i = !t.$stable, Hr(t, r)), o = t;
  } else t && (jr(e, t), o = { default: 1 });
  if (i)
    for (const l in r)
      !Lr(l) && o[l] == null && delete r[l];
}, de = jo;
function Eo(e) {
  return To(e);
}
function To(e, t) {
  const s = cs();
  s.__VUE__ = !0;
  const {
    insert: n,
    remove: r,
    patchProp: i,
    createElement: o,
    createText: l,
    createComment: a,
    setText: d,
    setElementText: f,
    parentNode: p,
    nextSibling: m,
    setScopeId: I = Re,
    insertStaticContent: O
  } = e, $ = (c, u, h, b = null, g = null, _ = null, x = void 0, v = null, y = !!u.dynamicChildren) => {
    if (c === u)
      return;
    c && !vt(c, u) && (b = Wt(c), ye(c, g, _, !0), c = null), u.patchFlag === -2 && (y = !1, u.dynamicChildren = null);
    const { type: w, ref: C, shapeFlag: S } = u;
    switch (w) {
      case hs:
        Y(c, u, h, b);
        break;
      case it:
        k(c, u, h, b);
        break;
      case Is:
        c == null && J(u, h, b, x);
        break;
      case Z:
        Ht(
          c,
          u,
          h,
          b,
          g,
          _,
          x,
          v,
          y
        );
        break;
      default:
        S & 1 ? ee(
          c,
          u,
          h,
          b,
          g,
          _,
          x,
          v,
          y
        ) : S & 6 ? jt(
          c,
          u,
          h,
          b,
          g,
          _,
          x,
          v,
          y
        ) : (S & 64 || S & 128) && w.process(
          c,
          u,
          h,
          b,
          g,
          _,
          x,
          v,
          y,
          bt
        );
    }
    C != null && g && es(C, c && c.ref, _, u || c, !u);
  }, Y = (c, u, h, b) => {
    if (c == null)
      n(
        u.el = l(u.children),
        h,
        b
      );
    else {
      const g = u.el = c.el;
      u.children !== c.children && d(g, u.children);
    }
  }, k = (c, u, h, b) => {
    c == null ? n(
      u.el = a(u.children || ""),
      h,
      b
    ) : u.el = c.el;
  }, J = (c, u, h, b) => {
    [c.el, c.anchor] = O(
      c.children,
      u,
      h,
      b,
      c.el,
      c.anchor
    );
  }, z = ({ el: c, anchor: u }, h, b) => {
    let g;
    for (; c && c !== u; )
      g = m(c), n(c, h, b), c = g;
    n(u, h, b);
  }, E = ({ el: c, anchor: u }) => {
    let h;
    for (; c && c !== u; )
      h = m(c), r(c), c = h;
    r(u);
  }, ee = (c, u, h, b, g, _, x, v, y) => {
    u.type === "svg" ? x = "svg" : u.type === "math" && (x = "mathml"), c == null ? Fe(
      u,
      h,
      b,
      g,
      _,
      x,
      v,
      y
    ) : Lt(
      c,
      u,
      g,
      _,
      x,
      v,
      y
    );
  }, Fe = (c, u, h, b, g, _, x, v) => {
    let y, w;
    const { props: C, shapeFlag: S, transition: A, dirs: T } = c;
    if (y = c.el = o(
      c.type,
      _,
      C && C.is,
      C
    ), S & 8 ? f(y, c.children) : S & 16 && ke(
      c.children,
      y,
      null,
      b,
      g,
      Ss(c, _),
      x,
      v
    ), T && Ye(c, null, b, "created"), we(y, c, c.scopeId, x, b), C) {
      for (const U in C)
        U !== "value" && !It(U) && i(y, U, null, C[U], _, b);
      "value" in C && i(y, "value", null, C.value, _), (w = C.onVnodeBeforeMount) && Ie(w, b, c);
    }
    T && Ye(c, null, b, "beforeMount");
    const D = Ro(g, A);
    D && A.beforeEnter(y), n(y, u, h), ((w = C && C.onVnodeMounted) || D || T) && de(() => {
      w && Ie(w, b, c), D && A.enter(y), T && Ye(c, null, b, "mounted");
    }, g);
  }, we = (c, u, h, b, g) => {
    if (h && I(c, h), b)
      for (let _ = 0; _ < b.length; _++)
        I(c, b[_]);
    if (g) {
      let _ = g.subTree;
      if (u === _ || qr(_.type) && (_.ssContent === u || _.ssFallback === u)) {
        const x = g.vnode;
        we(
          c,
          x,
          x.scopeId,
          x.slotScopeIds,
          g.parent
        );
      }
    }
  }, ke = (c, u, h, b, g, _, x, v, y = 0) => {
    for (let w = y; w < c.length; w++) {
      const C = c[w] = v ? Le(c[w]) : Ee(c[w]);
      $(
        null,
        C,
        u,
        h,
        b,
        g,
        _,
        x,
        v
      );
    }
  }, Lt = (c, u, h, b, g, _, x) => {
    const v = u.el = c.el;
    let { patchFlag: y, dynamicChildren: w, dirs: C } = u;
    y |= c.patchFlag & 16;
    const S = c.props || K, A = u.props || K;
    let T;
    if (h && Xe(h, !1), (T = A.onVnodeBeforeUpdate) && Ie(T, h, u, c), C && Ye(u, c, h, "beforeUpdate"), h && Xe(h, !0), (S.innerHTML && A.innerHTML == null || S.textContent && A.textContent == null) && f(v, ""), w ? qe(
      c.dynamicChildren,
      w,
      v,
      h,
      b,
      Ss(u, g),
      _
    ) : x || W(
      c,
      u,
      v,
      null,
      h,
      b,
      Ss(u, g),
      _,
      !1
    ), y > 0) {
      if (y & 16)
        mt(v, S, A, h, g);
      else if (y & 2 && S.class !== A.class && i(v, "class", null, A.class, g), y & 4 && i(v, "style", S.style, A.style, g), y & 8) {
        const D = u.dynamicProps;
        for (let U = 0; U < D.length; U++) {
          const H = D[U], ue = S[H], ae = A[H];
          (ae !== ue || H === "value") && i(v, H, ue, ae, g, h);
        }
      }
      y & 1 && c.children !== u.children && f(v, u.children);
    } else !x && w == null && mt(v, S, A, h, g);
    ((T = A.onVnodeUpdated) || C) && de(() => {
      T && Ie(T, h, u, c), C && Ye(u, c, h, "updated");
    }, b);
  }, qe = (c, u, h, b, g, _, x) => {
    for (let v = 0; v < u.length; v++) {
      const y = c[v], w = u[v], C = (
        // oldVNode may be an errored async setup() component inside Suspense
        // which will not have a mounted element
        y.el && // - In the case of a Fragment, we need to provide the actual parent
        // of the Fragment itself so it can move its children.
        (y.type === Z || // - In the case of different nodes, there is going to be a replacement
        // which also requires the correct parent container
        !vt(y, w) || // - In the case of a component, it could contain anything.
        y.shapeFlag & 70) ? p(y.el) : (
          // In other cases, the parent container is not actually used so we
          // just pass the block element here to avoid a DOM parentNode call.
          h
        )
      );
      $(
        y,
        w,
        C,
        null,
        b,
        g,
        _,
        x,
        !0
      );
    }
  }, mt = (c, u, h, b, g) => {
    if (u !== h) {
      if (u !== K)
        for (const _ in u)
          !It(_) && !(_ in h) && i(
            c,
            _,
            u[_],
            null,
            g,
            b
          );
      for (const _ in h) {
        if (It(_)) continue;
        const x = h[_], v = u[_];
        x !== v && _ !== "value" && i(c, _, v, x, g, b);
      }
      "value" in h && i(c, "value", u.value, h.value, g);
    }
  }, Ht = (c, u, h, b, g, _, x, v, y) => {
    const w = u.el = c ? c.el : l(""), C = u.anchor = c ? c.anchor : l("");
    let { patchFlag: S, dynamicChildren: A, slotScopeIds: T } = u;
    T && (v = v ? v.concat(T) : T), c == null ? (n(w, h, b), n(C, h, b), ke(
      // #10007
      // such fragment like `<></>` will be compiled into
      // a fragment which doesn't have a children.
      // In this case fallback to an empty array
      u.children || [],
      h,
      C,
      g,
      _,
      x,
      v,
      y
    )) : S > 0 && S & 64 && A && // #2715 the previous fragment could've been a BAILed one as a result
    // of renderSlot() with no valid children
    c.dynamicChildren ? (qe(
      c.dynamicChildren,
      A,
      h,
      g,
      _,
      x,
      v
    ), // #2080 if the stable fragment has a key, it's a <template v-for> that may
    //  get moved around. Make sure all root level vnodes inherit el.
    // #2134 or if it's a component root, it may also get moved around
    // as the component is being moved.
    (u.key != null || g && u === g.subTree) && Wr(
      c,
      u,
      !0
      /* shallow */
    )) : W(
      c,
      u,
      h,
      C,
      g,
      _,
      x,
      v,
      y
    );
  }, jt = (c, u, h, b, g, _, x, v, y) => {
    u.slotScopeIds = v, c == null ? u.shapeFlag & 512 ? g.ctx.activate(
      u,
      h,
      b,
      x,
      y
    ) : ps(
      u,
      h,
      b,
      g,
      _,
      x,
      y
    ) : un(c, u, y);
  }, ps = (c, u, h, b, g, _, x) => {
    const v = c.component = qo(
      c,
      b,
      g
    );
    if (Ar(c) && (v.ctx.renderer = bt), Jo(v, !1, x), v.asyncDep) {
      if (g && g.registerDep(v, ie, x), !c.el) {
        const y = v.subTree = be(it);
        k(null, y, u, h);
      }
    } else
      ie(
        v,
        c,
        u,
        h,
        g,
        _,
        x
      );
  }, un = (c, u, h) => {
    const b = u.component = c.component;
    if (Lo(c, u, h))
      if (b.asyncDep && !b.asyncResolved) {
        G(b, u, h);
        return;
      } else
        b.next = u, b.update();
    else
      u.el = c.el, b.vnode = u;
  }, ie = (c, u, h, b, g, _, x) => {
    const v = () => {
      if (c.isMounted) {
        let { next: S, bu: A, u: T, parent: D, vnode: U } = c;
        {
          const xe = Ur(c);
          if (xe) {
            S && (S.el = U.el, G(c, S, x)), xe.asyncDep.then(() => {
              c.isUnmounted || v();
            });
            return;
          }
        }
        let H = S, ue;
        Xe(c, !1), S ? (S.el = U.el, G(c, S, x)) : S = U, A && _s(A), (ue = S.props && S.props.onVnodeBeforeUpdate) && Ie(ue, D, S, U), Xe(c, !0);
        const ae = An(c), ve = c.subTree;
        c.subTree = ae, $(
          ve,
          ae,
          // parent may have changed if it's in a teleport
          p(ve.el),
          // anchor may have changed if it's in a fragment
          Wt(ve),
          c,
          g,
          _
        ), S.el = ae.el, H === null && Ho(c, ae.el), T && de(T, g), (ue = S.props && S.props.onVnodeUpdated) && de(
          () => Ie(ue, D, S, U),
          g
        );
      } else {
        let S;
        const { el: A, props: T } = u, { bm: D, m: U, parent: H, root: ue, type: ae } = c, ve = Et(u);
        Xe(c, !1), D && _s(D), !ve && (S = T && T.onVnodeBeforeMount) && Ie(S, H, u), Xe(c, !0);
        {
          ue.ce && ue.ce._injectChildStyle(ae);
          const xe = c.subTree = An(c);
          $(
            null,
            xe,
            h,
            b,
            c,
            g,
            _
          ), u.el = xe.el;
        }
        if (U && de(U, g), !ve && (S = T && T.onVnodeMounted)) {
          const xe = u;
          de(
            () => Ie(S, H, xe),
            g
          );
        }
        (u.shapeFlag & 256 || H && Et(H.vnode) && H.vnode.shapeFlag & 256) && c.a && de(c.a, g), c.isMounted = !0, u = h = b = null;
      }
    };
    c.scope.on();
    const y = c.effect = new tr(v);
    c.scope.off();
    const w = c.update = y.run.bind(y), C = c.job = y.runIfDirty.bind(y);
    C.i = c, C.id = c.uid, y.scheduler = () => nn(C), Xe(c, !0), w();
  }, G = (c, u, h) => {
    u.component = c;
    const b = c.vnode.props;
    c.vnode = u, c.next = null, xo(c, u.props, b, h), Co(c, u.children, h), Ve(), bn(c), Ke();
  }, W = (c, u, h, b, g, _, x, v, y = !1) => {
    const w = c && c.children, C = c ? c.shapeFlag : 0, S = u.children, { patchFlag: A, shapeFlag: T } = u;
    if (A > 0) {
      if (A & 128) {
        Bt(
          w,
          S,
          h,
          b,
          g,
          _,
          x,
          v,
          y
        );
        return;
      } else if (A & 256) {
        Je(
          w,
          S,
          h,
          b,
          g,
          _,
          x,
          v,
          y
        );
        return;
      }
    }
    T & 8 ? (C & 16 && _t(w, g, _), S !== w && f(h, S)) : C & 16 ? T & 16 ? Bt(
      w,
      S,
      h,
      b,
      g,
      _,
      x,
      v,
      y
    ) : _t(w, g, _, !0) : (C & 8 && f(h, ""), T & 16 && ke(
      S,
      h,
      b,
      g,
      _,
      x,
      v,
      y
    ));
  }, Je = (c, u, h, b, g, _, x, v, y) => {
    c = c || ut, u = u || ut;
    const w = c.length, C = u.length, S = Math.min(w, C);
    let A;
    for (A = 0; A < S; A++) {
      const T = u[A] = y ? Le(u[A]) : Ee(u[A]);
      $(
        c[A],
        T,
        h,
        null,
        g,
        _,
        x,
        v,
        y
      );
    }
    w > C ? _t(
      c,
      g,
      _,
      !0,
      !1,
      S
    ) : ke(
      u,
      h,
      b,
      g,
      _,
      x,
      v,
      y,
      S
    );
  }, Bt = (c, u, h, b, g, _, x, v, y) => {
    let w = 0;
    const C = u.length;
    let S = c.length - 1, A = C - 1;
    for (; w <= S && w <= A; ) {
      const T = c[w], D = u[w] = y ? Le(u[w]) : Ee(u[w]);
      if (vt(T, D))
        $(
          T,
          D,
          h,
          null,
          g,
          _,
          x,
          v,
          y
        );
      else
        break;
      w++;
    }
    for (; w <= S && w <= A; ) {
      const T = c[S], D = u[A] = y ? Le(u[A]) : Ee(u[A]);
      if (vt(T, D))
        $(
          T,
          D,
          h,
          null,
          g,
          _,
          x,
          v,
          y
        );
      else
        break;
      S--, A--;
    }
    if (w > S) {
      if (w <= A) {
        const T = A + 1, D = T < C ? u[T].el : b;
        for (; w <= A; )
          $(
            null,
            u[w] = y ? Le(u[w]) : Ee(u[w]),
            h,
            D,
            g,
            _,
            x,
            v,
            y
          ), w++;
      }
    } else if (w > A)
      for (; w <= S; )
        ye(c[w], g, _, !0), w++;
    else {
      const T = w, D = w, U = /* @__PURE__ */ new Map();
      for (w = D; w <= A; w++) {
        const fe = u[w] = y ? Le(u[w]) : Ee(u[w]);
        fe.key != null && U.set(fe.key, w);
      }
      let H, ue = 0;
      const ae = A - D + 1;
      let ve = !1, xe = 0;
      const wt = new Array(ae);
      for (w = 0; w < ae; w++) wt[w] = 0;
      for (w = T; w <= S; w++) {
        const fe = c[w];
        if (ue >= ae) {
          ye(fe, g, _, !0);
          continue;
        }
        let Se;
        if (fe.key != null)
          Se = U.get(fe.key);
        else
          for (H = D; H <= A; H++)
            if (wt[H - D] === 0 && vt(fe, u[H])) {
              Se = H;
              break;
            }
        Se === void 0 ? ye(fe, g, _, !0) : (wt[Se - D] = w + 1, Se >= xe ? xe = Se : ve = !0, $(
          fe,
          u[Se],
          h,
          null,
          g,
          _,
          x,
          v,
          y
        ), ue++);
      }
      const hn = ve ? Mo(wt) : ut;
      for (H = hn.length - 1, w = ae - 1; w >= 0; w--) {
        const fe = D + w, Se = u[fe], pn = fe + 1 < C ? u[fe + 1].el : b;
        wt[w] === 0 ? $(
          null,
          Se,
          h,
          pn,
          g,
          _,
          x,
          v,
          y
        ) : ve && (H < 0 || w !== hn[H] ? ze(Se, h, pn, 2) : H--);
      }
    }
  }, ze = (c, u, h, b, g = null) => {
    const { el: _, type: x, transition: v, children: y, shapeFlag: w } = c;
    if (w & 6) {
      ze(c.component.subTree, u, h, b);
      return;
    }
    if (w & 128) {
      c.suspense.move(u, h, b);
      return;
    }
    if (w & 64) {
      x.move(c, u, h, bt);
      return;
    }
    if (x === Z) {
      n(_, u, h);
      for (let S = 0; S < y.length; S++)
        ze(y[S], u, h, b);
      n(c.anchor, u, h);
      return;
    }
    if (x === Is) {
      z(c, u, h);
      return;
    }
    if (b !== 2 && w & 1 && v)
      if (b === 0)
        v.beforeEnter(_), n(_, u, h), de(() => v.enter(_), g);
      else {
        const { leave: S, delayLeave: A, afterLeave: T } = v, D = () => n(_, u, h), U = () => {
          S(_, () => {
            D(), T && T();
          });
        };
        A ? A(_, D, U) : U();
      }
    else
      n(_, u, h);
  }, ye = (c, u, h, b = !1, g = !1) => {
    const {
      type: _,
      props: x,
      ref: v,
      children: y,
      dynamicChildren: w,
      shapeFlag: C,
      patchFlag: S,
      dirs: A,
      cacheIndex: T
    } = c;
    if (S === -2 && (g = !1), v != null && es(v, null, h, c, !0), T != null && (u.renderCache[T] = void 0), C & 256) {
      u.ctx.deactivate(c);
      return;
    }
    const D = C & 1 && A, U = !Et(c);
    let H;
    if (U && (H = x && x.onVnodeBeforeUnmount) && Ie(H, u, c), C & 6)
      ri(c.component, h, b);
    else {
      if (C & 128) {
        c.suspense.unmount(h, b);
        return;
      }
      D && Ye(c, null, u, "beforeUnmount"), C & 64 ? c.type.remove(
        c,
        u,
        h,
        bt,
        b
      ) : w && // #5154
      // when v-once is used inside a block, setBlockTracking(-1) marks the
      // parent block with hasOnce: true
      // so that it doesn't take the fast path during unmount - otherwise
      // components nested in v-once are never unmounted.
      !w.hasOnce && // #1153: fast path should not be taken for non-stable (v-for) fragments
      (_ !== Z || S > 0 && S & 64) ? _t(
        w,
        u,
        h,
        !1,
        !0
      ) : (_ === Z && S & 384 || !g && C & 16) && _t(y, u, h), b && fn(c);
    }
    (U && (H = x && x.onVnodeUnmounted) || D) && de(() => {
      H && Ie(H, u, c), D && Ye(c, null, u, "unmounted");
    }, h);
  }, fn = (c) => {
    const { type: u, el: h, anchor: b, transition: g } = c;
    if (u === Z) {
      ni(h, b);
      return;
    }
    if (u === Is) {
      E(c);
      return;
    }
    const _ = () => {
      r(h), g && !g.persisted && g.afterLeave && g.afterLeave();
    };
    if (c.shapeFlag & 1 && g && !g.persisted) {
      const { leave: x, delayLeave: v } = g, y = () => x(h, _);
      v ? v(c.el, _, y) : y();
    } else
      _();
  }, ni = (c, u) => {
    let h;
    for (; c !== u; )
      h = m(c), r(c), c = h;
    r(u);
  }, ri = (c, u, h) => {
    const { bum: b, scope: g, job: _, subTree: x, um: v, m: y, a: w } = c;
    In(y), In(w), b && _s(b), g.stop(), _ && (_.flags |= 8, ye(x, c, u, h)), v && de(v, u), de(() => {
      c.isUnmounted = !0;
    }, u), u && u.pendingBranch && !u.isUnmounted && c.asyncDep && !c.asyncResolved && c.suspenseId === u.pendingId && (u.deps--, u.deps === 0 && u.resolve());
  }, _t = (c, u, h, b = !1, g = !1, _ = 0) => {
    for (let x = _; x < c.length; x++)
      ye(c[x], u, h, b, g);
  }, Wt = (c) => {
    if (c.shapeFlag & 6)
      return Wt(c.component.subTree);
    if (c.shapeFlag & 128)
      return c.suspense.next();
    const u = m(c.anchor || c.el), h = u && u[Zi];
    return h ? m(h) : u;
  };
  let gs = !1;
  const dn = (c, u, h) => {
    c == null ? u._vnode && ye(u._vnode, null, null, !0) : $(
      u._vnode || null,
      c,
      u,
      null,
      null,
      null,
      h
    ), u._vnode = c, gs || (gs = !0, bn(), vr(), gs = !1);
  }, bt = {
    p: $,
    um: ye,
    m: ze,
    r: fn,
    mt: ps,
    mc: ke,
    pc: W,
    pbc: qe,
    n: Wt,
    o: e
  };
  return {
    render: dn,
    hydrate: void 0,
    createApp: wo(dn)
  };
}
function Ss({ type: e, props: t }, s) {
  return s === "svg" && e === "foreignObject" || s === "mathml" && e === "annotation-xml" && t && t.encoding && t.encoding.includes("html") ? void 0 : s;
}
function Xe({ effect: e, job: t }, s) {
  s ? (e.flags |= 32, t.flags |= 4) : (e.flags &= -33, t.flags &= -5);
}
function Ro(e, t) {
  return (!e || e && !e.pendingBranch) && t && !t.persisted;
}
function Wr(e, t, s = !1) {
  const n = e.children, r = t.children;
  if (R(n) && R(r))
    for (let i = 0; i < n.length; i++) {
      const o = n[i];
      let l = r[i];
      l.shapeFlag & 1 && !l.dynamicChildren && ((l.patchFlag <= 0 || l.patchFlag === 32) && (l = r[i] = Le(r[i]), l.el = o.el), !s && l.patchFlag !== -2 && Wr(o, l)), l.type === hs && (l.el = o.el);
    }
}
function Mo(e) {
  const t = e.slice(), s = [0];
  let n, r, i, o, l;
  const a = e.length;
  for (n = 0; n < a; n++) {
    const d = e[n];
    if (d !== 0) {
      if (r = s[s.length - 1], e[r] < d) {
        t[n] = r, s.push(n);
        continue;
      }
      for (i = 0, o = s.length - 1; i < o; )
        l = i + o >> 1, e[s[l]] < d ? i = l + 1 : o = l;
      d < e[s[i]] && (i > 0 && (t[n] = s[i - 1]), s[i] = n);
    }
  }
  for (i = s.length, o = s[i - 1]; i-- > 0; )
    s[i] = o, o = t[o];
  return s;
}
function Ur(e) {
  const t = e.subTree.component;
  if (t)
    return t.asyncDep && !t.asyncResolved ? t : Ur(t);
}
function In(e) {
  if (e)
    for (let t = 0; t < e.length; t++)
      e[t].flags |= 8;
}
const Po = Symbol.for("v-scx"), $o = () => qt(Po);
function Jt(e, t, s) {
  return Vr(e, t, s);
}
function Vr(e, t, s = K) {
  const { immediate: n, deep: r, flush: i, once: o } = s, l = re({}, s), a = t && n || !t && i !== "post";
  let d;
  if (Dt) {
    if (i === "sync") {
      const I = $o();
      d = I.__watcherHandles || (I.__watcherHandles = []);
    } else if (!a) {
      const I = () => {
      };
      return I.stop = Re, I.resume = Re, I.pause = Re, I;
    }
  }
  const f = ce;
  l.call = (I, O, $) => Me(I, f, O, $);
  let p = !1;
  i === "post" ? l.scheduler = (I) => {
    de(I, f && f.suspense);
  } : i !== "sync" && (p = !0, l.scheduler = (I, O) => {
    O ? I() : nn(I);
  }), l.augmentJob = (I) => {
    t && (I.flags |= 4), p && (I.flags |= 2, f && (I.id = f.uid, I.i = f));
  };
  const m = qi(e, t, l);
  return Dt && (d ? d.push(m) : a && m()), m;
}
function Oo(e, t, s) {
  const n = this.proxy, r = Q(e) ? e.includes(".") ? Kr(n, e) : () => n[e] : e.bind(n, n);
  let i;
  M(t) ? i = t : (i = t.handler, s = t);
  const o = Nt(this), l = Vr(r, i.bind(n), s);
  return o(), l;
}
function Kr(e, t) {
  const s = t.split(".");
  return () => {
    let n = e;
    for (let r = 0; r < s.length && n; r++)
      n = n[s[r]];
    return n;
  };
}
const Do = (e, t) => t === "modelValue" || t === "model-value" ? e.modelModifiers : e[`${t}Modifiers`] || e[`${We(t)}Modifiers`] || e[`${ot(t)}Modifiers`];
function Fo(e, t, ...s) {
  if (e.isUnmounted) return;
  const n = e.vnode.props || K;
  let r = s;
  const i = t.startsWith("update:"), o = i && Do(n, t.slice(7));
  o && (o.trim && (r = s.map((f) => Q(f) ? f.trim() : f)), o.number && (r = s.map(di)));
  let l, a = n[l = ms(t)] || // also try camelCase event handler (#2249)
  n[l = ms(We(t))];
  !a && i && (a = n[l = ms(ot(t))]), a && Me(
    a,
    e,
    6,
    r
  );
  const d = n[l + "Once"];
  if (d) {
    if (!e.emitted)
      e.emitted = {};
    else if (e.emitted[l])
      return;
    e.emitted[l] = !0, Me(
      d,
      e,
      6,
      r
    );
  }
}
function Gr(e, t, s = !1) {
  const n = t.emitsCache, r = n.get(e);
  if (r !== void 0)
    return r;
  const i = e.emits;
  let o = {}, l = !1;
  if (!M(e)) {
    const a = (d) => {
      const f = Gr(d, t, !0);
      f && (l = !0, re(o, f));
    };
    !s && t.mixins.length && t.mixins.forEach(a), e.extends && a(e.extends), e.mixins && e.mixins.forEach(a);
  }
  return !i && !l ? (q(e) && n.set(e, null), null) : (R(i) ? i.forEach((a) => o[a] = null) : re(o, i), q(e) && n.set(e, o), o);
}
function ds(e, t) {
  return !e || !is(t) ? !1 : (t = t.slice(2).replace(/Once$/, ""), L(e, t[0].toLowerCase() + t.slice(1)) || L(e, ot(t)) || L(e, t));
}
function An(e) {
  const {
    type: t,
    vnode: s,
    proxy: n,
    withProxy: r,
    propsOptions: [i],
    slots: o,
    attrs: l,
    emit: a,
    render: d,
    renderCache: f,
    props: p,
    data: m,
    setupState: I,
    ctx: O,
    inheritAttrs: $
  } = e, Y = Qt(e);
  let k, J;
  try {
    if (s.shapeFlag & 4) {
      const E = r || n, ee = E;
      k = Ee(
        d.call(
          ee,
          E,
          f,
          p,
          I,
          m,
          O
        )
      ), J = l;
    } else {
      const E = t;
      k = Ee(
        E.length > 1 ? E(
          p,
          { attrs: l, slots: o, emit: a }
        ) : E(
          p,
          null
        )
      ), J = t.props ? l : ko(l);
    }
  } catch (E) {
    Rt.length = 0, us(E, e, 1), k = be(it);
  }
  let z = k;
  if (J && $ !== !1) {
    const E = Object.keys(J), { shapeFlag: ee } = z;
    E.length && ee & 7 && (i && E.some(Gs) && (J = No(
      J,
      i
    )), z = gt(z, J, !1, !0));
  }
  return s.dirs && (z = gt(z, null, !1, !0), z.dirs = z.dirs ? z.dirs.concat(s.dirs) : s.dirs), s.transition && rn(z, s.transition), k = z, Qt(Y), k;
}
const ko = (e) => {
  let t;
  for (const s in e)
    (s === "class" || s === "style" || is(s)) && ((t || (t = {}))[s] = e[s]);
  return t;
}, No = (e, t) => {
  const s = {};
  for (const n in e)
    (!Gs(n) || !(n.slice(9) in t)) && (s[n] = e[n]);
  return s;
};
function Lo(e, t, s) {
  const { props: n, children: r, component: i } = e, { props: o, children: l, patchFlag: a } = t, d = i.emitsOptions;
  if (t.dirs || t.transition)
    return !0;
  if (s && a >= 0) {
    if (a & 1024)
      return !0;
    if (a & 16)
      return n ? Cn(n, o, d) : !!o;
    if (a & 8) {
      const f = t.dynamicProps;
      for (let p = 0; p < f.length; p++) {
        const m = f[p];
        if (o[m] !== n[m] && !ds(d, m))
          return !0;
      }
    }
  } else
    return (r || l) && (!l || !l.$stable) ? !0 : n === o ? !1 : n ? o ? Cn(n, o, d) : !0 : !!o;
  return !1;
}
function Cn(e, t, s) {
  const n = Object.keys(t);
  if (n.length !== Object.keys(e).length)
    return !0;
  for (let r = 0; r < n.length; r++) {
    const i = n[r];
    if (t[i] !== e[i] && !ds(s, i))
      return !0;
  }
  return !1;
}
function Ho({ vnode: e, parent: t }, s) {
  for (; t; ) {
    const n = t.subTree;
    if (n.suspense && n.suspense.activeBranch === e && (n.el = e.el), n === e)
      (e = t.vnode).el = s, t = t.parent;
    else
      break;
  }
}
const qr = (e) => e.__isSuspense;
function jo(e, t) {
  t && t.pendingBranch ? R(e) ? t.effects.push(...e) : t.effects.push(e) : Yi(e);
}
const Z = Symbol.for("v-fgt"), hs = Symbol.for("v-txt"), it = Symbol.for("v-cmt"), Is = Symbol.for("v-stc"), Rt = [];
let ge = null;
function F(e = !1) {
  Rt.push(ge = e ? null : []);
}
function Bo() {
  Rt.pop(), ge = Rt[Rt.length - 1] || null;
}
let Ot = 1;
function En(e, t = !1) {
  Ot += e, e < 0 && ge && t && (ge.hasOnce = !0);
}
function Jr(e) {
  return e.dynamicChildren = Ot > 0 ? ge || ut : null, Bo(), Ot > 0 && ge && ge.push(e), e;
}
function B(e, t, s, n, r, i) {
  return Jr(
    P(
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
function et(e, t, s, n, r) {
  return Jr(
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
function zr(e) {
  return e ? e.__v_isVNode === !0 : !1;
}
function vt(e, t) {
  return e.type === t.type && e.key === t.key;
}
const Yr = ({ key: e }) => e ?? null, zt = ({
  ref: e,
  ref_key: t,
  ref_for: s
}) => (typeof e == "number" && (e = "" + e), e != null ? Q(e) || ne(e) || M(e) ? { i: Te, r: e, k: t, f: !!s } : e : null);
function P(e, t = null, s = null, n = 0, r = null, i = e === Z ? 0 : 1, o = !1, l = !1) {
  const a = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e,
    props: t,
    key: t && Yr(t),
    ref: t && zt(t),
    scopeId: Sr,
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
    ctx: Te
  };
  return l ? (ln(a, s), i & 128 && e.normalize(a)) : s && (a.shapeFlag |= Q(s) ? 8 : 16), Ot > 0 && // avoid a block node from tracking itself
  !o && // has current parent block
  ge && // presence of a patch flag indicates this node needs patching on updates.
  // component nodes also should always be patched, because even if the
  // component doesn't need to update, it needs to persist the instance on to
  // the next vnode so that it can be properly unmounted later.
  (a.patchFlag > 0 || i & 6) && // the EVENTS flag is only for hydration and if it is the only flag, the
  // vnode should not be considered dynamic due to handler caching.
  a.patchFlag !== 32 && ge.push(a), a;
}
const be = Wo;
function Wo(e, t = null, s = null, n = 0, r = null, i = !1) {
  if ((!e || e === uo) && (e = it), zr(e)) {
    const l = gt(
      e,
      t,
      !0
      /* mergeRef: true */
    );
    return s && ln(l, s), Ot > 0 && !i && ge && (l.shapeFlag & 6 ? ge[ge.indexOf(e)] = l : ge.push(l)), l.patchFlag = -2, l;
  }
  if (Zo(e) && (e = e.__vccOpts), t) {
    t = Uo(t);
    let { class: l, style: a } = t;
    l && !Q(l) && (t.class = lt(l)), q(a) && (sn(a) && !R(a) && (a = re({}, a)), t.style = pe(a));
  }
  const o = Q(e) ? 1 : qr(e) ? 128 : Qi(e) ? 64 : q(e) ? 4 : M(e) ? 2 : 0;
  return P(
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
function Uo(e) {
  return e ? sn(e) || Fr(e) ? re({}, e) : e : null;
}
function gt(e, t, s = !1, n = !1) {
  const { props: r, ref: i, patchFlag: o, children: l, transition: a } = e, d = t ? Vo(r || {}, t) : r, f = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e.type,
    props: d,
    key: d && Yr(d),
    ref: t && t.ref ? (
      // #2078 in the case of <component :is="vnode" ref="extra"/>
      // if the vnode itself already has a ref, cloneVNode will need to merge
      // the refs so the single vnode can be set on multiple refs
      s && i ? R(i) ? i.concat(zt(t)) : [i, zt(t)] : zt(t)
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
    patchFlag: t && e.type !== Z ? o === -1 ? 16 : o | 16 : o,
    dynamicProps: e.dynamicProps,
    dynamicChildren: e.dynamicChildren,
    appContext: e.appContext,
    dirs: e.dirs,
    transition: a,
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
  return a && n && rn(
    f,
    a.clone(f)
  ), f;
}
function tt(e = " ", t = 0) {
  return be(hs, null, e, t);
}
function Ce(e = "", t = !1) {
  return t ? (F(), et(it, null, e)) : be(it, null, e);
}
function Ee(e) {
  return e == null || typeof e == "boolean" ? be(it) : R(e) ? be(
    Z,
    null,
    // #3666, avoid reference pollution when reusing vnode
    e.slice()
  ) : zr(e) ? Le(e) : be(hs, null, String(e));
}
function Le(e) {
  return e.el === null && e.patchFlag !== -1 || e.memo ? e : gt(e);
}
function ln(e, t) {
  let s = 0;
  const { shapeFlag: n } = e;
  if (t == null)
    t = null;
  else if (R(t))
    s = 16;
  else if (typeof t == "object")
    if (n & 65) {
      const r = t.default;
      r && (r._c && (r._d = !1), ln(e, r()), r._c && (r._d = !0));
      return;
    } else {
      s = 32;
      const r = t._;
      !r && !Fr(t) ? t._ctx = Te : r === 3 && Te && (Te.slots._ === 1 ? t._ = 1 : (t._ = 2, e.patchFlag |= 1024));
    }
  else M(t) ? (t = { default: t, _ctx: Te }, s = 32) : (t = String(t), n & 64 ? (s = 16, t = [tt(t)]) : s = 8);
  e.children = t, e.shapeFlag |= s;
}
function Vo(...e) {
  const t = {};
  for (let s = 0; s < e.length; s++) {
    const n = e[s];
    for (const r in n)
      if (r === "class")
        t.class !== n.class && (t.class = lt([t.class, n.class]));
      else if (r === "style")
        t.style = pe([t.style, n.style]);
      else if (is(r)) {
        const i = t[r], o = n[r];
        o && i !== o && !(R(i) && i.includes(o)) && (t[r] = i ? [].concat(i, o) : o);
      } else r !== "" && (t[r] = n[r]);
  }
  return t;
}
function Ie(e, t, s, n = null) {
  Me(e, t, 7, [
    s,
    n
  ]);
}
const Ko = $r();
let Go = 0;
function qo(e, t, s) {
  const n = e.type, r = (t ? t.appContext : e.appContext) || Ko, i = {
    uid: Go++,
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
    scope: new wi(
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
    propsOptions: Nr(n, r),
    emitsOptions: Gr(n, r),
    // emit
    emit: null,
    // to be set immediately
    emitted: null,
    // props default value
    propsDefaults: K,
    // inheritAttrs
    inheritAttrs: n.inheritAttrs,
    // state
    ctx: K,
    data: K,
    props: K,
    attrs: K,
    slots: K,
    refs: K,
    setupState: K,
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
  return i.ctx = { _: i }, i.root = t ? t.root : i, i.emit = Fo.bind(null, i), e.ce && e.ce(i), i;
}
let ce = null, ss, js;
{
  const e = cs(), t = (s, n) => {
    let r;
    return (r = e[s]) || (r = e[s] = []), r.push(n), (i) => {
      r.length > 1 ? r.forEach((o) => o(i)) : r[0](i);
    };
  };
  ss = t(
    "__VUE_INSTANCE_SETTERS__",
    (s) => ce = s
  ), js = t(
    "__VUE_SSR_SETTERS__",
    (s) => Dt = s
  );
}
const Nt = (e) => {
  const t = ce;
  return ss(e), e.scope.on(), () => {
    e.scope.off(), ss(t);
  };
}, Tn = () => {
  ce && ce.scope.off(), ss(null);
};
function Xr(e) {
  return e.vnode.shapeFlag & 4;
}
let Dt = !1;
function Jo(e, t = !1, s = !1) {
  t && js(t);
  const { props: n, children: r } = e.vnode, i = Xr(e);
  vo(e, n, i, t), Ao(e, r, s);
  const o = i ? zo(e, t) : void 0;
  return t && js(!1), o;
}
function zo(e, t) {
  const s = e.type;
  e.accessCache = /* @__PURE__ */ Object.create(null), e.proxy = new Proxy(e.ctx, fo);
  const { setup: n } = s;
  if (n) {
    Ve();
    const r = e.setupContext = n.length > 1 ? Xo(e) : null, i = Nt(e), o = kt(
      n,
      e,
      0,
      [
        e.props,
        r
      ]
    ), l = qn(o);
    if (Ke(), i(), (l || e.sp) && !Et(e) && Ir(e), l) {
      if (o.then(Tn, Tn), t)
        return o.then((a) => {
          Rn(e, a);
        }).catch((a) => {
          us(a, e, 0);
        });
      e.asyncDep = o;
    } else
      Rn(e, o);
  } else
    Zr(e);
}
function Rn(e, t, s) {
  M(t) ? e.type.__ssrInlineRender ? e.ssrRender = t : e.render = t : q(t) && (e.setupState = _r(t)), Zr(e);
}
function Zr(e, t, s) {
  const n = e.type;
  e.render || (e.render = n.render || Re);
  {
    const r = Nt(e);
    Ve();
    try {
      ho(e);
    } finally {
      Ke(), r();
    }
  }
}
const Yo = {
  get(e, t) {
    return te(e, "get", ""), e[t];
  }
};
function Xo(e) {
  const t = (s) => {
    e.exposed = s || {};
  };
  return {
    attrs: new Proxy(e.attrs, Yo),
    slots: e.slots,
    emit: e.emit,
    expose: t
  };
}
function cn(e) {
  return e.exposed ? e.exposeProxy || (e.exposeProxy = new Proxy(_r(ji(e.exposed)), {
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
function Zo(e) {
  return M(e) && "__vccOpts" in e;
}
const nt = (e, t) => Ki(e, t, Dt), Qo = "3.5.13";
/**
* @vue/runtime-dom v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
let Bs;
const Mn = typeof window < "u" && window.trustedTypes;
if (Mn)
  try {
    Bs = /* @__PURE__ */ Mn.createPolicy("vue", {
      createHTML: (e) => e
    });
  } catch {
  }
const Qr = Bs ? (e) => Bs.createHTML(e) : (e) => e, el = "http://www.w3.org/2000/svg", tl = "http://www.w3.org/1998/Math/MathML", $e = typeof document < "u" ? document : null, Pn = $e && /* @__PURE__ */ $e.createElement("template"), sl = {
  insert: (e, t, s) => {
    t.insertBefore(e, s || null);
  },
  remove: (e) => {
    const t = e.parentNode;
    t && t.removeChild(e);
  },
  createElement: (e, t, s, n) => {
    const r = t === "svg" ? $e.createElementNS(el, e) : t === "mathml" ? $e.createElementNS(tl, e) : s ? $e.createElement(e, { is: s }) : $e.createElement(e);
    return e === "select" && n && n.multiple != null && r.setAttribute("multiple", n.multiple), r;
  },
  createText: (e) => $e.createTextNode(e),
  createComment: (e) => $e.createComment(e),
  setText: (e, t) => {
    e.nodeValue = t;
  },
  setElementText: (e, t) => {
    e.textContent = t;
  },
  parentNode: (e) => e.parentNode,
  nextSibling: (e) => e.nextSibling,
  querySelector: (e) => $e.querySelector(e),
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
      Pn.innerHTML = Qr(
        n === "svg" ? `<svg>${e}</svg>` : n === "mathml" ? `<math>${e}</math>` : e
      );
      const l = Pn.content;
      if (n === "svg" || n === "mathml") {
        const a = l.firstChild;
        for (; a.firstChild; )
          l.appendChild(a.firstChild);
        l.removeChild(a);
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
}, nl = Symbol("_vtc");
function rl(e, t, s) {
  const n = e[nl];
  n && (t = (t ? [t, ...n] : [...n]).join(" ")), t == null ? e.removeAttribute("class") : s ? e.setAttribute("class", t) : e.className = t;
}
const $n = Symbol("_vod"), il = Symbol("_vsh"), ol = Symbol(""), ll = /(^|;)\s*display\s*:/;
function cl(e, t, s) {
  const n = e.style, r = Q(s);
  let i = !1;
  if (s && !r) {
    if (t)
      if (Q(t))
        for (const o of t.split(";")) {
          const l = o.slice(0, o.indexOf(":")).trim();
          s[l] == null && Yt(n, l, "");
        }
      else
        for (const o in t)
          s[o] == null && Yt(n, o, "");
    for (const o in s)
      o === "display" && (i = !0), Yt(n, o, s[o]);
  } else if (r) {
    if (t !== s) {
      const o = n[ol];
      o && (s += ";" + o), n.cssText = s, i = ll.test(s);
    }
  } else t && e.removeAttribute("style");
  $n in e && (e[$n] = i ? n.display : "", e[il] && (n.display = "none"));
}
const On = /\s*!important$/;
function Yt(e, t, s) {
  if (R(s))
    s.forEach((n) => Yt(e, t, n));
  else if (s == null && (s = ""), t.startsWith("--"))
    e.setProperty(t, s);
  else {
    const n = al(e, t);
    On.test(s) ? e.setProperty(
      ot(n),
      s.replace(On, ""),
      "important"
    ) : e[n] = s;
  }
}
const Dn = ["Webkit", "Moz", "ms"], As = {};
function al(e, t) {
  const s = As[t];
  if (s)
    return s;
  let n = We(t);
  if (n !== "filter" && n in e)
    return As[t] = n;
  n = Yn(n);
  for (let r = 0; r < Dn.length; r++) {
    const i = Dn[r] + n;
    if (i in e)
      return As[t] = i;
  }
  return t;
}
const Fn = "http://www.w3.org/1999/xlink";
function kn(e, t, s, n, r, i = bi(t)) {
  n && t.startsWith("xlink:") ? s == null ? e.removeAttributeNS(Fn, t.slice(6, t.length)) : e.setAttributeNS(Fn, t, s) : s == null || i && !Zn(s) ? e.removeAttribute(t) : e.setAttribute(
    t,
    i ? "" : Ue(s) ? String(s) : s
  );
}
function Nn(e, t, s, n, r) {
  if (t === "innerHTML" || t === "textContent") {
    s != null && (e[t] = t === "innerHTML" ? Qr(s) : s);
    return;
  }
  const i = e.tagName;
  if (t === "value" && i !== "PROGRESS" && // custom elements may use _value internally
  !i.includes("-")) {
    const l = i === "OPTION" ? e.getAttribute("value") || "" : e.value, a = s == null ? (
      // #11647: value should be set as empty string for null and undefined,
      // but <input type="checkbox"> should be set as 'on'.
      e.type === "checkbox" ? "on" : ""
    ) : String(s);
    (l !== a || !("_value" in e)) && (e.value = a), s == null && e.removeAttribute(t), e._value = s;
    return;
  }
  let o = !1;
  if (s === "" || s == null) {
    const l = typeof e[t];
    l === "boolean" ? s = Zn(s) : s == null && l === "string" ? (s = "", o = !0) : l === "number" && (s = 0, o = !0);
  }
  try {
    e[t] = s;
  } catch {
  }
  o && e.removeAttribute(r || t);
}
function ul(e, t, s, n) {
  e.addEventListener(t, s, n);
}
function fl(e, t, s, n) {
  e.removeEventListener(t, s, n);
}
const Ln = Symbol("_vei");
function dl(e, t, s, n, r = null) {
  const i = e[Ln] || (e[Ln] = {}), o = i[t];
  if (n && o)
    o.value = n;
  else {
    const [l, a] = hl(t);
    if (n) {
      const d = i[t] = ml(
        n,
        r
      );
      ul(e, l, d, a);
    } else o && (fl(e, l, o, a), i[t] = void 0);
  }
}
const Hn = /(?:Once|Passive|Capture)$/;
function hl(e) {
  let t;
  if (Hn.test(e)) {
    t = {};
    let n;
    for (; n = e.match(Hn); )
      e = e.slice(0, e.length - n[0].length), t[n[0].toLowerCase()] = !0;
  }
  return [e[2] === ":" ? e.slice(3) : ot(e.slice(2)), t];
}
let Cs = 0;
const pl = /* @__PURE__ */ Promise.resolve(), gl = () => Cs || (pl.then(() => Cs = 0), Cs = Date.now());
function ml(e, t) {
  const s = (n) => {
    if (!n._vts)
      n._vts = Date.now();
    else if (n._vts <= s.attached)
      return;
    Me(
      _l(n, s.value),
      t,
      5,
      [n]
    );
  };
  return s.value = e, s.attached = gl(), s;
}
function _l(e, t) {
  if (R(t)) {
    const s = e.stopImmediatePropagation;
    return e.stopImmediatePropagation = () => {
      s.call(e), e._stopped = !0;
    }, t.map(
      (n) => (r) => !r._stopped && n && n(r)
    );
  } else
    return t;
}
const jn = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && // lowercase letter
e.charCodeAt(2) > 96 && e.charCodeAt(2) < 123, bl = (e, t, s, n, r, i) => {
  const o = r === "svg";
  t === "class" ? rl(e, n, o) : t === "style" ? cl(e, s, n) : is(t) ? Gs(t) || dl(e, t, s, n, i) : (t[0] === "." ? (t = t.slice(1), !0) : t[0] === "^" ? (t = t.slice(1), !1) : wl(e, t, n, o)) ? (Nn(e, t, n), !e.tagName.includes("-") && (t === "value" || t === "checked" || t === "selected") && kn(e, t, n, o, i, t !== "value")) : /* #11081 force set props for possible async custom element */ e._isVueCE && (/[A-Z]/.test(t) || !Q(n)) ? Nn(e, We(t), n, i, t) : (t === "true-value" ? e._trueValue = n : t === "false-value" && (e._falseValue = n), kn(e, t, n, o));
};
function wl(e, t, s, n) {
  if (n)
    return !!(t === "innerHTML" || t === "textContent" || t in e && jn(t) && M(s));
  if (t === "spellcheck" || t === "draggable" || t === "translate" || t === "form" || t === "list" && e.tagName === "INPUT" || t === "type" && e.tagName === "TEXTAREA")
    return !1;
  if (t === "width" || t === "height") {
    const r = e.tagName;
    if (r === "IMG" || r === "VIDEO" || r === "CANVAS" || r === "SOURCE")
      return !1;
  }
  return jn(t) && Q(s) ? !1 : t in e;
}
const yl = /* @__PURE__ */ re({ patchProp: bl }, sl);
let Bn;
function vl() {
  return Bn || (Bn = Eo(yl));
}
const xl = (...e) => {
  const t = vl().createApp(...e), { mount: s } = t;
  return t.mount = (n) => {
    const r = Il(n);
    if (!r) return;
    const i = t._component;
    !M(i) && !i.render && !i.template && (i.template = r.innerHTML), r.nodeType === 1 && (r.textContent = "");
    const o = s(r, !1, Sl(r));
    return r instanceof Element && (r.removeAttribute("v-cloak"), r.setAttribute("data-v-app", "")), o;
  }, t;
};
function Sl(e) {
  if (e instanceof SVGElement)
    return "svg";
  if (typeof MathMLElement == "function" && e instanceof MathMLElement)
    return "mathml";
}
function Il(e) {
  return Q(e) ? document.querySelector(e) : e;
}
function Al(e, t, s) {
  return e.logs.filter((n) => {
    if (n.cursor <= s.get(n.runId)) return !1;
    if (t.mode === "all") return !0;
    if (n.runId !== t.runId) return !1;
    const r = e.runs[n.runId];
    return (n.phaseId && (r == null ? void 0 : r.instanceOfPhase[n.phaseId]) || n.instanceId || n.phaseId) === t.instanceId;
  });
}
function Cl(e, t, s) {
  s.set(t, Math.max(s.get(t), e.maxCursor));
}
const Ws = "@runner", Wn = 5e3;
function El() {
  return { runs: {}, logs: [], seen: {}, maxCursor: 0 };
}
function Tl(e) {
  return e.outcome !== null || e.abandoned;
}
function Rl(e) {
  return Object.values(e.phases).sort((t, s) => t.order - s.order);
}
function Gt(e) {
  e.visible = Rl(e).map((t) => t.instanceId);
}
function Ml(e, t, s) {
  e.visible = e.visible.map((n) => n === t ? s : n);
  for (const n of e.arrows)
    n.from === t && (n.from = s), n.to === t && (n.to = s);
}
const Pl = /* @__PURE__ */ new Set([
  "phase_start",
  "bound",
  "progress",
  "tool_call",
  "tool_result",
  "message",
  "log"
]);
function Un(e) {
  return {
    runId: e.run_id,
    adwName: e.adw_name,
    status: e.status,
    startedAt: e.started_at,
    endedAt: e.ended_at,
    phases: {},
    instanceOfPhase: {},
    arrows: [],
    visible: []
  };
}
function ei(e, t) {
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
function $l(e, t) {
  return t.phase_id && e.instanceOfPhase[t.phase_id] ? e.instanceOfPhase[t.phase_id] : t.instance_id || t.phase_id;
}
function Ol(e, t) {
  const s = t.instance_id, n = e.phases[t.phase_id], r = e.phases[s] ?? ei(t, s);
  return n && n !== r && (r.started = r.started || n.started, r.startedAt = r.startedAt || n.startedAt, r.lastProgressAt = Math.max(
    r.lastProgressAt,
    n.lastProgressAt
  ), r.outcome = r.outcome ?? n.outcome, delete e.phases[t.phase_id], Ml(e, t.phase_id, s)), e.phases[s] = r, e.instanceOfPhase[t.phase_id] = s, r.phaseId = t.phase_id, r;
}
function ns(e, t, s, n, r, i) {
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
function Dl(e, t, s) {
  if (t.kind === "progress") {
    t.message && ns(e, t, s, s, t.message, !1);
    return;
  }
  if (t.kind !== "tool_call" && t.kind !== "tool_result" && t.kind !== "message")
    return;
  const n = t.kind === "message" && t.source_instance && t.target_instance;
  ns(
    e,
    t,
    n ? t.source_instance : s,
    n ? t.target_instance : s,
    t.message,
    t.kind === "tool_result"
  );
}
function Fl(e, t) {
  if (!e || !t) return "";
  const s = Math.max(0, t - e);
  return s < 1e3 ? `${Math.round(s)} ms` : `${(s / 1e3).toFixed(1)}s`;
}
function kl(e, t) {
  var i;
  const s = Date.parse(t.recorded_at) || 0, n = $l(e, t);
  if (!n) return;
  let r;
  if (t.kind === "bound" ? r = Ol(e, t) : ((i = e.phases)[n] ?? (i[n] = ei(t, n)), r = e.phases[n]), t.attempt !== null && t.attempt !== void 0 && (r.attempt = t.attempt), Dl(e, t, r.instanceId), t.kind === "constructed" ? (r.constructed = !0, r.className = t.message) : t.kind === "purpose" ? r.purpose = t.message : t.kind === "cleanup" ? (r.cleanup = t.message, !r.started && r.outcome === null && (r.abandoned = !0)) : t.kind === "error" && (r.error = t.message), r.outcome !== null || r.abandoned) {
    Gt(e);
    return;
  }
  if (t.kind === "phase_end" && t.status && t.status !== "running") {
    r.outcome = t.status, r.endedAt = s, r.started = !0, ns(
      e,
      t,
      r.instanceId,
      Ws,
      [t.status, Fl(r.startedAt, s), r.error].filter(Boolean).join(" · "),
      !0
    ), Gt(e);
    return;
  }
  if (t.kind === "waiting" ? (r.waitDeadlineAt = t.deadline_at ? Date.parse(t.deadline_at) : null, r.waitReason = t.message, r.lastProgressAt = s) : Pl.has(t.kind) && (r.waitDeadlineAt = null, r.waitReason = "", r.lastProgressAt = s), (t.kind === "phase_start" || t.kind === "bound") && !r.started) {
    r.started = !0, r.startedAt = s, t.kind === "phase_start" && (r.phaseId = t.phase_id), ns(e, t, Ws, r.instanceId, r.name, !1), Gt(e);
    return;
  }
  Gt(e);
}
function Nl(e) {
  const t = [e.run_id, e.phase_name, e.kind].filter(Boolean).join(" ");
  return `${e.recorded_at} [${t}] ${e.message}`;
}
function Ll(e, t) {
  var i, o, l, a;
  const s = t.events.filter((d) => !e.seen[d.event_id]), n = t.runs.some((d) => {
    const f = e.runs[d.run_id];
    return !f || f.status !== d.status || f.endedAt !== d.ended_at;
  });
  if (s.length === 0 && !n) return e;
  const r = structuredClone(e);
  for (const d of t.runs) {
    (i = r.runs)[o = d.run_id] ?? (i[o] = Un(d));
    const f = r.runs[d.run_id];
    f.status = d.status, f.endedAt = d.ended_at;
  }
  for (const d of s.sort((f, p) => f.cursor - p.cursor)) {
    r.seen[d.event_id] = !0, r.maxCursor = Math.max(r.maxCursor, d.cursor), (l = r.runs)[a = d.run_id] ?? (l[a] = Un({
      run_id: d.run_id,
      adw_name: d.adw_name,
      status: "running",
      started_at: d.recorded_at,
      ended_at: null
    }));
    const f = r.runs[d.run_id];
    kl(f, d), r.logs.push({
      cursor: d.cursor,
      eventId: d.event_id,
      runId: d.run_id,
      phaseId: d.phase_id,
      instanceId: d.instance_id,
      recordedAt: d.recorded_at,
      kind: d.kind,
      text: Nl(d)
    });
  }
  return r.logs.sort((d, f) => d.cursor - f.cursor), r.logs.length > Wn && r.logs.splice(0, r.logs.length - Wn), r;
}
const Hl = {
  idle: "Idle -- no pilot run recorded yet",
  live: "Live",
  completed: "Completed",
  pinned: "Pinned after failure"
}, ti = {
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
function jl(e, t, s, n, r, i) {
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
    const a = r.evaluate(
      {
        started: e.started,
        terminal: Tl(e),
        lastProgressAt: e.lastProgressAt,
        waitDeadlineAt: e.waitDeadlineAt,
        waitReason: e.waitReason
      },
      s,
      n
    );
    o = a ? "stalled" : e.waitDeadlineAt !== null ? "waiting" : "running", l = [
      Us(e.startedAt, s),
      (a == null ? void 0 : a.reason) ?? e.waitReason
    ].filter(Boolean).join(" -- ");
  }
  return {
    instanceId: e.instanceId,
    name: e.name,
    attempt: e.attempt,
    status: o,
    statusLabel: ti[o],
    detail: l,
    purpose: e.purpose,
    selected: i
  };
}
const Bl = {
  running: "running",
  success: "pass",
  fail: "fail",
  interrupted: "stalled"
};
function Wl(e, t) {
  const s = Bl[e.status] ?? "waiting", n = Date.parse(e.startedAt) || 0, r = e.endedAt && Date.parse(e.endedAt) || t;
  return {
    instanceId: Ws,
    kind: "runner",
    name: e.adwName,
    attempt: null,
    status: s,
    statusLabel: ti[s],
    detail: Us(n, r),
    purpose: `ADW run ${e.runId}: starts each phase and receives its outcome`,
    selected: !1
  };
}
function Ul(e, t) {
  if (!e || !t) return "";
  const s = Math.max(0, t - e);
  return s >= 1e4 ? `+${(s / 1e3).toFixed(1)} s` : `+${s} ms`;
}
function Vl(e, t, s, n, r) {
  var p;
  if (!e) return { runId: "", columns: [], rows: [] };
  const i = e.visible.map((m) => e.phases[m]).filter(Boolean).map((m) => ({
    ...jl(
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
  const o = [Wl(e, t), ...i], l = new Map(
    o.map((m, I) => [m.instanceId, I])
  ), a = Date.parse(e.startedAt) || (((p = e.arrows[0]) == null ? void 0 : p.at) ?? 0), f = e.arrows.filter((m) => l.has(m.from) && l.has(m.to)).sort((m, I) => m.cursor - I.cursor).map((m) => ({
    id: m.id,
    from: l.get(m.from),
    to: l.get(m.to),
    text: m.text,
    dashed: m.dashed,
    kind: m.kind,
    elapsed: Ul(a, m.at)
  }));
  for (const m of o) {
    if (m.kind === "runner") {
      m.activeFrom = f.length ? 0 : null, m.activeTo = e.status === "running" ? null : f.length - 1;
      continue;
    }
    const I = l.get(m.instanceId), O = f.findIndex((k) => k.to === I || k.from === I), $ = f.findIndex(
      (k) => k.kind === "phase_end" && k.from === I
    ), Y = e.phases[m.instanceId];
    m.activeFrom = Y != null && Y.started && O >= 0 ? O : null, m.activeTo = $ >= 0 ? $ : null;
  }
  return { runId: e.runId, columns: o, rows: f };
}
function Kl(e, t, s, n) {
  var i;
  const r = s.mode === "phase" ? (i = n.runs[s.runId]) == null ? void 0 : i.phases[s.instanceId] : void 0;
  return {
    modeLabel: Hl[t],
    filterLabel: s.mode === "all" ? "All events" : `Run ${s.runId} -- phase ${(r == null ? void 0 : r.name) ?? s.instanceId} (${s.instanceId}${r != null && r.attempt ? `, attempt ${r.attempt}` : ""})`,
    clearLabel: e ? `Clear displayed logs for ${e.runId}` : "Clear displayed logs",
    clearDisabledReason: e ? "" : "No ADW run is selected, so there is nothing run-scoped to clear."
  };
}
class Gl {
  constructor(t) {
    X(this, "state", El());
    X(this, "selected", { runId: null, pinReleased: !1 });
    X(this, "filter", { mode: "all" });
    X(this, "connection", { status: "connecting" });
    X(this, "timeoutSeconds", 120);
    X(this, "lastDelayMs", null);
    X(this, "renderError", "");
    X(this, "tick", null);
    X(this, "unsubscribe", null);
    X(this, "listeners", /* @__PURE__ */ new Set());
    this.deps = t;
  }
  start() {
    this.unsubscribe = this.deps.source.subscribe({
      onPage: (s) => this.onPage(s),
      onConnection: (s) => {
        this.connection = s, this.publish();
      }
    }), this.deps.source.start();
    const t = () => {
      this.publish(), this.tick = this.deps.timer.set(t, this.deps.tickMs ?? 1e3);
    };
    this.tick = this.deps.timer.set(t, this.deps.tickMs ?? 1e3);
  }
  /** The view came into sight: catch up now rather than on the slow cadence. */
  wake() {
    this.deps.source.wake();
  }
  dispose() {
    var t;
    this.deps.source.stop(), (t = this.unsubscribe) == null || t.call(this), this.deps.timer.clear(this.tick), this.deps.legacy.setVisible(!0), this.listeners.clear();
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
  clearSelectedRun() {
    this.selected.runId && (Cl(this.state, this.selected.runId, this.deps.cleared), this.publish());
  }
  reportRenderError(t) {
    this.renderError = t, this.publish();
  }
  runs() {
    return Object.values(this.state.runs).map((t) => ({
      runId: t.runId,
      status: t.status,
      startedAt: t.startedAt
    }));
  }
  follow(t) {
    t.runId !== this.selected.runId && (this.filter = { mode: "all" }), this.selected = t;
  }
  onPage(t) {
    var n, r;
    (r = (n = this.deps.clock).align) == null || r.call(n, t.server_now), this.timeoutSeconds = t.stall_timeout_seconds;
    const s = this.state;
    if (this.state = Ll(this.state, t), !t.bootstrap && this.state !== s && t.events.length > 0) {
      const i = Date.parse(
        t.events[t.events.length - 1].recorded_at
      );
      Number.isNaN(i) || (this.lastDelayMs = Math.max(0, this.deps.clock.now() - i));
    }
    this.follow(this.deps.selection.select(this.selected, this.runs())), this.publish();
  }
  view() {
    const t = this.selected.runId ? this.state.runs[this.selected.runId] : void 0, s = this.deps.selection.mode(this.selected, this.runs()), n = this.filter.mode === "phase" && this.filter.runId === (t == null ? void 0 : t.runId) ? this.filter.instanceId : null, r = this.deps.renderer.render(
      Vl(
        t,
        this.deps.clock.now(),
        this.timeoutSeconds * 1e3,
        this.deps.stall,
        n
      )
    );
    return {
      runId: (t == null ? void 0 : t.runId) ?? null,
      adwName: (t == null ? void 0 : t.adwName) ?? "",
      runStatus: (t == null ? void 0 : t.status) ?? null,
      mode: s,
      diagram: r.model,
      lines: Al(this.state, this.filter, this.deps.cleared),
      phaseSelected: this.filter.mode === "phase",
      connection: this.connection,
      renderError: r.error || this.renderError,
      stallTimeoutSeconds: this.timeoutSeconds,
      lastDelayMs: this.lastDelayMs,
      ...Kl(t, s, this.filter, this.state)
    };
  }
  publish() {
    this.deps.legacy.setVisible(this.filter.mode === "all");
    const t = this.view();
    for (const s of this.listeners) s(t);
  }
}
function Es(e, t) {
  return e.startedAt.localeCompare(t.startedAt) || e.runId.localeCompare(t.runId);
}
function Vn(e) {
  return (e == null ? void 0 : e.status) === "fail" || (e == null ? void 0 : e.status) === "interrupted";
}
class ql {
  select(t, s) {
    const n = s.find((o) => o.runId === t.runId);
    if ((n == null ? void 0 : n.status) === "running" || Vn(n) && !t.pinReleased) return t;
    const r = s.filter((o) => o.status === "running").sort(Es)[0];
    if (r) return { runId: r.runId, pinReleased: !1 };
    const i = [...s].sort(Es).at(-1);
    return n && (!i || Es(i, n) <= 0) ? t : { runId: (i == null ? void 0 : i.runId) ?? null, pinReleased: !1 };
  }
  followLive(t, s) {
    return this.select({ runId: t.runId, pinReleased: !0 }, s);
  }
  mode(t, s) {
    const n = s.find((r) => r.runId === t.runId);
    return n ? n.status === "running" ? "live" : Vn(n) && !t.pinReleased ? "pinned" : "completed" : "idle";
  }
}
function Ts(e) {
  return `${Math.max(0, Math.round(e / 1e3))}s`;
}
class Jl {
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
class zl {
  async getJSON(t) {
    const s = await fetch(t, { cache: "no-store" });
    if (!s.ok) throw new Error(`HTTP ${s.status} from ${t}`);
    return s.json();
  }
}
class Yl {
  set(t, s) {
    return window.setTimeout(t, s);
  }
  clear(t) {
    window.clearTimeout(t);
  }
}
class Xl {
  constructor() {
    X(this, "offset", 0);
  }
  align(t) {
    const s = Date.parse(t);
    Number.isNaN(s) || (this.offset = s - Date.now());
  }
  now() {
    return Date.now() + this.offset;
  }
}
class Zl {
  constructor(t = "adwDebugger.clearedThrough.v1") {
    X(this, "marks", {});
    this.key = t;
    try {
      this.marks = JSON.parse(localStorage.getItem(this.key) ?? "{}") ?? {};
    } catch {
      this.marks = {};
    }
  }
  get(t) {
    return this.marks[t] ?? 0;
  }
  set(t, s) {
    this.marks[t] = s;
    try {
      localStorage.setItem(this.key, JSON.stringify(this.marks));
    } catch {
    }
  }
}
class Ql {
  constructor(t) {
    this.node = t;
  }
  setVisible(t) {
    this.node && (this.node.style.display = t ? "" : "none");
  }
}
class ec {
  constructor(t, s, n) {
    X(this, "listeners", /* @__PURE__ */ new Set());
    X(this, "cursor", null);
    X(this, "handle", null);
    X(this, "running", !1);
    X(this, "inflight", !1);
    X(this, "failures", 0);
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
        const t = this.cursor === null ? this.options.url : `${this.options.url}?after=${this.cursor}`, s = await this.http.getJSON(t);
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
class tc {
  constructor() {
    X(this, "lastGood", { runId: "", columns: [], rows: [] });
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
const sc = { class: "adwdbg-log" }, nc = { class: "adwdbg-log-head" }, rc = { class: "adwdbg-log-label" }, ic = {
  key: 0,
  class: "adwdbg-log-empty"
}, oc = ["data-kind", "data-run"], lc = /* @__PURE__ */ Ge({
  __name: "LogPane",
  props: {
    lines: {},
    label: {},
    tall: { type: Boolean }
  },
  setup(e) {
    const t = e, s = Fs(null), n = Fs(!0);
    function r() {
      const i = s.value;
      i && (n.value = i.scrollHeight - i.scrollTop - i.clientHeight <= 8);
    }
    return Jt(() => t.lines.length, async () => {
      n.value && (await wr(), s.value && (s.value.scrollTop = s.value.scrollHeight));
    }, { immediate: !0 }), (i, o) => (F(), B("div", sc, [
      P("div", nc, [
        P("span", rc, j(i.label), 1),
        P("span", null, j(i.lines.length) + " line" + j(i.lines.length === 1 ? "" : "s") + j(n.value ? "" : " · paused (scroll to bottom to follow)"), 1)
      ]),
      P("div", {
        ref_key: "host",
        ref: s,
        class: lt(["adwdbg-log-lines", { "adwdbg-log-tall": i.tall }]),
        role: "log",
        onScroll: r
      }, [
        i.lines.length === 0 ? (F(), B("div", ic, "No ADW events to show.")) : Ce("", !0),
        (F(!0), B(Z, null, Qe(i.lines, (l) => (F(), B("div", {
          key: l.eventId,
          class: "adwdbg-log-line",
          "data-kind": l.kind,
          "data-run": l.runId
        }, j(l.text), 9, oc))), 128))
      ], 34)
    ]));
  }
}), St = 78, cc = 170, Ft = 40, an = 22, Rs = 11;
function Vs(e, t) {
  return (e + 0.5) / Math.max(1, t) * 100;
}
function ac(e) {
  return 100 / Math.max(1, e);
}
function rs(e) {
  return an + e * Ft + Ft * 0.62;
}
function si(e) {
  return an * 2 + Math.max(1, e) * Ft;
}
function uc(e, t, s) {
  const n = rs(e) - Rs, r = t === null ? si(s) - an / 2 : rs(Math.max(e, t)) + Rs;
  return { top: n, height: Math.max(Rs * 2, r - n) };
}
function fc(e, t) {
  return e === t ? "self" : e < t ? "right" : "left";
}
const dc = ["data-status"], hc = /* @__PURE__ */ Ge({
  __name: "ActivationBar",
  props: {
    from: {},
    to: {},
    rows: {},
    status: {}
  },
  setup(e) {
    const t = e, s = nt(() => uc(t.from, t.to, t.rows));
    return (n, r) => (F(), B("span", {
      class: lt(["sd-bar", { "sd-bar-open": n.to === null }]),
      "data-status": n.status,
      style: pe({ top: `${s.value.top}px`, height: `${s.value.height}px` })
    }, null, 14, dc));
  }
}), pc = ["data-lifeline"], gc = /* @__PURE__ */ Ge({
  __name: "Lifeline",
  props: {
    column: {},
    centre: {},
    rows: {}
  },
  setup(e) {
    return (t, s) => (F(), B("div", {
      class: "sd-lifeline-track",
      "data-lifeline": t.column.instanceId,
      style: pe({ left: `${t.centre}%` })
    }, [
      s[0] || (s[0] = P("span", { class: "sd-lifeline" }, null, -1)),
      t.column.activeFrom !== null && t.column.activeFrom !== void 0 ? (F(), et(hc, {
        key: 0,
        from: t.column.activeFrom,
        to: t.column.activeTo ?? null,
        rows: t.rows,
        status: t.column.status
      }, null, 8, ["from", "to", "rows", "status"])) : Ce("", !0)
    ], 12, pc));
  }
}), mc = ["data-kind", "data-row"], _c = ["title"], bc = { class: "sd-label-text" }, wc = /* @__PURE__ */ Ge({
  __name: "MessageArrow",
  props: {
    row: {},
    index: {},
    count: {}
  },
  setup(e) {
    const t = e, s = nt(() => fc(t.row.from, t.row.to)), n = nt(() => {
      const r = `${rs(t.index) - Ft * 0.62}px`, i = `${Ft}px`, o = Vs(t.row.from, t.count);
      if (s.value === "self") {
        const a = t.row.from === t.count - 1 ? 0.46 : 0.92;
        return { top: r, height: i, left: `${o}%`, width: `${ac(t.count) * a}%` };
      }
      const l = Vs(t.row.to, t.count);
      return { top: r, height: i, left: `${Math.min(o, l)}%`, width: `${Math.abs(l - o)}%` };
    });
    return (r, i) => (F(), B("div", {
      class: lt(["sd-message", [`sd-${s.value}`, { "sd-dashed": r.row.dashed }]]),
      "data-kind": r.row.kind,
      "data-row": r.index,
      style: pe(n.value)
    }, [
      P("div", {
        class: "sd-label",
        title: r.row.text
      }, [
        P("span", bc, j(r.row.text), 1)
      ], 8, _c),
      i[0] || (i[0] = P("div", { class: "sd-line" }, [
        P("span", { class: "sd-head" })
      ], -1))
    ], 14, mc));
  }
}), yc = ["data-status", "data-instance", "data-edge", "data-participant", "title", "aria-pressed"], vc = { class: "sd-name" }, xc = { class: "sd-status" }, Kn = /* @__PURE__ */ Ge({
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
    return (i, o) => (F(), B("button", {
      type: "button",
      class: lt(["sd-box", { "sd-selected": i.column.selected, "sd-runner": i.column.kind === "runner" }]),
      "data-status": i.column.status,
      "data-instance": i.column.instanceId,
      "data-edge": i.edge,
      "data-participant": i.column.kind ?? "phase",
      title: r(),
      "aria-pressed": i.column.selected,
      onClick: o[0] || (o[0] = (l) => n("select", i.column))
    }, [
      P("span", vc, [
        tt(j(i.column.name), 1),
        i.column.attempt && i.column.attempt > 1 ? (F(), B(Z, { key: 0 }, [
          tt(" · attempt " + j(i.column.attempt), 1)
        ], 64)) : Ce("", !0)
      ]),
      P("span", xc, [
        tt(j(i.column.statusLabel), 1),
        i.column.detail ? (F(), B(Z, { key: 0 }, [
          tt(" · " + j(i.column.detail), 1)
        ], 64)) : Ce("", !0)
      ])
    ], 10, yc));
  }
}), Sc = /* @__PURE__ */ Ge({
  __name: "TimeAxis",
  props: {
    rows: {}
  },
  setup(e) {
    return (t, s) => (F(), B("div", {
      class: "sd-axis",
      style: pe({ width: `${He(St)}px` }),
      "aria-hidden": "true"
    }, [
      (F(!0), B(Z, null, Qe(t.rows, (n, r) => (F(), B("span", {
        key: n.id,
        class: "sd-tick",
        style: pe({ top: `${He(rs)(r)}px` })
      }, j(n.elapsed), 5))), 128))
    ], 4));
  }
}), Ic = { class: "sd" }, Ac = { class: "sd-tools" }, Cc = { class: "sd-zoom-value" }, Ec = { class: "sd-scroll" }, Tc = /* @__PURE__ */ Ge({
  __name: "SequenceDiagram",
  props: {
    model: {}
  },
  emits: ["phase-click", "runner-click"],
  setup(e, { emit: t }) {
    const s = e, n = t, r = Fs(1), i = nt(() => Math.max(1, s.model.columns.length)), o = nt(() => s.model.rows.length), l = nt(() => `${St + i.value * cc}px`);
    function a(d) {
      d.kind === "runner" ? n("runner-click") : n("phase-click", d.instanceId);
    }
    return (d, f) => (F(), B("div", Ic, [
      P("div", Ac, [
        P("button", {
          type: "button",
          class: "sd-zoom",
          "aria-label": "Zoom out",
          onClick: f[0] || (f[0] = (p) => r.value = Math.max(0.4, r.value - 0.1))
        }, "-"),
        P("span", Cc, j(Math.round(r.value * 100)) + "%", 1),
        P("button", {
          type: "button",
          class: "sd-zoom",
          "aria-label": "Zoom in",
          onClick: f[1] || (f[1] = (p) => r.value = Math.min(2, r.value + 0.1))
        }, "+"),
        P("button", {
          type: "button",
          class: "sd-zoom",
          onClick: f[2] || (f[2] = (p) => r.value = 1)
        }, "Reset"),
        f[3] || (f[3] = P("span", { class: "sd-hint" }, "Click a phase box to filter the events below; click the ADW box for all events.", -1))
      ]),
      P("div", Ec, [
        P("div", {
          class: "sd-canvas",
          style: pe({ zoom: r.value, minWidth: l.value })
        }, [
          P("div", {
            class: "sd-titles sd-titles-top",
            style: pe({ marginLeft: `${He(St)}px` })
          }, [
            (F(!0), B(Z, null, Qe(d.model.columns, (p) => (F(), et(Kn, {
              key: p.instanceId,
              column: p,
              edge: "top",
              onSelect: a
            }, null, 8, ["column"]))), 128))
          ], 4),
          P("div", {
            class: "sd-body",
            style: pe({ height: `${He(si)(o.value)}px` })
          }, [
            be(Sc, {
              rows: d.model.rows
            }, null, 8, ["rows"]),
            P("div", {
              class: "sd-plot",
              style: pe({ left: `${He(St)}px` })
            }, [
              (F(!0), B(Z, null, Qe(d.model.columns, (p, m) => (F(), et(gc, {
                key: p.instanceId,
                column: p,
                centre: He(Vs)(m, i.value),
                rows: o.value
              }, null, 8, ["column", "centre", "rows"]))), 128)),
              (F(!0), B(Z, null, Qe(d.model.rows, (p, m) => (F(), et(wc, {
                key: p.id,
                row: p,
                index: m,
                count: i.value
              }, null, 8, ["row", "index", "count"]))), 128))
            ], 4)
          ], 4),
          P("div", {
            class: "sd-titles sd-titles-bottom",
            style: pe({ marginLeft: `${He(St)}px` })
          }, [
            (F(!0), B(Z, null, Qe(d.model.columns, (p) => (F(), et(Kn, {
              key: p.instanceId,
              column: p,
              edge: "bottom",
              onSelect: a
            }, null, 8, ["column"]))), 128))
          ], 4)
        ], 4)
      ])
    ]));
  }
}), Rc = {
  key: 0,
  class: "adwdbg",
  "aria-label": "Live ADW sequence debugger"
}, Mc = { class: "adwdbg-head" }, Pc = { "data-field": "adw" }, $c = { "data-field": "run" }, Oc = ["data-run-status"], Dc = ["data-mode"], Fc = {
  class: "adwdbg-legend",
  "aria-label": "Status colours"
}, kc = ["data-status"], Nc = {
  key: 0,
  class: "adwdbg-warn",
  "data-warning": "connection",
  role: "status"
}, Lc = {
  key: 1,
  class: "adwdbg-warn",
  "data-warning": "feed",
  role: "status"
}, Hc = {
  key: 2,
  class: "adwdbg-warn",
  "data-warning": "render",
  role: "alert"
}, jc = {
  key: 4,
  class: "adwdbg-idle",
  "data-field": "idle"
}, Bc = { class: "adwdbg-bar" }, Wc = ["disabled"], Uc = ["disabled", "title"], Vc = {
  key: 0,
  class: "adwdbg-note"
}, Kc = {
  class: "adwdbg-note",
  "data-field": "timing"
}, Gc = /* @__PURE__ */ Ge({
  __name: "DebuggerPanel",
  props: {
    controller: {}
  },
  setup(e) {
    const t = e, s = Bi(null), n = t.controller.subscribe((i) => {
      s.value = i;
    });
    Er(n), Rr((i) => (t.controller.reportRenderError(i instanceof Error ? i.message : String(i)), !1));
    const r = [
      ["waiting", "Waiting"],
      ["running", "Running"],
      ["stalled", "Stalled"],
      ["fail", "Fail"],
      ["pass", "Pass"]
    ];
    return (i, o) => s.value ? (F(), B("section", Rc, [
      P("header", Mc, [
        o[6] || (o[6] = P("strong", { class: "adwdbg-title" }, "ADW sequence", -1)),
        s.value.runId ? (F(), B(Z, { key: 0 }, [
          P("span", Pc, j(s.value.adwName), 1),
          P("span", $c, "run " + j(s.value.runId), 1),
          P("span", {
            class: "adwdbg-chip",
            "data-run-status": s.value.runStatus,
            "data-field": "status"
          }, j(s.value.runStatus), 9, Oc)
        ], 64)) : Ce("", !0),
        P("span", {
          class: "adwdbg-chip",
          "data-mode": s.value.mode,
          "data-field": "mode"
        }, j(s.value.modeLabel), 9, Dc),
        P("span", Fc, [
          (F(), B(Z, null, Qe(r, ([l, a]) => P("span", {
            key: l,
            class: "adwdbg-key",
            "data-status": l
          }, j(a), 9, kc)), 64)),
          o[5] || (o[5] = P("span", { class: "adwdbg-key adwdbg-key-selected" }, "Selected", -1))
        ])
      ]),
      s.value.connection.status === "disconnected" ? (F(), B("p", Nc, " Event feed disconnected (attempt " + j(s.value.connection.attempts) + "): " + j(s.value.connection.reason) + ". The diagram shows the last events received; this is a connection problem, not an ADW failure. ", 1)) : s.value.connection.status === "degraded" ? (F(), B("p", Lc, " The dashboard cannot read the ADW trace: " + j(s.value.connection.reason), 1)) : Ce("", !0),
      s.value.renderError ? (F(), B("p", Hc, " Diagram could not be redrawn (" + j(s.value.renderError) + "). Showing the last good diagram; the terminal is unaffected. ", 1)) : Ce("", !0),
      s.value.diagram.columns.length ? (F(), et(Tc, {
        key: 3,
        model: s.value.diagram,
        onPhaseClick: o[0] || (o[0] = (l) => t.controller.selectPhase(l)),
        onRunnerClick: o[1] || (o[1] = (l) => t.controller.allEvents())
      }, null, 8, ["model"])) : (F(), B("p", jc, j(s.value.runId ? "This run has not constructed a phase yet." : "No pilot ADW run has been recorded yet."), 1)),
      P("div", Bc, [
        P("button", {
          type: "button",
          class: "am-btn",
          "data-action": "follow-live",
          onClick: o[2] || (o[2] = (l) => t.controller.followLive())
        }, "Follow live"),
        P("button", {
          type: "button",
          class: "am-btn",
          "data-action": "all-events",
          disabled: !s.value.phaseSelected,
          onClick: o[3] || (o[3] = (l) => t.controller.allEvents())
        }, "All events", 8, Wc),
        P("button", {
          type: "button",
          class: "am-btn",
          "data-action": "clear-run",
          disabled: !!s.value.clearDisabledReason,
          title: s.value.clearDisabledReason,
          onClick: o[4] || (o[4] = (l) => t.controller.clearSelectedRun())
        }, j(s.value.clearLabel), 9, Uc),
        s.value.clearDisabledReason ? (F(), B("span", Vc, j(s.value.clearDisabledReason), 1)) : Ce("", !0),
        P("span", Kc, [
          tt(" stall timeout " + j(s.value.stallTimeoutSeconds) + "s", 1),
          s.value.lastDelayMs !== null ? (F(), B(Z, { key: 0 }, [
            tt(" · last event shown " + j(s.value.lastDelayMs) + " ms after it was recorded", 1)
          ], 64)) : Ce("", !0)
        ])
      ]),
      be(lc, {
        lines: s.value.lines,
        label: `ADW events — ${s.value.filterLabel}`,
        tall: s.value.phaseSelected
      }, null, 8, ["lines", "label", "tall"])
    ])) : Ce("", !0);
  }
});
function qc(e = document) {
  const t = e.getElementById("terminal"), s = e.getElementById("terminal-stream"), n = (t == null ? void 0 : t.querySelector(".terminal-toolbar")) ?? s;
  if (!t || !s || !n || e.getElementById("adw-debugger-root"))
    return null;
  const r = e.createElement("div");
  r.id = "adw-debugger-root", n.parentNode.insertBefore(r, n);
  const i = new Yl(), o = new Gl({
    source: new ec(new zl(), i, {
      url: "/api/adw-debugger/feed",
      activeMs: 500,
      idleMs: 5e3,
      retryStepMs: 1e3,
      retryMaxMs: 5e3,
      isActive: () => t.classList.contains("active") && e.visibilityState !== "hidden"
    }),
    selection: new ql(),
    stall: new Jl(),
    renderer: new tc(),
    cleared: new Zl(),
    legacy: new Ql(s),
    clock: new Xl(),
    timer: i
  }), l = xl(Gc, { controller: o });
  l.mount(r), o.start();
  const a = () => o.wake(), d = new MutationObserver(a);
  return d.observe(t, { attributes: !0, attributeFilter: ["class"] }), e.addEventListener("visibilitychange", a), {
    controller: o,
    unmount() {
      d.disconnect(), e.removeEventListener("visibilitychange", a), o.dispose(), l.unmount(), r.remove();
    }
  };
}
window.adwDebugger = qc();
export {
  qc as mountAdwDebugger
};
