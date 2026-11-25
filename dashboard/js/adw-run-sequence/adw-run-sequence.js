var oi = Object.defineProperty;
var li = (e, t, s) => t in e ? oi(e, t, { enumerable: !0, configurable: !0, writable: !0, value: s }) : e[t] = s;
var Q = (e, t, s) => li(e, typeof t != "symbol" ? t + "" : t, s);
/**
* @vue/shared v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
/*! #__NO_SIDE_EFFECTS__ */
// @__NO_SIDE_EFFECTS__
function Vs(e) {
  const t = /* @__PURE__ */ Object.create(null);
  for (const s of e.split(",")) t[s] = 1;
  return (s) => s in t;
}
const U = {}, ut = [], Te = () => {
}, ci = () => !1, os = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && // uppercase letter
(e.charCodeAt(2) > 122 || e.charCodeAt(2) < 97), Ks = (e) => e.startsWith("onUpdate:"), re = Object.assign, qs = (e, t) => {
  const s = e.indexOf(t);
  s > -1 && e.splice(s, 1);
}, ai = Object.prototype.hasOwnProperty, L = (e, t) => ai.call(e, t), R = Array.isArray, ft = (e) => ls(e) === "[object Map]", qn = (e) => ls(e) === "[object Set]", P = (e) => typeof e == "function", X = (e) => typeof e == "string", Ue = (e) => typeof e == "symbol", G = (e) => e !== null && typeof e == "object", Gn = (e) => (G(e) || P(e)) && P(e.then) && P(e.catch), Jn = Object.prototype.toString, ls = (e) => Jn.call(e), ui = (e) => ls(e).slice(8, -1), zn = (e) => ls(e) === "[object Object]", Gs = (e) => X(e) && e !== "NaN" && e[0] !== "-" && "" + parseInt(e, 10) === e, At = /* @__PURE__ */ Vs(
  // the leading comma is intentional so empty string "" is also included
  ",key,ref,ref_for,ref_key,onVnodeBeforeMount,onVnodeMounted,onVnodeBeforeUpdate,onVnodeUpdated,onVnodeBeforeUnmount,onVnodeUnmounted"
), cs = (e) => {
  const t = /* @__PURE__ */ Object.create(null);
  return (s) => t[s] || (t[s] = e(s));
}, fi = /-(\w)/g, We = cs(
  (e) => e.replace(fi, (t, s) => s ? s.toUpperCase() : "")
), di = /\B([A-Z])/g, ot = cs(
  (e) => e.replace(di, "-$1").toLowerCase()
), Yn = cs((e) => e.charAt(0).toUpperCase() + e.slice(1)), _s = cs(
  (e) => e ? `on${Yn(e)}` : ""
), Be = (e, t) => !Object.is(e, t), bs = (e, ...t) => {
  for (let s = 0; s < e.length; s++)
    e[s](...t);
}, Xn = (e, t, s, n = !1) => {
  Object.defineProperty(e, t, {
    configurable: !0,
    enumerable: !1,
    writable: n,
    value: s
  });
}, hi = (e) => {
  const t = parseFloat(e);
  return isNaN(t) ? e : t;
};
let gn;
const as = () => gn || (gn = typeof globalThis < "u" ? globalThis : typeof self < "u" ? self : typeof window < "u" ? window : typeof global < "u" ? global : {});
function pe(e) {
  if (R(e)) {
    const t = {};
    for (let s = 0; s < e.length; s++) {
      const n = e[s], r = X(n) ? _i(n) : pe(n);
      if (r)
        for (const i in r)
          t[i] = r[i];
    }
    return t;
  } else if (X(e) || G(e))
    return e;
}
const pi = /;(?![^(]*\))/g, gi = /:([^]+)/, mi = /\/\*[^]*?\*\//g;
function _i(e) {
  const t = {};
  return e.replace(mi, "").split(pi).forEach((s) => {
    if (s) {
      const n = s.split(gi);
      n.length > 1 && (t[n[0].trim()] = n[1].trim());
    }
  }), t;
}
function Ve(e) {
  let t = "";
  if (X(e))
    t = e;
  else if (R(e))
    for (let s = 0; s < e.length; s++) {
      const n = Ve(e[s]);
      n && (t += n + " ");
    }
  else if (G(e))
    for (const s in e)
      e[s] && (t += s + " ");
  return t.trim();
}
const bi = "itemscope,allowfullscreen,formnovalidate,ismap,nomodule,novalidate,readonly", wi = /* @__PURE__ */ Vs(bi);
function Zn(e) {
  return !!e || e === "";
}
const Qn = (e) => !!(e && e.__v_isRef === !0), Y = (e) => X(e) ? e : e == null ? "" : R(e) || G(e) && (e.toString === Jn || !P(e.toString)) ? Qn(e) ? Y(e.value) : JSON.stringify(e, er, 2) : String(e), er = (e, t) => Qn(t) ? er(e, t.value) : ft(t) ? {
  [`Map(${t.size})`]: [...t.entries()].reduce(
    (s, [n, r], i) => (s[ws(n, i) + " =>"] = r, s),
    {}
  )
} : qn(t) ? {
  [`Set(${t.size})`]: [...t.values()].map((s) => ws(s))
} : Ue(t) ? ws(t) : G(t) && !R(t) && !zn(t) ? String(t) : t, ws = (e, t = "") => {
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
class yi {
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
function vi() {
  return he;
}
let W;
const ys = /* @__PURE__ */ new WeakSet();
class tr {
  constructor(t) {
    this.fn = t, this.deps = void 0, this.depsTail = void 0, this.flags = 5, this.next = void 0, this.cleanup = void 0, this.scheduler = void 0, he && he.active && he.effects.push(this);
  }
  pause() {
    this.flags |= 64;
  }
  resume() {
    this.flags & 64 && (this.flags &= -65, ys.has(this) && (ys.delete(this), this.trigger()));
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
    const t = W, s = _e;
    W = this, _e = !0;
    try {
      return this.fn();
    } finally {
      ir(this), W = t, _e = s, this.flags &= -3;
    }
  }
  stop() {
    if (this.flags & 1) {
      for (let t = this.deps; t; t = t.nextDep)
        Ys(t);
      this.deps = this.depsTail = void 0, mn(this), this.onStop && this.onStop(), this.flags &= -2;
    }
  }
  trigger() {
    this.flags & 64 ? ys.add(this) : this.scheduler ? this.scheduler() : this.runIfDirty();
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
let sr = 0, Ct, $t;
function nr(e, t = !1) {
  if (e.flags |= 8, t) {
    e.next = $t, $t = e;
    return;
  }
  e.next = Ct, Ct = e;
}
function Js() {
  sr++;
}
function zs() {
  if (--sr > 0)
    return;
  if ($t) {
    let t = $t;
    for ($t = void 0; t; ) {
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
function rr(e) {
  for (let t = e.deps; t; t = t.nextDep)
    t.version = -1, t.prevActiveLink = t.dep.activeLink, t.dep.activeLink = t;
}
function ir(e) {
  let t, s = e.depsTail, n = s;
  for (; n; ) {
    const r = n.prevDep;
    n.version === -1 ? (n === s && (s = r), Ys(n), xi(n)) : t = n, n.dep.activeLink = n.prevActiveLink, n.prevActiveLink = void 0, n = r;
  }
  e.deps = t, e.depsTail = s;
}
function Rs(e) {
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
  if (e.flags |= 2, t.version > 0 && !e.isSSR && e.deps && !Rs(e)) {
    e.flags &= -3;
    return;
  }
  const s = W, n = _e;
  W = e, _e = !0;
  try {
    rr(e);
    const r = e.fn(e._value);
    (t.version === 0 || Be(r, e._value)) && (e._value = r, t.version++);
  } catch (r) {
    throw t.version++, r;
  } finally {
    W = s, _e = n, ir(e), e.flags &= -3;
  }
}
function Ys(e, t = !1) {
  const { dep: s, prevSub: n, nextSub: r } = e;
  if (n && (n.nextSub = r, e.prevSub = void 0), r && (r.prevSub = n, e.nextSub = void 0), s.subs === e && (s.subs = n, !n && s.computed)) {
    s.computed.flags &= -5;
    for (let i = s.computed.deps; i; i = i.nextDep)
      Ys(i, !0);
  }
  !t && !--s.sc && s.map && s.map.delete(s.key);
}
function xi(e) {
  const { prevDep: t, nextDep: s } = e;
  t && (t.nextDep = s, e.prevDep = void 0), s && (s.prevDep = t, e.nextDep = void 0);
}
let _e = !0;
const lr = [];
function Ke() {
  lr.push(_e), _e = !1;
}
function qe() {
  const e = lr.pop();
  _e = e === void 0 ? !0 : e;
}
function mn(e) {
  const { cleanup: t } = e;
  if (e.cleanup = void 0, t) {
    const s = W;
    W = void 0;
    try {
      t();
    } finally {
      W = s;
    }
  }
}
let Mt = 0;
class Si {
  constructor(t, s) {
    this.sub = t, this.dep = s, this.version = s.version, this.nextDep = this.prevDep = this.nextSub = this.prevSub = this.prevActiveLink = void 0;
  }
}
class Xs {
  constructor(t) {
    this.computed = t, this.version = 0, this.activeLink = void 0, this.subs = void 0, this.map = void 0, this.key = void 0, this.sc = 0;
  }
  track(t) {
    if (!W || !_e || W === this.computed)
      return;
    let s = this.activeLink;
    if (s === void 0 || s.sub !== W)
      s = this.activeLink = new Si(W, this), W.deps ? (s.prevDep = W.depsTail, W.depsTail.nextDep = s, W.depsTail = s) : W.deps = W.depsTail = s, cr(s);
    else if (s.version === -1 && (s.version = this.version, s.nextDep)) {
      const n = s.nextDep;
      n.prevDep = s.prevDep, s.prevDep && (s.prevDep.nextDep = n), s.prevDep = W.depsTail, s.nextDep = void 0, W.depsTail.nextDep = s, W.depsTail = s, W.deps === s && (W.deps = n);
    }
    return s;
  }
  trigger(t) {
    this.version++, Mt++, this.notify(t);
  }
  notify(t) {
    Js();
    try {
      for (let s = this.subs; s; s = s.prevSub)
        s.sub.notify() && s.sub.dep.notify();
    } finally {
      zs();
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
const Ms = /* @__PURE__ */ new WeakMap(), st = Symbol(
  ""
), Ps = Symbol(
  ""
), Pt = Symbol(
  ""
);
function te(e, t, s) {
  if (_e && W) {
    let n = Ms.get(e);
    n || Ms.set(e, n = /* @__PURE__ */ new Map());
    let r = n.get(s);
    r || (n.set(s, r = new Xs()), r.map = n, r.key = s), r.track();
  }
}
function Pe(e, t, s, n, r, i) {
  const o = Ms.get(e);
  if (!o) {
    Mt++;
    return;
  }
  const l = (a) => {
    a && a.trigger();
  };
  if (Js(), t === "clear")
    o.forEach(l);
  else {
    const a = R(e), f = a && Gs(s);
    if (a && s === "length") {
      const d = Number(n);
      o.forEach((p, m) => {
        (m === "length" || m === Pt || !Ue(m) && m >= d) && l(p);
      });
    } else
      switch ((s !== void 0 || o.has(void 0)) && l(o.get(s)), f && l(o.get(Pt)), t) {
        case "add":
          a ? f && l(o.get("length")) : (l(o.get(st)), ft(e) && l(o.get(Ps)));
          break;
        case "delete":
          a || (l(o.get(st)), ft(e) && l(o.get(Ps)));
          break;
        case "set":
          ft(e) && l(o.get(st));
          break;
      }
  }
  zs();
}
function lt(e) {
  const t = N(e);
  return t === e ? t : (te(t, "iterate", Pt), me(e) ? t : t.map(se));
}
function us(e) {
  return te(e = N(e), "iterate", Pt), e;
}
const Ii = {
  __proto__: null,
  [Symbol.iterator]() {
    return vs(this, Symbol.iterator, se);
  },
  concat(...e) {
    return lt(this).concat(
      ...e.map((t) => R(t) ? lt(t) : t)
    );
  },
  entries() {
    return vs(this, "entries", (e) => (e[1] = se(e[1]), e));
  },
  every(e, t) {
    return Re(this, "every", e, t, void 0, arguments);
  },
  filter(e, t) {
    return Re(this, "filter", e, t, (s) => s.map(se), arguments);
  },
  find(e, t) {
    return Re(this, "find", e, t, se, arguments);
  },
  findIndex(e, t) {
    return Re(this, "findIndex", e, t, void 0, arguments);
  },
  findLast(e, t) {
    return Re(this, "findLast", e, t, se, arguments);
  },
  findLastIndex(e, t) {
    return Re(this, "findLastIndex", e, t, void 0, arguments);
  },
  // flat, flatMap could benefit from ARRAY_ITERATE but are not straight-forward to implement
  forEach(e, t) {
    return Re(this, "forEach", e, t, void 0, arguments);
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
    return Re(this, "map", e, t, void 0, arguments);
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
    return Re(this, "some", e, t, void 0, arguments);
  },
  splice(...e) {
    return yt(this, "splice", e);
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
    return yt(this, "unshift", e);
  },
  values() {
    return vs(this, "values", se);
  }
};
function vs(e, t, s) {
  const n = us(e), r = n[t]();
  return n !== e && !me(e) && (r._next = r.next, r.next = () => {
    const i = r._next();
    return i.value && (i.value = s(i.value)), i;
  }), r;
}
const Ai = Array.prototype;
function Re(e, t, s, n, r, i) {
  const o = us(e), l = o !== e && !me(e), a = o[t];
  if (a !== Ai[t]) {
    const p = a.apply(e, i);
    return l ? se(p) : p;
  }
  let f = s;
  o !== e && (l ? f = function(p, m) {
    return s.call(this, se(p), m, e);
  } : s.length > 2 && (f = function(p, m) {
    return s.call(this, p, m, e);
  }));
  const d = a.call(o, f, n);
  return l && r ? r(d) : d;
}
function _n(e, t, s, n) {
  const r = us(e);
  let i = s;
  return r !== e && (me(e) ? s.length > 3 && (i = function(o, l, a) {
    return s.call(this, o, l, a, e);
  }) : i = function(o, l, a) {
    return s.call(this, o, se(l), a, e);
  }), r[t](i, ...n);
}
function xs(e, t, s) {
  const n = N(e);
  te(n, "iterate", Pt);
  const r = n[t](...s);
  return (r === -1 || r === !1) && tn(s[0]) ? (s[0] = N(s[0]), n[t](...s)) : r;
}
function yt(e, t, s = []) {
  Ke(), Js();
  const n = N(e)[t].apply(e, s);
  return zs(), qe(), n;
}
const Ci = /* @__PURE__ */ Vs("__proto__,__v_isRef,__isVue"), ar = new Set(
  /* @__PURE__ */ Object.getOwnPropertyNames(Symbol).filter((e) => e !== "arguments" && e !== "caller").map((e) => Symbol[e]).filter(Ue)
);
function $i(e) {
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
      return n === (r ? i ? Li : pr : i ? hr : dr).get(t) || // receiver is not the reactive proxy, but has the same prototype
      // this means the receiver is a user proxy of the reactive proxy
      Object.getPrototypeOf(t) === Object.getPrototypeOf(n) ? t : void 0;
    const o = R(t);
    if (!r) {
      let a;
      if (o && (a = Ii[s]))
        return a;
      if (s === "hasOwnProperty")
        return $i;
    }
    const l = Reflect.get(
      t,
      s,
      // if this is a proxy wrapping a ref, return methods using the raw ref
      // as receiver so that we don't have to call `toRaw` on the ref in all
      // its class methods
      ne(t) ? t : n
    );
    return (Ue(s) ? ar.has(s) : Ci(s)) || (r || te(t, "get", s), i) ? l : ne(l) ? o && Gs(s) ? l : l.value : G(l) ? r ? gr(l) : Qs(l) : l;
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
    const o = R(t) && Gs(s) ? Number(s) < t.length : L(t, s), l = Reflect.set(
      t,
      s,
      n,
      ne(t) ? t : r
    );
    return t === N(r) && (o ? Be(n, i) && Pe(t, "set", s, n) : Pe(t, "add", s, n)), l;
  }
  deleteProperty(t, s) {
    const n = L(t, s);
    t[s];
    const r = Reflect.deleteProperty(t, s);
    return r && n && Pe(t, "delete", s, void 0), r;
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
class Ti extends ur {
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
const Ei = /* @__PURE__ */ new fr(), Ri = /* @__PURE__ */ new Ti(), Mi = /* @__PURE__ */ new fr(!0);
const Os = (e) => e, Vt = (e) => Reflect.getPrototypeOf(e);
function Pi(e, t, s) {
  return function(...n) {
    const r = this.__v_raw, i = N(r), o = ft(i), l = e === "entries" || e === Symbol.iterator && o, a = e === "keys" && o, f = r[e](...n), d = s ? Os : t ? Ds : se;
    return !t && te(
      i,
      "iterate",
      a ? Ps : st
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
function Oi(e, t) {
  const s = {
    get(r) {
      const i = this.__v_raw, o = N(i), l = N(r);
      e || (Be(r, l) && te(o, "get", r), te(o, "get", l));
      const { has: a } = Vt(o), f = t ? Os : e ? Ds : se;
      if (a.call(o, r))
        return f(i.get(r));
      if (a.call(o, l))
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
      const o = this, l = o.__v_raw, a = N(l), f = t ? Os : e ? Ds : se;
      return !e && te(a, "iterate", st), l.forEach((d, p) => r.call(i, f(d), f(p), o));
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
        return Vt(i).has.call(i, r) || (i.add(r), Pe(i, "add", r, r)), this;
      },
      set(r, i) {
        !t && !me(i) && !rt(i) && (i = N(i));
        const o = N(this), { has: l, get: a } = Vt(o);
        let f = l.call(o, r);
        f || (r = N(r), f = l.call(o, r));
        const d = a.call(o, r);
        return o.set(r, i), f ? Be(i, d) && Pe(o, "set", r, i) : Pe(o, "add", r, i), this;
      },
      delete(r) {
        const i = N(this), { has: o, get: l } = Vt(i);
        let a = o.call(i, r);
        a || (r = N(r), a = o.call(i, r)), l && l.call(i, r);
        const f = i.delete(r);
        return a && Pe(i, "delete", r, void 0), f;
      },
      clear() {
        const r = N(this), i = r.size !== 0, o = r.clear();
        return i && Pe(
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
function Zs(e, t) {
  const s = Oi(e, t);
  return (n, r, i) => r === "__v_isReactive" ? !e : r === "__v_isReadonly" ? e : r === "__v_raw" ? n : Reflect.get(
    L(s, r) && r in n ? s : n,
    r,
    i
  );
}
const Di = {
  get: /* @__PURE__ */ Zs(!1, !1)
}, Fi = {
  get: /* @__PURE__ */ Zs(!1, !0)
}, Ni = {
  get: /* @__PURE__ */ Zs(!0, !1)
};
const dr = /* @__PURE__ */ new WeakMap(), hr = /* @__PURE__ */ new WeakMap(), pr = /* @__PURE__ */ new WeakMap(), Li = /* @__PURE__ */ new WeakMap();
function ki(e) {
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
function Hi(e) {
  return e.__v_skip || !Object.isExtensible(e) ? 0 : ki(ui(e));
}
function Qs(e) {
  return rt(e) ? e : en(
    e,
    !1,
    Ei,
    Di,
    dr
  );
}
function ji(e) {
  return en(
    e,
    !1,
    Mi,
    Fi,
    hr
  );
}
function gr(e) {
  return en(
    e,
    !0,
    Ri,
    Ni,
    pr
  );
}
function en(e, t, s, n, r) {
  if (!G(e) || e.__v_raw && !(t && e.__v_isReactive))
    return e;
  const i = r.get(e);
  if (i)
    return i;
  const o = Hi(e);
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
function tn(e) {
  return e ? !!e.__v_raw : !1;
}
function N(e) {
  const t = e && e.__v_raw;
  return t ? N(t) : e;
}
function Bi(e) {
  return !L(e, "__v_skip") && Object.isExtensible(e) && Xn(e, "__v_skip", !0), e;
}
const se = (e) => G(e) ? Qs(e) : e, Ds = (e) => G(e) ? gr(e) : e;
function ne(e) {
  return e ? e.__v_isRef === !0 : !1;
}
function et(e) {
  return mr(e, !1);
}
function Wi(e) {
  return mr(e, !0);
}
function mr(e, t) {
  return ne(e) ? e : new Ui(e, t);
}
class Ui {
  constructor(t, s) {
    this.dep = new Xs(), this.__v_isRef = !0, this.__v_isShallow = !1, this._rawValue = s ? t : N(t), this._value = s ? t : se(t), this.__v_isShallow = s;
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
const Vi = {
  get: (e, t, s) => t === "__v_raw" ? e : He(Reflect.get(e, t, s)),
  set: (e, t, s, n) => {
    const r = e[t];
    return ne(r) && !ne(s) ? (r.value = s, !0) : Reflect.set(e, t, s, n);
  }
};
function _r(e) {
  return dt(e) ? e : new Proxy(e, Vi);
}
class Ki {
  constructor(t, s, n) {
    this.fn = t, this.setter = s, this._value = void 0, this.dep = new Xs(this), this.__v_isRef = !0, this.deps = void 0, this.depsTail = void 0, this.flags = 16, this.globalVersion = Mt - 1, this.next = void 0, this.effect = this, this.__v_isReadonly = !s, this.isSSR = n;
  }
  /**
   * @internal
   */
  notify() {
    if (this.flags |= 16, !(this.flags & 8) && // avoid infinite self recursion
    W !== this)
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
function qi(e, t, s = !1) {
  let n, r;
  return P(e) ? n = e : (n = e.get, r = e.set), new Ki(n, r, s);
}
const qt = {}, Zt = /* @__PURE__ */ new WeakMap();
let Qe;
function Gi(e, t = !1, s = Qe) {
  if (s) {
    let n = Zt.get(s);
    n || Zt.set(s, n = []), n.push(e);
  }
}
function Ji(e, t, s = U) {
  const { immediate: n, deep: r, once: i, scheduler: o, augmentJob: l, call: a } = s, f = (T) => r ? T : me(T) || r === !1 || r === 0 ? je(T, 1) : je(T);
  let d, p, m, x, M = !1, C = !1;
  if (ne(e) ? (p = () => e.value, M = me(e)) : dt(e) ? (p = () => f(e), M = !0) : R(e) ? (C = !0, M = e.some((T) => dt(T) || me(T)), p = () => e.map((T) => {
    if (ne(T))
      return T.value;
    if (dt(T))
      return f(T);
    if (P(T))
      return a ? a(T, 2) : T();
  })) : P(e) ? t ? p = a ? () => a(e, 2) : e : p = () => {
    if (m) {
      Ke();
      try {
        m();
      } finally {
        qe();
      }
    }
    const T = Qe;
    Qe = d;
    try {
      return a ? a(e, 3, [x]) : e(x);
    } finally {
      Qe = T;
    }
  } : p = Te, t && r) {
    const T = p, Z = r === !0 ? 1 / 0 : r;
    p = () => je(T(), Z);
  }
  const K = vi(), D = () => {
    d.stop(), K && K.active && qs(K.effects, d);
  };
  if (i && t) {
    const T = t;
    t = (...Z) => {
      T(...Z), D();
    };
  }
  let J = C ? new Array(e.length).fill(qt) : qt;
  const z = (T) => {
    if (!(!(d.flags & 1) || !d.dirty && !T))
      if (t) {
        const Z = d.run();
        if (r || M || (C ? Z.some((Fe, we) => Be(Fe, J[we])) : Be(Z, J))) {
          m && m();
          const Fe = Qe;
          Qe = d;
          try {
            const we = [
              Z,
              // pass undefined as the old value when it's changed for the first time
              J === qt ? void 0 : C && J[0] === qt ? [] : J,
              x
            ];
            a ? a(t, 3, we) : (
              // @ts-expect-error
              t(...we)
            ), J = Z;
          } finally {
            Qe = Fe;
          }
        }
      } else
        d.run();
  };
  return l && l(z), d = new tr(p), d.scheduler = o ? () => o(z, !1) : z, x = (T) => Gi(T, !1, d), m = d.onStop = () => {
    const T = Zt.get(d);
    if (T) {
      if (a)
        a(T, 4);
      else
        for (const Z of T) Z();
      Zt.delete(d);
    }
  }, t ? n ? z(!0) : J = d.run() : o ? o(z.bind(null, !0), !0) : d.run(), D.pause = d.pause.bind(d), D.resume = d.resume.bind(d), D.stop = D, D;
}
function je(e, t = 1 / 0, s) {
  if (t <= 0 || !G(e) || e.__v_skip || (s = s || /* @__PURE__ */ new Set(), s.has(e)))
    return e;
  if (s.add(e), t--, ne(e))
    je(e.value, t, s);
  else if (R(e))
    for (let n = 0; n < e.length; n++)
      je(e[n], t, s);
  else if (qn(e) || ft(e))
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
function Lt(e, t, s, n) {
  try {
    return n ? e(...n) : e();
  } catch (r) {
    fs(r, t, s);
  }
}
function Ee(e, t, s, n) {
  if (P(e)) {
    const r = Lt(e, t, s, n);
    return r && Gn(r) && r.catch((i) => {
      fs(i, t, s);
    }), r;
  }
  if (R(e)) {
    const r = [];
    for (let i = 0; i < e.length; i++)
      r.push(Ee(e[i], t, s, n));
    return r;
  }
}
function fs(e, t, s, n = !0) {
  const r = t ? t.vnode : null, { errorHandler: i, throwUnhandledErrorInProduction: o } = t && t.appContext.config || U;
  if (t) {
    let l = t.parent;
    const a = t.proxy, f = `https://vuejs.org/error-reference/#runtime-${s}`;
    for (; l; ) {
      const d = l.ec;
      if (d) {
        for (let p = 0; p < d.length; p++)
          if (d[p](e, a, f) === !1)
            return;
      }
      l = l.parent;
    }
    if (i) {
      Ke(), Lt(i, null, 10, [
        e,
        a,
        f
      ]), qe();
      return;
    }
  }
  zi(e, s, r, n, o);
}
function zi(e, t, s, n = !0, r = !1) {
  if (r)
    throw e;
  console.error(e);
}
const le = [];
let Ae = -1;
const ht = [];
let Le = null, ct = 0;
const br = /* @__PURE__ */ Promise.resolve();
let Qt = null;
function wr(e) {
  const t = Qt || br;
  return e ? t.then(this ? e.bind(this) : e) : t;
}
function Yi(e) {
  let t = Ae + 1, s = le.length;
  for (; t < s; ) {
    const n = t + s >>> 1, r = le[n], i = Ot(r);
    i < e || i === e && r.flags & 2 ? t = n + 1 : s = n;
  }
  return t;
}
function sn(e) {
  if (!(e.flags & 1)) {
    const t = Ot(e), s = le[le.length - 1];
    !s || // fast path when the job id is larger than the tail
    !(e.flags & 2) && t >= Ot(s) ? le.push(e) : le.splice(Yi(t), 0, e), e.flags |= 1, yr();
  }
}
function yr() {
  Qt || (Qt = br.then(xr));
}
function Xi(e) {
  R(e) ? ht.push(...e) : Le && e.id === -1 ? Le.splice(ct + 1, 0, e) : e.flags & 1 || (ht.push(e), e.flags |= 1), yr();
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
      (s, n) => Ot(s) - Ot(n)
    );
    if (ht.length = 0, Le) {
      Le.push(...t);
      return;
    }
    for (Le = t, ct = 0; ct < Le.length; ct++) {
      const s = Le[ct];
      s.flags & 4 && (s.flags &= -2), s.flags & 8 || s(), s.flags &= -2;
    }
    Le = null, ct = 0;
  }
}
const Ot = (e) => e.id == null ? e.flags & 2 ? -1 : 1 / 0 : e.id;
function xr(e) {
  try {
    for (Ae = 0; Ae < le.length; Ae++) {
      const t = le[Ae];
      t && !(t.flags & 8) && (t.flags & 4 && (t.flags &= -2), Lt(
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
    Ae = -1, le.length = 0, vr(), Qt = null, (le.length || ht.length) && xr();
  }
}
let $e = null, Sr = null;
function es(e) {
  const t = $e;
  return $e = e, Sr = e && e.type.__scopeId || null, t;
}
function Zi(e, t = $e, s) {
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
    let a = l.dir[n];
    a && (Ke(), Ee(a, s, 8, [
      e.el,
      l,
      e,
      t
    ]), qe());
  }
}
const Qi = Symbol("_vte"), eo = (e) => e.__isTeleport;
function nn(e, t) {
  e.shapeFlag & 6 && e.component ? (e.transition = t, nn(e.component.subTree, t)) : e.shapeFlag & 128 ? (e.ssContent.transition = t.clone(e.ssContent), e.ssFallback.transition = t.clone(e.ssFallback)) : e.transition = t;
}
/*! #__NO_SIDE_EFFECTS__ */
// @__NO_SIDE_EFFECTS__
function Ge(e, t) {
  return P(e) ? (
    // #8236: extend call and options.name access are considered side-effects
    // by Rollup, so we have to wrap it in a pure-annotated IIFE.
    re({ name: e.name }, t, { setup: e })
  ) : e;
}
function Ir(e) {
  e.ids = [e.ids[0] + e.ids[2]++ + "-", 0, 0];
}
function ts(e, t, s, n, r = !1) {
  if (R(e)) {
    e.forEach(
      (M, C) => ts(
        M,
        t && (R(t) ? t[C] : t),
        s,
        n,
        r
      )
    );
    return;
  }
  if (Tt(n) && !r) {
    n.shapeFlag & 512 && n.type.__asyncResolved && n.component.subTree.component && ts(e, t, s, n.component.subTree);
    return;
  }
  const i = n.shapeFlag & 4 ? cn(n.component) : n.el, o = r ? null : i, { i: l, r: a } = e, f = t && t.r, d = l.refs === U ? l.refs = {} : l.refs, p = l.setupState, m = N(p), x = p === U ? () => !1 : (M) => L(m, M);
  if (f != null && f !== a && (X(f) ? (d[f] = null, x(f) && (p[f] = null)) : ne(f) && (f.value = null)), P(a))
    Lt(a, l, 12, [o, d]);
  else {
    const M = X(a), C = ne(a);
    if (M || C) {
      const K = () => {
        if (e.f) {
          const D = M ? x(a) ? p[a] : d[a] : a.value;
          r ? R(D) && qs(D, i) : R(D) ? D.includes(i) || D.push(i) : M ? (d[a] = [i], x(a) && (p[a] = d[a])) : (a.value = [i], e.k && (d[e.k] = a.value));
        } else M ? (d[a] = o, x(a) && (p[a] = o)) : C && (a.value = o, e.k && (d[e.k] = o));
      };
      o ? (K.id = -1, de(K, s)) : K();
    }
  }
}
as().requestIdleCallback;
as().cancelIdleCallback;
const Tt = (e) => !!e.type.__asyncLoader, Ar = (e) => e.type.__isKeepAlive;
function to(e, t) {
  Cr(e, "a", t);
}
function so(e, t) {
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
  if (ds(t, n, s), s) {
    let r = s.parent;
    for (; r && r.parent; )
      Ar(r.parent.vnode) && no(n, t, s, r), r = r.parent;
  }
}
function no(e, t, s, n) {
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
      const l = kt(s), a = Ee(t, s, e, o);
      return l(), qe(), a;
    });
    return n ? r.unshift(i) : r.push(i), i;
  }
}
const De = (e) => (t, s = ce) => {
  (!Ft || e === "sp") && ds(e, (...n) => t(...n), s);
}, ro = De("bm"), $r = De("m"), io = De(
  "bu"
), oo = De("u"), rn = De(
  "bum"
), Tr = De("um"), lo = De(
  "sp"
), co = De("rtg"), ao = De("rtc");
function Er(e, t = ce) {
  ds("ec", e, t);
}
const uo = Symbol.for("v-ndc");
function at(e, t, s, n) {
  let r;
  const i = s, o = R(e);
  if (o || X(e)) {
    const l = o && dt(e);
    let a = !1;
    l && (a = !me(e), e = us(e)), r = new Array(e.length);
    for (let f = 0, d = e.length; f < d; f++)
      r[f] = t(
        a ? se(e[f]) : e[f],
        f,
        void 0,
        i
      );
  } else if (typeof e == "number") {
    r = new Array(e);
    for (let l = 0; l < e; l++)
      r[l] = t(l + 1, l, void 0, i);
  } else if (G(e))
    if (e[Symbol.iterator])
      r = Array.from(
        e,
        (l, a) => t(l, a, void 0, i)
      );
    else {
      const l = Object.keys(e);
      r = new Array(l.length);
      for (let a = 0, f = l.length; a < f; a++) {
        const d = l[a];
        r[a] = t(e[d], d, a, i);
      }
    }
  else
    r = [];
  return r;
}
const Fs = (e) => e ? Xr(e) ? cn(e) : Fs(e.parent) : null, Et = (
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
    $parent: (e) => Fs(e.parent),
    $root: (e) => Fs(e.root),
    $host: (e) => e.ce,
    $emit: (e) => e.emit,
    $options: (e) => Mr(e),
    $forceUpdate: (e) => e.f || (e.f = () => {
      sn(e.update);
    }),
    $nextTick: (e) => e.n || (e.n = wr.bind(e.proxy)),
    $watch: (e) => Oo.bind(e)
  })
), Ss = (e, t) => e !== U && !e.__isScriptSetup && L(e, t), fo = {
  get({ _: e }, t) {
    if (t === "__v_skip")
      return !0;
    const { ctx: s, setupState: n, data: r, props: i, accessCache: o, type: l, appContext: a } = e;
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
        if (r !== U && L(r, t))
          return o[t] = 2, r[t];
        if (
          // only cache other properties when instance has declared (thus stable)
          // props
          (f = e.propsOptions[0]) && L(f, t)
        )
          return o[t] = 3, i[t];
        if (s !== U && L(s, t))
          return o[t] = 4, s[t];
        Ns && (o[t] = 0);
      }
    }
    const d = Et[t];
    let p, m;
    if (d)
      return t === "$attrs" && te(e.attrs, "get", ""), d(e);
    if (
      // css module (injected by vue-loader)
      (p = l.__cssModules) && (p = p[t])
    )
      return p;
    if (s !== U && L(s, t))
      return o[t] = 4, s[t];
    if (
      // global properties
      m = a.config.globalProperties, L(m, t)
    )
      return m[t];
  },
  set({ _: e }, t, s) {
    const { data: n, setupState: r, ctx: i } = e;
    return Ss(r, t) ? (r[t] = s, !0) : n !== U && L(n, t) ? (n[t] = s, !0) : L(e.props, t) || t[0] === "$" && t.slice(1) in e ? !1 : (i[t] = s, !0);
  },
  has({
    _: { data: e, setupState: t, accessCache: s, ctx: n, appContext: r, propsOptions: i }
  }, o) {
    let l;
    return !!s[o] || e !== U && L(e, o) || Ss(t, o) || (l = i[0]) && L(l, o) || L(n, o) || L(Et, o) || L(r.config.globalProperties, o);
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
  const t = Mr(e), s = e.proxy, n = e.ctx;
  Ns = !1, t.beforeCreate && yn(t.beforeCreate, e, "bc");
  const {
    // state
    data: r,
    computed: i,
    methods: o,
    watch: l,
    provide: a,
    inject: f,
    // lifecycle
    created: d,
    beforeMount: p,
    mounted: m,
    beforeUpdate: x,
    updated: M,
    activated: C,
    deactivated: K,
    beforeDestroy: D,
    beforeUnmount: J,
    destroyed: z,
    unmounted: T,
    render: Z,
    renderTracked: Fe,
    renderTriggered: we,
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
  if (f && po(f, n, null), o)
    for (const q in o) {
      const j = o[q];
      P(j) && (n[q] = j.bind(s));
    }
  if (r) {
    const q = r.call(s, s);
    G(q) && (e.data = Qs(q));
  }
  if (Ns = !0, i)
    for (const q in i) {
      const j = i[q], ze = P(j) ? j.bind(s, s) : P(j.get) ? j.get.bind(s, s) : Te, Wt = !P(j) && P(j.set) ? j.set.bind(s) : Te, Ye = nt({
        get: ze,
        set: Wt
      });
      Object.defineProperty(n, q, {
        enumerable: !0,
        configurable: !0,
        get: () => Ye.value,
        set: (ye) => Ye.value = ye
      });
    }
  if (l)
    for (const q in l)
      Rr(l[q], n, s, q);
  if (a) {
    const q = P(a) ? a.call(s) : a;
    Reflect.ownKeys(q).forEach((j) => {
      yo(j, q[j]);
    });
  }
  d && yn(d, e, "c");
  function ie(q, j) {
    R(j) ? j.forEach((ze) => q(ze.bind(s))) : j && q(j.bind(s));
  }
  if (ie(ro, p), ie($r, m), ie(io, x), ie(oo, M), ie(to, C), ie(so, K), ie(Er, Ne), ie(ao, Fe), ie(co, we), ie(rn, J), ie(Tr, T), ie(lo, Ht), R(Je))
    if (Je.length) {
      const q = e.exposed || (e.exposed = {});
      Je.forEach((j) => {
        Object.defineProperty(q, j, {
          get: () => s[j],
          set: (ze) => s[j] = ze
        });
      });
    } else e.exposed || (e.exposed = {});
  Z && e.render === Te && (e.render = Z), mt != null && (e.inheritAttrs = mt), jt && (e.components = jt), Bt && (e.directives = Bt), Ht && Ir(e);
}
function po(e, t, s = Te) {
  R(e) && (e = Ls(e));
  for (const n in e) {
    const r = e[n];
    let i;
    G(r) ? "default" in r ? i = Jt(
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
  Ee(
    R(e) ? e.map((n) => n.bind(t.proxy)) : e.bind(t.proxy),
    t,
    s
  );
}
function Rr(e, t, s, n) {
  let r = n.includes(".") ? Kr(s, n) : () => s[n];
  if (X(e)) {
    const i = t[e];
    P(i) && zt(r, i);
  } else if (P(e))
    zt(r, e.bind(s));
  else if (G(e))
    if (R(e))
      e.forEach((i) => Rr(i, t, s, n));
    else {
      const i = P(e.handler) ? e.handler.bind(s) : t[e.handler];
      P(i) && zt(r, i, e);
    }
}
function Mr(e) {
  const t = e.type, { mixins: s, extends: n } = t, {
    mixins: r,
    optionsCache: i,
    config: { optionMergeStrategies: o }
  } = e.appContext, l = i.get(t);
  let a;
  return l ? a = l : !r.length && !s && !n ? a = t : (a = {}, r.length && r.forEach(
    (f) => ss(a, f, o, !0)
  ), ss(a, t, o)), G(t) && i.set(t, a), a;
}
function ss(e, t, s, n = !1) {
  const { mixins: r, extends: i } = t;
  i && ss(e, i, s, !0), r && r.forEach(
    (o) => ss(e, o, s, !0)
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
      P(e) ? e.call(this, this) : e,
      P(t) ? t.call(this, this) : t
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
function Pr() {
  return {
    app: null,
    config: {
      isNativeTag: ci,
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
    P(n) || (n = re({}, n)), r != null && !G(r) && (r = null);
    const i = Pr(), o = /* @__PURE__ */ new WeakSet(), l = [];
    let a = !1;
    const f = i.app = {
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
      set config(d) {
      },
      use(d, ...p) {
        return o.has(d) || (d && P(d.install) ? (o.add(d), d.install(f, ...p)) : P(d) && (o.add(d), d(f, ...p))), f;
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
        if (!a) {
          const x = f._ceVNode || be(n, r);
          return x.appContext = i, m === !0 ? m = "svg" : m === !1 && (m = void 0), e(x, d, m), a = !0, f._container = d, d.__vue_app__ = f, cn(x.component);
        }
      },
      onUnmount(d) {
        l.push(d);
      },
      unmount() {
        a && (Ee(
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
function yo(e, t) {
  if (ce) {
    let s = ce.provides;
    const n = ce.parent && ce.parent.provides;
    n === s && (s = ce.provides = Object.create(n)), s[e] = t;
  }
}
function Jt(e, t, s = !1) {
  const n = ce || $e;
  if (n || pt) {
    const r = pt ? pt._context.provides : n ? n.parent == null ? n.vnode.appContext && n.vnode.appContext.provides : n.parent.provides : void 0;
    if (r && e in r)
      return r[e];
    if (arguments.length > 1)
      return s && P(t) ? t.call(n && n.proxy) : t;
  }
}
const Or = {}, Dr = () => Object.create(Or), Fr = (e) => Object.getPrototypeOf(e) === Or;
function vo(e, t, s, n = !1) {
  const r = {}, i = Dr();
  e.propsDefaults = /* @__PURE__ */ Object.create(null), Nr(e, t, r, i);
  for (const o in e.propsOptions[0])
    o in r || (r[o] = void 0);
  s ? e.props = n ? r : ji(r) : e.type.props ? e.props = r : e.props = i, e.attrs = i;
}
function xo(e, t, s, n) {
  const {
    props: r,
    attrs: i,
    vnode: { patchFlag: o }
  } = e, l = N(r), [a] = e.propsOptions;
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
        if (a)
          if (L(i, m))
            x !== i[m] && (i[m] = x, f = !0);
          else {
            const M = We(m);
            r[M] = ks(
              a,
              l,
              M,
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
    Nr(e, t, r, i) && (f = !0);
    let d;
    for (const p in l)
      (!t || // for camelCase
      !L(t, p) && // it's possible the original props was passed in as kebab-case
      // and converted to camelCase (#955)
      ((d = ot(p)) === p || !L(t, d))) && (a ? s && // for camelCase
      (s[p] !== void 0 || // for kebab-case
      s[d] !== void 0) && (r[p] = ks(
        a,
        l,
        p,
        void 0,
        e,
        !0
      )) : delete r[p]);
    if (i !== l)
      for (const p in i)
        (!t || !L(t, p)) && (delete i[p], f = !0);
  }
  f && Pe(e.attrs, "set", "");
}
function Nr(e, t, s, n) {
  const [r, i] = e.propsOptions;
  let o = !1, l;
  if (t)
    for (let a in t) {
      if (At(a))
        continue;
      const f = t[a];
      let d;
      r && L(r, d = We(a)) ? !i || !i.includes(d) ? s[d] = f : (l || (l = {}))[d] = f : hs(e.emitsOptions, a) || (!(a in n) || f !== n[a]) && (n[a] = f, o = !0);
    }
  if (i) {
    const a = N(s), f = l || U;
    for (let d = 0; d < i.length; d++) {
      const p = i[d];
      s[p] = ks(
        r,
        a,
        p,
        f[p],
        e,
        !L(f, p)
      );
    }
  }
  return o;
}
function ks(e, t, s, n, r, i) {
  const o = e[s];
  if (o != null) {
    const l = L(o, "default");
    if (l && n === void 0) {
      const a = o.default;
      if (o.type !== Function && !o.skipFactory && P(a)) {
        const { propsDefaults: f } = r;
        if (s in f)
          n = f[s];
        else {
          const d = kt(r);
          n = f[s] = a.call(
            null,
            t
          ), d();
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
function Lr(e, t, s = !1) {
  const n = s ? So : t.propsCache, r = n.get(e);
  if (r)
    return r;
  const i = e.props, o = {}, l = [];
  let a = !1;
  if (!P(e)) {
    const d = (p) => {
      a = !0;
      const [m, x] = Lr(p, t, !0);
      re(o, m), x && l.push(...x);
    };
    !s && t.mixins.length && t.mixins.forEach(d), e.extends && d(e.extends), e.mixins && e.mixins.forEach(d);
  }
  if (!i && !a)
    return G(e) && n.set(e, ut), ut;
  if (R(i))
    for (let d = 0; d < i.length; d++) {
      const p = We(i[d]);
      Sn(p) && (o[p] = U);
    }
  else if (i)
    for (const d in i) {
      const p = We(d);
      if (Sn(p)) {
        const m = i[d], x = o[p] = R(m) || P(m) ? { type: m } : re({}, m), M = x.type;
        let C = !1, K = !0;
        if (R(M))
          for (let D = 0; D < M.length; ++D) {
            const J = M[D], z = P(J) && J.name;
            if (z === "Boolean") {
              C = !0;
              break;
            } else z === "String" && (K = !1);
          }
        else
          C = P(M) && M.name === "Boolean";
        x[
          0
          /* shouldCast */
        ] = C, x[
          1
          /* shouldCastTrue */
        ] = K, (C || L(x, "default")) && l.push(p);
      }
    }
  const f = [o, l];
  return G(e) && n.set(e, f), f;
}
function Sn(e) {
  return e[0] !== "$" && !At(e);
}
const kr = (e) => e[0] === "_" || e === "$stable", on = (e) => R(e) ? e.map(Ce) : [Ce(e)], Io = (e, t, s) => {
  if (t._n)
    return t;
  const n = Zi((...r) => on(t(...r)), s);
  return n._c = !1, n;
}, Hr = (e, t, s) => {
  const n = e._ctx;
  for (const r in e) {
    if (kr(r)) continue;
    const i = e[r];
    if (P(i))
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
  let i = !0, o = U;
  if (n.shapeFlag & 32) {
    const l = t._;
    l ? s && l === 1 ? i = !1 : Br(r, t, s) : (i = !t.$stable, Hr(t, r)), o = t;
  } else t && (jr(e, t), o = { default: 1 });
  if (i)
    for (const l in r)
      !kr(l) && o[l] == null && delete r[l];
}, de = jo;
function $o(e) {
  return To(e);
}
function To(e, t) {
  const s = as();
  s.__VUE__ = !0;
  const {
    insert: n,
    remove: r,
    patchProp: i,
    createElement: o,
    createText: l,
    createComment: a,
    setText: f,
    setElementText: d,
    parentNode: p,
    nextSibling: m,
    setScopeId: x = Te,
    insertStaticContent: M
  } = e, C = (c, u, h, b = null, g = null, _ = null, S = void 0, v = null, y = !!u.dynamicChildren) => {
    if (c === u)
      return;
    c && !vt(c, u) && (b = Ut(c), ye(c, g, _, !0), c = null), u.patchFlag === -2 && (y = !1, u.dynamicChildren = null);
    const { type: w, ref: $, shapeFlag: I } = u;
    switch (w) {
      case ps:
        K(c, u, h, b);
        break;
      case it:
        D(c, u, h, b);
        break;
      case As:
        c == null && J(u, h, b, S);
        break;
      case ee:
        jt(
          c,
          u,
          h,
          b,
          g,
          _,
          S,
          v,
          y
        );
        break;
      default:
        I & 1 ? Z(
          c,
          u,
          h,
          b,
          g,
          _,
          S,
          v,
          y
        ) : I & 6 ? Bt(
          c,
          u,
          h,
          b,
          g,
          _,
          S,
          v,
          y
        ) : (I & 64 || I & 128) && w.process(
          c,
          u,
          h,
          b,
          g,
          _,
          S,
          v,
          y,
          bt
        );
    }
    $ != null && g && ts($, c && c.ref, _, u || c, !u);
  }, K = (c, u, h, b) => {
    if (c == null)
      n(
        u.el = l(u.children),
        h,
        b
      );
    else {
      const g = u.el = c.el;
      u.children !== c.children && f(g, u.children);
    }
  }, D = (c, u, h, b) => {
    c == null ? n(
      u.el = a(u.children || ""),
      h,
      b
    ) : u.el = c.el;
  }, J = (c, u, h, b) => {
    [c.el, c.anchor] = M(
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
  }, T = ({ el: c, anchor: u }) => {
    let h;
    for (; c && c !== u; )
      h = m(c), r(c), c = h;
    r(u);
  }, Z = (c, u, h, b, g, _, S, v, y) => {
    u.type === "svg" ? S = "svg" : u.type === "math" && (S = "mathml"), c == null ? Fe(
      u,
      h,
      b,
      g,
      _,
      S,
      v,
      y
    ) : Ht(
      c,
      u,
      g,
      _,
      S,
      v,
      y
    );
  }, Fe = (c, u, h, b, g, _, S, v) => {
    let y, w;
    const { props: $, shapeFlag: I, transition: A, dirs: E } = c;
    if (y = c.el = o(
      c.type,
      _,
      $ && $.is,
      $
    ), I & 8 ? d(y, c.children) : I & 16 && Ne(
      c.children,
      y,
      null,
      b,
      g,
      Is(c, _),
      S,
      v
    ), E && Xe(c, null, b, "created"), we(y, c, c.scopeId, S, b), $) {
      for (const B in $)
        B !== "value" && !At(B) && i(y, B, null, $[B], _, b);
      "value" in $ && i(y, "value", null, $.value, _), (w = $.onVnodeBeforeMount) && Ie(w, b, c);
    }
    E && Xe(c, null, b, "beforeMount");
    const O = Eo(g, A);
    O && A.beforeEnter(y), n(y, u, h), ((w = $ && $.onVnodeMounted) || O || E) && de(() => {
      w && Ie(w, b, c), O && A.enter(y), E && Xe(c, null, b, "mounted");
    }, g);
  }, we = (c, u, h, b, g) => {
    if (h && x(c, h), b)
      for (let _ = 0; _ < b.length; _++)
        x(c, b[_]);
    if (g) {
      let _ = g.subTree;
      if (u === _ || Gr(_.type) && (_.ssContent === u || _.ssFallback === u)) {
        const S = g.vnode;
        we(
          c,
          S,
          S.scopeId,
          S.slotScopeIds,
          g.parent
        );
      }
    }
  }, Ne = (c, u, h, b, g, _, S, v, y = 0) => {
    for (let w = y; w < c.length; w++) {
      const $ = c[w] = v ? ke(c[w]) : Ce(c[w]);
      C(
        null,
        $,
        u,
        h,
        b,
        g,
        _,
        S,
        v
      );
    }
  }, Ht = (c, u, h, b, g, _, S) => {
    const v = u.el = c.el;
    let { patchFlag: y, dynamicChildren: w, dirs: $ } = u;
    y |= c.patchFlag & 16;
    const I = c.props || U, A = u.props || U;
    let E;
    if (h && Ze(h, !1), (E = A.onVnodeBeforeUpdate) && Ie(E, h, u, c), $ && Xe(u, c, h, "beforeUpdate"), h && Ze(h, !0), (I.innerHTML && A.innerHTML == null || I.textContent && A.textContent == null) && d(v, ""), w ? Je(
      c.dynamicChildren,
      w,
      v,
      h,
      b,
      Is(u, g),
      _
    ) : S || j(
      c,
      u,
      v,
      null,
      h,
      b,
      Is(u, g),
      _,
      !1
    ), y > 0) {
      if (y & 16)
        mt(v, I, A, h, g);
      else if (y & 2 && I.class !== A.class && i(v, "class", null, A.class, g), y & 4 && i(v, "style", I.style, A.style, g), y & 8) {
        const O = u.dynamicProps;
        for (let B = 0; B < O.length; B++) {
          const H = O[B], ue = I[H], ae = A[H];
          (ae !== ue || H === "value") && i(v, H, ue, ae, g, h);
        }
      }
      y & 1 && c.children !== u.children && d(v, u.children);
    } else !S && w == null && mt(v, I, A, h, g);
    ((E = A.onVnodeUpdated) || $) && de(() => {
      E && Ie(E, h, u, c), $ && Xe(u, c, h, "updated");
    }, b);
  }, Je = (c, u, h, b, g, _, S) => {
    for (let v = 0; v < u.length; v++) {
      const y = c[v], w = u[v], $ = (
        // oldVNode may be an errored async setup() component inside Suspense
        // which will not have a mounted element
        y.el && // - In the case of a Fragment, we need to provide the actual parent
        // of the Fragment itself so it can move its children.
        (y.type === ee || // - In the case of different nodes, there is going to be a replacement
        // which also requires the correct parent container
        !vt(y, w) || // - In the case of a component, it could contain anything.
        y.shapeFlag & 70) ? p(y.el) : (
          // In other cases, the parent container is not actually used so we
          // just pass the block element here to avoid a DOM parentNode call.
          h
        )
      );
      C(
        y,
        w,
        $,
        null,
        b,
        g,
        _,
        S,
        !0
      );
    }
  }, mt = (c, u, h, b, g) => {
    if (u !== h) {
      if (u !== U)
        for (const _ in u)
          !At(_) && !(_ in h) && i(
            c,
            _,
            u[_],
            null,
            g,
            b
          );
      for (const _ in h) {
        if (At(_)) continue;
        const S = h[_], v = u[_];
        S !== v && _ !== "value" && i(c, _, v, S, g, b);
      }
      "value" in h && i(c, "value", u.value, h.value, g);
    }
  }, jt = (c, u, h, b, g, _, S, v, y) => {
    const w = u.el = c ? c.el : l(""), $ = u.anchor = c ? c.anchor : l("");
    let { patchFlag: I, dynamicChildren: A, slotScopeIds: E } = u;
    E && (v = v ? v.concat(E) : E), c == null ? (n(w, h, b), n($, h, b), Ne(
      // #10007
      // such fragment like `<></>` will be compiled into
      // a fragment which doesn't have a children.
      // In this case fallback to an empty array
      u.children || [],
      h,
      $,
      g,
      _,
      S,
      v,
      y
    )) : I > 0 && I & 64 && A && // #2715 the previous fragment could've been a BAILed one as a result
    // of renderSlot() with no valid children
    c.dynamicChildren ? (Je(
      c.dynamicChildren,
      A,
      h,
      g,
      _,
      S,
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
    )) : j(
      c,
      u,
      h,
      $,
      g,
      _,
      S,
      v,
      y
    );
  }, Bt = (c, u, h, b, g, _, S, v, y) => {
    u.slotScopeIds = v, c == null ? u.shapeFlag & 512 ? g.ctx.activate(
      u,
      h,
      b,
      S,
      y
    ) : gs(
      u,
      h,
      b,
      g,
      _,
      S,
      y
    ) : un(c, u, y);
  }, gs = (c, u, h, b, g, _, S) => {
    const v = c.component = Go(
      c,
      b,
      g
    );
    if (Ar(c) && (v.ctx.renderer = bt), Jo(v, !1, S), v.asyncDep) {
      if (g && g.registerDep(v, ie, S), !c.el) {
        const y = v.subTree = be(it);
        D(null, y, u, h);
      }
    } else
      ie(
        v,
        c,
        u,
        h,
        g,
        _,
        S
      );
  }, un = (c, u, h) => {
    const b = u.component = c.component;
    if (ko(c, u, h))
      if (b.asyncDep && !b.asyncResolved) {
        q(b, u, h);
        return;
      } else
        b.next = u, b.update();
    else
      u.el = c.el, b.vnode = u;
  }, ie = (c, u, h, b, g, _, S) => {
    const v = () => {
      if (c.isMounted) {
        let { next: I, bu: A, u: E, parent: O, vnode: B } = c;
        {
          const xe = Ur(c);
          if (xe) {
            I && (I.el = B.el, q(c, I, S)), xe.asyncDep.then(() => {
              c.isUnmounted || v();
            });
            return;
          }
        }
        let H = I, ue;
        Ze(c, !1), I ? (I.el = B.el, q(c, I, S)) : I = B, A && bs(A), (ue = I.props && I.props.onVnodeBeforeUpdate) && Ie(ue, O, I, B), Ze(c, !0);
        const ae = An(c), ve = c.subTree;
        c.subTree = ae, C(
          ve,
          ae,
          // parent may have changed if it's in a teleport
          p(ve.el),
          // anchor may have changed if it's in a fragment
          Ut(ve),
          c,
          g,
          _
        ), I.el = ae.el, H === null && Ho(c, ae.el), E && de(E, g), (ue = I.props && I.props.onVnodeUpdated) && de(
          () => Ie(ue, O, I, B),
          g
        );
      } else {
        let I;
        const { el: A, props: E } = u, { bm: O, m: B, parent: H, root: ue, type: ae } = c, ve = Tt(u);
        Ze(c, !1), O && bs(O), !ve && (I = E && E.onVnodeBeforeMount) && Ie(I, H, u), Ze(c, !0);
        {
          ue.ce && ue.ce._injectChildStyle(ae);
          const xe = c.subTree = An(c);
          C(
            null,
            xe,
            h,
            b,
            c,
            g,
            _
          ), u.el = xe.el;
        }
        if (B && de(B, g), !ve && (I = E && E.onVnodeMounted)) {
          const xe = u;
          de(
            () => Ie(I, H, xe),
            g
          );
        }
        (u.shapeFlag & 256 || H && Tt(H.vnode) && H.vnode.shapeFlag & 256) && c.a && de(c.a, g), c.isMounted = !0, u = h = b = null;
      }
    };
    c.scope.on();
    const y = c.effect = new tr(v);
    c.scope.off();
    const w = c.update = y.run.bind(y), $ = c.job = y.runIfDirty.bind(y);
    $.i = c, $.id = c.uid, y.scheduler = () => sn($), Ze(c, !0), w();
  }, q = (c, u, h) => {
    u.component = c;
    const b = c.vnode.props;
    c.vnode = u, c.next = null, xo(c, u.props, b, h), Co(c, u.children, h), Ke(), bn(c), qe();
  }, j = (c, u, h, b, g, _, S, v, y = !1) => {
    const w = c && c.children, $ = c ? c.shapeFlag : 0, I = u.children, { patchFlag: A, shapeFlag: E } = u;
    if (A > 0) {
      if (A & 128) {
        Wt(
          w,
          I,
          h,
          b,
          g,
          _,
          S,
          v,
          y
        );
        return;
      } else if (A & 256) {
        ze(
          w,
          I,
          h,
          b,
          g,
          _,
          S,
          v,
          y
        );
        return;
      }
    }
    E & 8 ? ($ & 16 && _t(w, g, _), I !== w && d(h, I)) : $ & 16 ? E & 16 ? Wt(
      w,
      I,
      h,
      b,
      g,
      _,
      S,
      v,
      y
    ) : _t(w, g, _, !0) : ($ & 8 && d(h, ""), E & 16 && Ne(
      I,
      h,
      b,
      g,
      _,
      S,
      v,
      y
    ));
  }, ze = (c, u, h, b, g, _, S, v, y) => {
    c = c || ut, u = u || ut;
    const w = c.length, $ = u.length, I = Math.min(w, $);
    let A;
    for (A = 0; A < I; A++) {
      const E = u[A] = y ? ke(u[A]) : Ce(u[A]);
      C(
        c[A],
        E,
        h,
        null,
        g,
        _,
        S,
        v,
        y
      );
    }
    w > $ ? _t(
      c,
      g,
      _,
      !0,
      !1,
      I
    ) : Ne(
      u,
      h,
      b,
      g,
      _,
      S,
      v,
      y,
      I
    );
  }, Wt = (c, u, h, b, g, _, S, v, y) => {
    let w = 0;
    const $ = u.length;
    let I = c.length - 1, A = $ - 1;
    for (; w <= I && w <= A; ) {
      const E = c[w], O = u[w] = y ? ke(u[w]) : Ce(u[w]);
      if (vt(E, O))
        C(
          E,
          O,
          h,
          null,
          g,
          _,
          S,
          v,
          y
        );
      else
        break;
      w++;
    }
    for (; w <= I && w <= A; ) {
      const E = c[I], O = u[A] = y ? ke(u[A]) : Ce(u[A]);
      if (vt(E, O))
        C(
          E,
          O,
          h,
          null,
          g,
          _,
          S,
          v,
          y
        );
      else
        break;
      I--, A--;
    }
    if (w > I) {
      if (w <= A) {
        const E = A + 1, O = E < $ ? u[E].el : b;
        for (; w <= A; )
          C(
            null,
            u[w] = y ? ke(u[w]) : Ce(u[w]),
            h,
            O,
            g,
            _,
            S,
            v,
            y
          ), w++;
      }
    } else if (w > A)
      for (; w <= I; )
        ye(c[w], g, _, !0), w++;
    else {
      const E = w, O = w, B = /* @__PURE__ */ new Map();
      for (w = O; w <= A; w++) {
        const fe = u[w] = y ? ke(u[w]) : Ce(u[w]);
        fe.key != null && B.set(fe.key, w);
      }
      let H, ue = 0;
      const ae = A - O + 1;
      let ve = !1, xe = 0;
      const wt = new Array(ae);
      for (w = 0; w < ae; w++) wt[w] = 0;
      for (w = E; w <= I; w++) {
        const fe = c[w];
        if (ue >= ae) {
          ye(fe, g, _, !0);
          continue;
        }
        let Se;
        if (fe.key != null)
          Se = B.get(fe.key);
        else
          for (H = O; H <= A; H++)
            if (wt[H - O] === 0 && vt(fe, u[H])) {
              Se = H;
              break;
            }
        Se === void 0 ? ye(fe, g, _, !0) : (wt[Se - O] = w + 1, Se >= xe ? xe = Se : ve = !0, C(
          fe,
          u[Se],
          h,
          null,
          g,
          _,
          S,
          v,
          y
        ), ue++);
      }
      const hn = ve ? Ro(wt) : ut;
      for (H = hn.length - 1, w = ae - 1; w >= 0; w--) {
        const fe = O + w, Se = u[fe], pn = fe + 1 < $ ? u[fe + 1].el : b;
        wt[w] === 0 ? C(
          null,
          Se,
          h,
          pn,
          g,
          _,
          S,
          v,
          y
        ) : ve && (H < 0 || w !== hn[H] ? Ye(Se, h, pn, 2) : H--);
      }
    }
  }, Ye = (c, u, h, b, g = null) => {
    const { el: _, type: S, transition: v, children: y, shapeFlag: w } = c;
    if (w & 6) {
      Ye(c.component.subTree, u, h, b);
      return;
    }
    if (w & 128) {
      c.suspense.move(u, h, b);
      return;
    }
    if (w & 64) {
      S.move(c, u, h, bt);
      return;
    }
    if (S === ee) {
      n(_, u, h);
      for (let I = 0; I < y.length; I++)
        Ye(y[I], u, h, b);
      n(c.anchor, u, h);
      return;
    }
    if (S === As) {
      z(c, u, h);
      return;
    }
    if (b !== 2 && w & 1 && v)
      if (b === 0)
        v.beforeEnter(_), n(_, u, h), de(() => v.enter(_), g);
      else {
        const { leave: I, delayLeave: A, afterLeave: E } = v, O = () => n(_, u, h), B = () => {
          I(_, () => {
            O(), E && E();
          });
        };
        A ? A(_, O, B) : B();
      }
    else
      n(_, u, h);
  }, ye = (c, u, h, b = !1, g = !1) => {
    const {
      type: _,
      props: S,
      ref: v,
      children: y,
      dynamicChildren: w,
      shapeFlag: $,
      patchFlag: I,
      dirs: A,
      cacheIndex: E
    } = c;
    if (I === -2 && (g = !1), v != null && ts(v, null, h, c, !0), E != null && (u.renderCache[E] = void 0), $ & 256) {
      u.ctx.deactivate(c);
      return;
    }
    const O = $ & 1 && A, B = !Tt(c);
    let H;
    if (B && (H = S && S.onVnodeBeforeUnmount) && Ie(H, u, c), $ & 6)
      ii(c.component, h, b);
    else {
      if ($ & 128) {
        c.suspense.unmount(h, b);
        return;
      }
      O && Xe(c, null, u, "beforeUnmount"), $ & 64 ? c.type.remove(
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
      (_ !== ee || I > 0 && I & 64) ? _t(
        w,
        u,
        h,
        !1,
        !0
      ) : (_ === ee && I & 384 || !g && $ & 16) && _t(y, u, h), b && fn(c);
    }
    (B && (H = S && S.onVnodeUnmounted) || O) && de(() => {
      H && Ie(H, u, c), O && Xe(c, null, u, "unmounted");
    }, h);
  }, fn = (c) => {
    const { type: u, el: h, anchor: b, transition: g } = c;
    if (u === ee) {
      ri(h, b);
      return;
    }
    if (u === As) {
      T(c);
      return;
    }
    const _ = () => {
      r(h), g && !g.persisted && g.afterLeave && g.afterLeave();
    };
    if (c.shapeFlag & 1 && g && !g.persisted) {
      const { leave: S, delayLeave: v } = g, y = () => S(h, _);
      v ? v(c.el, _, y) : y();
    } else
      _();
  }, ri = (c, u) => {
    let h;
    for (; c !== u; )
      h = m(c), r(c), c = h;
    r(u);
  }, ii = (c, u, h) => {
    const { bum: b, scope: g, job: _, subTree: S, um: v, m: y, a: w } = c;
    In(y), In(w), b && bs(b), g.stop(), _ && (_.flags |= 8, ye(S, c, u, h)), v && de(v, u), de(() => {
      c.isUnmounted = !0;
    }, u), u && u.pendingBranch && !u.isUnmounted && c.asyncDep && !c.asyncResolved && c.suspenseId === u.pendingId && (u.deps--, u.deps === 0 && u.resolve());
  }, _t = (c, u, h, b = !1, g = !1, _ = 0) => {
    for (let S = _; S < c.length; S++)
      ye(c[S], u, h, b, g);
  }, Ut = (c) => {
    if (c.shapeFlag & 6)
      return Ut(c.component.subTree);
    if (c.shapeFlag & 128)
      return c.suspense.next();
    const u = m(c.anchor || c.el), h = u && u[Qi];
    return h ? m(h) : u;
  };
  let ms = !1;
  const dn = (c, u, h) => {
    c == null ? u._vnode && ye(u._vnode, null, null, !0) : C(
      u._vnode || null,
      c,
      u,
      null,
      null,
      null,
      h
    ), u._vnode = c, ms || (ms = !0, bn(), vr(), ms = !1);
  }, bt = {
    p: C,
    um: ye,
    m: Ye,
    r: fn,
    mt: gs,
    mc: Ne,
    pc: j,
    pbc: Je,
    n: Ut,
    o: e
  };
  return {
    render: dn,
    hydrate: void 0,
    createApp: wo(dn)
  };
}
function Is({ type: e, props: t }, s) {
  return s === "svg" && e === "foreignObject" || s === "mathml" && e === "annotation-xml" && t && t.encoding && t.encoding.includes("html") ? void 0 : s;
}
function Ze({ effect: e, job: t }, s) {
  s ? (e.flags |= 32, t.flags |= 4) : (e.flags &= -33, t.flags &= -5);
}
function Eo(e, t) {
  return (!e || e && !e.pendingBranch) && t && !t.persisted;
}
function Wr(e, t, s = !1) {
  const n = e.children, r = t.children;
  if (R(n) && R(r))
    for (let i = 0; i < n.length; i++) {
      const o = n[i];
      let l = r[i];
      l.shapeFlag & 1 && !l.dynamicChildren && ((l.patchFlag <= 0 || l.patchFlag === 32) && (l = r[i] = ke(r[i]), l.el = o.el), !s && l.patchFlag !== -2 && Wr(o, l)), l.type === ps && (l.el = o.el);
    }
}
function Ro(e) {
  const t = e.slice(), s = [0];
  let n, r, i, o, l;
  const a = e.length;
  for (n = 0; n < a; n++) {
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
const Mo = Symbol.for("v-scx"), Po = () => Jt(Mo);
function zt(e, t, s) {
  return Vr(e, t, s);
}
function Vr(e, t, s = U) {
  const { immediate: n, deep: r, flush: i, once: o } = s, l = re({}, s), a = t && n || !t && i !== "post";
  let f;
  if (Ft) {
    if (i === "sync") {
      const x = Po();
      f = x.__watcherHandles || (x.__watcherHandles = []);
    } else if (!a) {
      const x = () => {
      };
      return x.stop = Te, x.resume = Te, x.pause = Te, x;
    }
  }
  const d = ce;
  l.call = (x, M, C) => Ee(x, d, M, C);
  let p = !1;
  i === "post" ? l.scheduler = (x) => {
    de(x, d && d.suspense);
  } : i !== "sync" && (p = !0, l.scheduler = (x, M) => {
    M ? x() : sn(x);
  }), l.augmentJob = (x) => {
    t && (x.flags |= 4), p && (x.flags |= 2, d && (x.id = d.uid, x.i = d));
  };
  const m = Ji(e, t, l);
  return Ft && (f ? f.push(m) : a && m()), m;
}
function Oo(e, t, s) {
  const n = this.proxy, r = X(e) ? e.includes(".") ? Kr(n, e) : () => n[e] : e.bind(n, n);
  let i;
  P(t) ? i = t : (i = t.handler, s = t);
  const o = kt(this), l = Vr(r, i.bind(n), s);
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
  const n = e.vnode.props || U;
  let r = s;
  const i = t.startsWith("update:"), o = i && Do(n, t.slice(7));
  o && (o.trim && (r = s.map((d) => X(d) ? d.trim() : d)), o.number && (r = s.map(hi)));
  let l, a = n[l = _s(t)] || // also try camelCase event handler (#2249)
  n[l = _s(We(t))];
  !a && i && (a = n[l = _s(ot(t))]), a && Ee(
    a,
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
    e.emitted[l] = !0, Ee(
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
  if (!P(e)) {
    const a = (f) => {
      const d = qr(f, t, !0);
      d && (l = !0, re(o, d));
    };
    !s && t.mixins.length && t.mixins.forEach(a), e.extends && a(e.extends), e.mixins && e.mixins.forEach(a);
  }
  return !i && !l ? (G(e) && n.set(e, null), null) : (R(i) ? i.forEach((a) => o[a] = null) : re(o, i), G(e) && n.set(e, o), o);
}
function hs(e, t) {
  return !e || !os(t) ? !1 : (t = t.slice(2).replace(/Once$/, ""), L(e, t[0].toLowerCase() + t.slice(1)) || L(e, ot(t)) || L(e, t));
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
    render: f,
    renderCache: d,
    props: p,
    data: m,
    setupState: x,
    ctx: M,
    inheritAttrs: C
  } = e, K = es(e);
  let D, J;
  try {
    if (s.shapeFlag & 4) {
      const T = r || n, Z = T;
      D = Ce(
        f.call(
          Z,
          T,
          d,
          p,
          x,
          m,
          M
        )
      ), J = l;
    } else {
      const T = t;
      D = Ce(
        T.length > 1 ? T(
          p,
          { attrs: l, slots: o, emit: a }
        ) : T(
          p,
          null
        )
      ), J = t.props ? l : No(l);
    }
  } catch (T) {
    Rt.length = 0, fs(T, e, 1), D = be(it);
  }
  let z = D;
  if (J && C !== !1) {
    const T = Object.keys(J), { shapeFlag: Z } = z;
    T.length && Z & 7 && (i && T.some(Ks) && (J = Lo(
      J,
      i
    )), z = gt(z, J, !1, !0));
  }
  return s.dirs && (z = gt(z, null, !1, !0), z.dirs = z.dirs ? z.dirs.concat(s.dirs) : s.dirs), s.transition && nn(z, s.transition), D = z, es(K), D;
}
const No = (e) => {
  let t;
  for (const s in e)
    (s === "class" || s === "style" || os(s)) && ((t || (t = {}))[s] = e[s]);
  return t;
}, Lo = (e, t) => {
  const s = {};
  for (const n in e)
    (!Ks(n) || !(n.slice(9) in t)) && (s[n] = e[n]);
  return s;
};
function ko(e, t, s) {
  const { props: n, children: r, component: i } = e, { props: o, children: l, patchFlag: a } = t, f = i.emitsOptions;
  if (t.dirs || t.transition)
    return !0;
  if (s && a >= 0) {
    if (a & 1024)
      return !0;
    if (a & 16)
      return n ? Cn(n, o, f) : !!o;
    if (a & 8) {
      const d = t.dynamicProps;
      for (let p = 0; p < d.length; p++) {
        const m = d[p];
        if (o[m] !== n[m] && !hs(f, m))
          return !0;
      }
    }
  } else
    return (r || l) && (!l || !l.$stable) ? !0 : n === o ? !1 : n ? o ? Cn(n, o, f) : !0 : !!o;
  return !1;
}
function Cn(e, t, s) {
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
function Ho({ vnode: e, parent: t }, s) {
  for (; t; ) {
    const n = t.subTree;
    if (n.suspense && n.suspense.activeBranch === e && (n.el = e.el), n === e)
      (e = t.vnode).el = s, t = t.parent;
    else
      break;
  }
}
const Gr = (e) => e.__isSuspense;
function jo(e, t) {
  t && t.pendingBranch ? R(e) ? t.effects.push(...e) : t.effects.push(e) : Xi(e);
}
const ee = Symbol.for("v-fgt"), ps = Symbol.for("v-txt"), it = Symbol.for("v-cmt"), As = Symbol.for("v-stc"), Rt = [];
let ge = null;
function F(e = !1) {
  Rt.push(ge = e ? null : []);
}
function Bo() {
  Rt.pop(), ge = Rt[Rt.length - 1] || null;
}
let Dt = 1;
function $n(e, t = !1) {
  Dt += e, e < 0 && ge && t && (ge.hasOnce = !0);
}
function Jr(e) {
  return e.dynamicChildren = Dt > 0 ? ge || ut : null, Bo(), Dt > 0 && ge && ge.push(e), e;
}
function V(e, t, s, n, r, i) {
  return Jr(
    k(
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
const Yr = ({ key: e }) => e ?? null, Yt = ({
  ref: e,
  ref_key: t,
  ref_for: s
}) => (typeof e == "number" && (e = "" + e), e != null ? X(e) || ne(e) || P(e) ? { i: $e, r: e, k: t, f: !!s } : e : null);
function k(e, t = null, s = null, n = 0, r = null, i = e === ee ? 0 : 1, o = !1, l = !1) {
  const a = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e,
    props: t,
    key: t && Yr(t),
    ref: t && Yt(t),
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
    ctx: $e
  };
  return l ? (ln(a, s), i & 128 && e.normalize(a)) : s && (a.shapeFlag |= X(s) ? 8 : 16), Dt > 0 && // avoid a block node from tracking itself
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
    return s && ln(l, s), Dt > 0 && !i && ge && (l.shapeFlag & 6 ? ge[ge.indexOf(e)] = l : ge.push(l)), l.patchFlag = -2, l;
  }
  if (Zo(e) && (e = e.__vccOpts), t) {
    t = Uo(t);
    let { class: l, style: a } = t;
    l && !X(l) && (t.class = Ve(l)), G(a) && (tn(a) && !R(a) && (a = re({}, a)), t.style = pe(a));
  }
  const o = X(e) ? 1 : Gr(e) ? 128 : eo(e) ? 64 : G(e) ? 4 : P(e) ? 2 : 0;
  return k(
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
  return e ? tn(e) || Fr(e) ? re({}, e) : e : null;
}
function gt(e, t, s = !1, n = !1) {
  const { props: r, ref: i, patchFlag: o, children: l, transition: a } = e, f = t ? Vo(r || {}, t) : r, d = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e.type,
    props: f,
    key: f && Yr(f),
    ref: t && t.ref ? (
      // #2078 in the case of <component :is="vnode" ref="extra"/>
      // if the vnode itself already has a ref, cloneVNode will need to merge
      // the refs so the single vnode can be set on multiple refs
      s && i ? R(i) ? i.concat(Yt(t)) : [i, Yt(t)] : Yt(t)
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
  return a && n && nn(
    d,
    a.clone(d)
  ), d;
}
function St(e = " ", t = 0) {
  return be(ps, null, e, t);
}
function Oe(e = "", t = !1) {
  return t ? (F(), tt(it, null, e)) : be(it, null, e);
}
function Ce(e) {
  return e == null || typeof e == "boolean" ? be(it) : R(e) ? be(
    ee,
    null,
    // #3666, avoid reference pollution when reusing vnode
    e.slice()
  ) : zr(e) ? ke(e) : be(ps, null, String(e));
}
function ke(e) {
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
      !r && !Fr(t) ? t._ctx = $e : r === 3 && $e && ($e.slots._ === 1 ? t._ = 1 : (t._ = 2, e.patchFlag |= 1024));
    }
  else P(t) ? (t = { default: t, _ctx: $e }, s = 32) : (t = String(t), n & 64 ? (s = 16, t = [St(t)]) : s = 8);
  e.children = t, e.shapeFlag |= s;
}
function Vo(...e) {
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
        o && i !== o && !(R(i) && i.includes(o)) && (t[r] = i ? [].concat(i, o) : o);
      } else r !== "" && (t[r] = n[r]);
  }
  return t;
}
function Ie(e, t, s, n = null) {
  Ee(e, t, 7, [
    s,
    n
  ]);
}
const Ko = Pr();
let qo = 0;
function Go(e, t, s) {
  const n = e.type, r = (t ? t.appContext : e.appContext) || Ko, i = {
    uid: qo++,
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
    scope: new yi(
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
    propsDefaults: U,
    // inheritAttrs
    inheritAttrs: n.inheritAttrs,
    // state
    ctx: U,
    data: U,
    props: U,
    attrs: U,
    slots: U,
    refs: U,
    setupState: U,
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
let ce = null, ns, Hs;
{
  const e = as(), t = (s, n) => {
    let r;
    return (r = e[s]) || (r = e[s] = []), r.push(n), (i) => {
      r.length > 1 ? r.forEach((o) => o(i)) : r[0](i);
    };
  };
  ns = t(
    "__VUE_INSTANCE_SETTERS__",
    (s) => ce = s
  ), Hs = t(
    "__VUE_SSR_SETTERS__",
    (s) => Ft = s
  );
}
const kt = (e) => {
  const t = ce;
  return ns(e), e.scope.on(), () => {
    e.scope.off(), ns(t);
  };
}, Tn = () => {
  ce && ce.scope.off(), ns(null);
};
function Xr(e) {
  return e.vnode.shapeFlag & 4;
}
let Ft = !1;
function Jo(e, t = !1, s = !1) {
  t && Hs(t);
  const { props: n, children: r } = e.vnode, i = Xr(e);
  vo(e, n, i, t), Ao(e, r, s);
  const o = i ? zo(e, t) : void 0;
  return t && Hs(!1), o;
}
function zo(e, t) {
  const s = e.type;
  e.accessCache = /* @__PURE__ */ Object.create(null), e.proxy = new Proxy(e.ctx, fo);
  const { setup: n } = s;
  if (n) {
    Ke();
    const r = e.setupContext = n.length > 1 ? Xo(e) : null, i = kt(e), o = Lt(
      n,
      e,
      0,
      [
        e.props,
        r
      ]
    ), l = Gn(o);
    if (qe(), i(), (l || e.sp) && !Tt(e) && Ir(e), l) {
      if (o.then(Tn, Tn), t)
        return o.then((a) => {
          En(e, a);
        }).catch((a) => {
          fs(a, e, 0);
        });
      e.asyncDep = o;
    } else
      En(e, o);
  } else
    Zr(e);
}
function En(e, t, s) {
  P(t) ? e.type.__ssrInlineRender ? e.ssrRender = t : e.render = t : G(t) && (e.setupState = _r(t)), Zr(e);
}
function Zr(e, t, s) {
  const n = e.type;
  e.render || (e.render = n.render || Te);
  {
    const r = kt(e);
    Ke();
    try {
      ho(e);
    } finally {
      qe(), r();
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
  return e.exposed ? e.exposeProxy || (e.exposeProxy = new Proxy(_r(Bi(e.exposed)), {
    get(t, s) {
      if (s in t)
        return t[s];
      if (s in Et)
        return Et[s](e);
    },
    has(t, s) {
      return s in t || s in Et;
    }
  })) : e.proxy;
}
function Zo(e) {
  return P(e) && "__vccOpts" in e;
}
const nt = (e, t) => qi(e, t, Ft), Qo = "3.5.13";
/**
* @vue/runtime-dom v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
let js;
const Rn = typeof window < "u" && window.trustedTypes;
if (Rn)
  try {
    js = /* @__PURE__ */ Rn.createPolicy("vue", {
      createHTML: (e) => e
    });
  } catch {
  }
const Qr = js ? (e) => js.createHTML(e) : (e) => e, el = "http://www.w3.org/2000/svg", tl = "http://www.w3.org/1998/Math/MathML", Me = typeof document < "u" ? document : null, Mn = Me && /* @__PURE__ */ Me.createElement("template"), sl = {
  insert: (e, t, s) => {
    t.insertBefore(e, s || null);
  },
  remove: (e) => {
    const t = e.parentNode;
    t && t.removeChild(e);
  },
  createElement: (e, t, s, n) => {
    const r = t === "svg" ? Me.createElementNS(el, e) : t === "mathml" ? Me.createElementNS(tl, e) : s ? Me.createElement(e, { is: s }) : Me.createElement(e);
    return e === "select" && n && n.multiple != null && r.setAttribute("multiple", n.multiple), r;
  },
  createText: (e) => Me.createTextNode(e),
  createComment: (e) => Me.createComment(e),
  setText: (e, t) => {
    e.nodeValue = t;
  },
  setElementText: (e, t) => {
    e.textContent = t;
  },
  parentNode: (e) => e.parentNode,
  nextSibling: (e) => e.nextSibling,
  querySelector: (e) => Me.querySelector(e),
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
      Mn.innerHTML = Qr(
        n === "svg" ? `<svg>${e}</svg>` : n === "mathml" ? `<math>${e}</math>` : e
      );
      const l = Mn.content;
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
const Pn = Symbol("_vod"), il = Symbol("_vsh"), ol = Symbol(""), ll = /(^|;)\s*display\s*:/;
function cl(e, t, s) {
  const n = e.style, r = X(s);
  let i = !1;
  if (s && !r) {
    if (t)
      if (X(t))
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
      const o = n[ol];
      o && (s += ";" + o), n.cssText = s, i = ll.test(s);
    }
  } else t && e.removeAttribute("style");
  Pn in e && (e[Pn] = i ? n.display : "", e[il] && (n.display = "none"));
}
const On = /\s*!important$/;
function Xt(e, t, s) {
  if (R(s))
    s.forEach((n) => Xt(e, t, n));
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
const Dn = ["Webkit", "Moz", "ms"], Cs = {};
function al(e, t) {
  const s = Cs[t];
  if (s)
    return s;
  let n = We(t);
  if (n !== "filter" && n in e)
    return Cs[t] = n;
  n = Yn(n);
  for (let r = 0; r < Dn.length; r++) {
    const i = Dn[r] + n;
    if (i in e)
      return Cs[t] = i;
  }
  return t;
}
const Fn = "http://www.w3.org/1999/xlink";
function Nn(e, t, s, n, r, i = wi(t)) {
  n && t.startsWith("xlink:") ? s == null ? e.removeAttributeNS(Fn, t.slice(6, t.length)) : e.setAttributeNS(Fn, t, s) : s == null || i && !Zn(s) ? e.removeAttribute(t) : e.setAttribute(
    t,
    i ? "" : Ue(s) ? String(s) : s
  );
}
function Ln(e, t, s, n, r) {
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
const kn = Symbol("_vei");
function dl(e, t, s, n, r = null) {
  const i = e[kn] || (e[kn] = {}), o = i[t];
  if (n && o)
    o.value = n;
  else {
    const [l, a] = hl(t);
    if (n) {
      const f = i[t] = ml(
        n,
        r
      );
      ul(e, l, f, a);
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
let $s = 0;
const pl = /* @__PURE__ */ Promise.resolve(), gl = () => $s || (pl.then(() => $s = 0), $s = Date.now());
function ml(e, t) {
  const s = (n) => {
    if (!n._vts)
      n._vts = Date.now();
    else if (n._vts <= s.attached)
      return;
    Ee(
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
  t === "class" ? rl(e, n, o) : t === "style" ? cl(e, s, n) : os(t) ? Ks(t) || dl(e, t, s, n, i) : (t[0] === "." ? (t = t.slice(1), !0) : t[0] === "^" ? (t = t.slice(1), !1) : wl(e, t, n, o)) ? (Ln(e, t, n), !e.tagName.includes("-") && (t === "value" || t === "checked" || t === "selected") && Nn(e, t, n, o, i, t !== "value")) : /* #11081 force set props for possible async custom element */ e._isVueCE && (/[A-Z]/.test(t) || !X(n)) ? Ln(e, We(t), n, i, t) : (t === "true-value" ? e._trueValue = n : t === "false-value" && (e._falseValue = n), Nn(e, t, n, o));
};
function wl(e, t, s, n) {
  if (n)
    return !!(t === "innerHTML" || t === "textContent" || t in e && jn(t) && P(s));
  if (t === "spellcheck" || t === "draggable" || t === "translate" || t === "form" || t === "list" && e.tagName === "INPUT" || t === "type" && e.tagName === "TEXTAREA")
    return !1;
  if (t === "width" || t === "height") {
    const r = e.tagName;
    if (r === "IMG" || r === "VIDEO" || r === "CANVAS" || r === "SOURCE")
      return !1;
  }
  return jn(t) && X(s) ? !1 : t in e;
}
const yl = /* @__PURE__ */ re({ patchProp: bl }, sl);
let Bn;
function vl() {
  return Bn || (Bn = $o(yl));
}
const xl = (...e) => {
  const t = vl().createApp(...e), { mount: s } = t;
  return t.mount = (n) => {
    const r = Il(n);
    if (!r) return;
    const i = t._component;
    !P(i) && !i.render && !i.template && (i.template = r.innerHTML), r.nodeType === 1 && (r.textContent = "");
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
  return X(e) ? document.querySelector(e) : e;
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
const Bs = "@runner", Wn = 5e3;
function $l() {
  return { runs: {}, logs: [], seen: {}, maxCursor: 0 };
}
function ei(e) {
  return e.outcome !== null || e.abandoned;
}
function Tl(e) {
  return Object.values(e.phases).sort((t, s) => t.order - s.order);
}
function Gt(e) {
  e.visible = Tl(e).map((t) => t.instanceId);
}
function El(e, t, s) {
  e.visible = e.visible.map((n) => n === t ? s : n);
  for (const n of e.arrows)
    n.from === t && (n.from = s), n.to === t && (n.to = s);
}
const Rl = /* @__PURE__ */ new Set([
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
function ti(e, t) {
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
function Ml(e, t) {
  return t.phase_id && e.instanceOfPhase[t.phase_id] ? e.instanceOfPhase[t.phase_id] : t.instance_id || t.phase_id;
}
function Pl(e, t) {
  const s = t.instance_id, n = e.phases[t.phase_id], r = e.phases[s] ?? ti(t, s);
  return n && n !== r && (r.started = r.started || n.started, r.startedAt = r.startedAt || n.startedAt, r.lastProgressAt = Math.max(
    r.lastProgressAt,
    n.lastProgressAt
  ), r.outcome = r.outcome ?? n.outcome, delete e.phases[t.phase_id], El(e, t.phase_id, s)), e.phases[s] = r, e.instanceOfPhase[t.phase_id] = s, r.phaseId = t.phase_id, r;
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
function Ol(e, t, s) {
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
function Dl(e, t) {
  if (!e || !t) return "";
  const s = Math.max(0, t - e);
  return s < 1e3 ? `${Math.round(s)} ms` : `${(s / 1e3).toFixed(1)}s`;
}
function Fl(e, t) {
  var i;
  const s = Date.parse(t.recorded_at) || 0, n = Ml(e, t);
  if (!n) return;
  let r;
  if (t.kind === "bound" ? r = Pl(e, t) : ((i = e.phases)[n] ?? (i[n] = ti(t, n)), r = e.phases[n]), t.attempt !== null && t.attempt !== void 0 && (r.attempt = t.attempt), Ol(e, t, r.instanceId), t.kind === "constructed" ? (r.constructed = !0, r.className = t.message) : t.kind === "purpose" ? r.purpose = t.message : t.kind === "cleanup" ? (r.cleanup = t.message, !r.started && r.outcome === null && (r.abandoned = !0)) : t.kind === "error" && (r.error = t.message), r.outcome !== null || r.abandoned) {
    Gt(e);
    return;
  }
  if (t.kind === "phase_end" && t.status && t.status !== "running") {
    r.outcome = t.status, r.endedAt = s, r.started = !0, rs(
      e,
      t,
      r.instanceId,
      Bs,
      [t.status, Dl(r.startedAt, s), r.error].filter(Boolean).join(" · "),
      !0
    ), Gt(e);
    return;
  }
  if (t.kind === "waiting" ? (r.waitDeadlineAt = t.deadline_at ? Date.parse(t.deadline_at) : null, r.waitReason = t.message, r.lastProgressAt = s) : Rl.has(t.kind) && (r.waitDeadlineAt = null, r.waitReason = "", r.lastProgressAt = s), (t.kind === "phase_start" || t.kind === "bound") && !r.started) {
    r.started = !0, r.startedAt = s, t.kind === "phase_start" && (r.phaseId = t.phase_id), rs(e, t, Bs, r.instanceId, r.name, !1), Gt(e);
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
  const s = t.events.filter((f) => !e.seen[f.event_id]), n = t.runs.some((f) => {
    const d = e.runs[f.run_id];
    return !d || d.status !== f.status || d.endedAt !== f.ended_at;
  });
  if (s.length === 0 && !n) return e;
  const r = structuredClone(e);
  for (const f of t.runs) {
    (i = r.runs)[o = f.run_id] ?? (i[o] = Un(f));
    const d = r.runs[f.run_id];
    d.status = f.status, d.endedAt = f.ended_at;
  }
  for (const f of s.sort((d, p) => d.cursor - p.cursor)) {
    r.seen[f.event_id] = !0, r.maxCursor = Math.max(r.maxCursor, f.cursor), (l = r.runs)[a = f.run_id] ?? (l[a] = Un({
      run_id: f.run_id,
      adw_name: f.adw_name,
      status: "running",
      started_at: f.recorded_at,
      ended_at: null
    }));
    const d = r.runs[f.run_id];
    Fl(d, f), r.logs.push({
      cursor: f.cursor,
      eventId: f.event_id,
      runId: f.run_id,
      phaseId: f.phase_id,
      instanceId: f.instance_id,
      recordedAt: f.recorded_at,
      kind: f.kind,
      text: Nl(f)
    });
  }
  return r.logs.sort((f, d) => f.cursor - d.cursor), r.logs.length > Wn && r.logs.splice(0, r.logs.length - Wn), r;
}
const kl = {
  idle: "Idle -- no ADW run recorded yet",
  live: "Live",
  completed: "Completed",
  pinned: "Pinned after failure"
}, si = {
  waiting: "Waiting",
  running: "Running",
  stalled: "Stalled",
  fail: "Fail",
  pass: "Pass"
};
function Ws(e, t) {
  if (!e) return "";
  const s = Math.max(0, Math.round((t - e) / 1e3));
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
}
function Hl(e, t, s, n, r, i) {
  let o = "waiting", l = "";
  if (e.outcome === "pass" || e.outcome === "fail")
    o = e.outcome, l = [Ws(e.startedAt, e.endedAt), e.error].filter(Boolean).join(" -- ");
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
        terminal: ei(e),
        lastProgressAt: e.lastProgressAt,
        waitDeadlineAt: e.waitDeadlineAt,
        waitReason: e.waitReason
      },
      s,
      n
    );
    o = a ? "stalled" : e.waitDeadlineAt !== null ? "waiting" : "running", l = [
      Ws(e.startedAt, s),
      (a == null ? void 0 : a.reason) ?? e.waitReason
    ].filter(Boolean).join(" -- ");
  }
  return {
    instanceId: e.instanceId,
    name: e.name,
    attempt: e.attempt,
    status: o,
    statusLabel: si[o],
    detail: l,
    purpose: e.purpose,
    selected: i
  };
}
const jl = {
  running: "running",
  success: "pass",
  fail: "fail",
  interrupted: "stalled"
};
function Bl(e, t) {
  const s = jl[e.status] ?? "waiting", n = Date.parse(e.startedAt) || 0, r = e.endedAt && Date.parse(e.endedAt) || t;
  return {
    instanceId: Bs,
    kind: "runner",
    name: e.adwName,
    attempt: null,
    status: s,
    statusLabel: si[s],
    detail: Ws(n, r),
    purpose: `ADW run ${e.runId}: starts each phase and receives its outcome`,
    selected: !1
  };
}
function Wl(e, t) {
  if (!e || !t) return "";
  const s = Math.max(0, t - e);
  return s >= 1e4 ? `+${(s / 1e3).toFixed(1)} s` : `+${s} ms`;
}
function Ul(e, t, s, n, r) {
  var p;
  if (!e) return { runId: "", columns: [], rows: [] };
  const i = e.visible.map((m) => e.phases[m]).filter(Boolean).map((m) => ({
    ...Hl(
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
  const o = [Bl(e, t), ...i], l = new Map(
    o.map((m, x) => [m.instanceId, x])
  ), a = Date.parse(e.startedAt) || (((p = e.arrows[0]) == null ? void 0 : p.at) ?? 0), d = e.arrows.filter((m) => l.has(m.from) && l.has(m.to)).sort((m, x) => m.cursor - x.cursor).map((m) => ({
    id: m.id,
    from: l.get(m.from),
    to: l.get(m.to),
    text: m.text,
    dashed: m.dashed,
    kind: m.kind,
    elapsed: Wl(a, m.at)
  }));
  for (const m of o) {
    if (m.kind === "runner") {
      m.activeFrom = d.length ? 0 : null, m.activeTo = e.status === "running" ? null : d.length - 1;
      continue;
    }
    const x = l.get(m.instanceId), M = d.findIndex((D) => D.to === x || D.from === x), C = d.findIndex(
      (D) => D.kind === "phase_end" && D.from === x
    ), K = e.phases[m.instanceId];
    m.activeFrom = K != null && K.started && M >= 0 ? M : null, m.activeTo = C >= 0 ? C : null;
  }
  return { runId: e.runId, columns: o, rows: d };
}
function Vl(e) {
  const t = e.replace(/\.py$/, "").replace(/^adw_/, "").replace(/^(interface|op)_/, "").replace(/_/g, " ").trim();
  return t ? t[0].toUpperCase() + t.slice(1) : "An ADW";
}
function Kl(e) {
  if (!e) return "No ADW has run yet -- the next one started will show here";
  const t = Vl(e.adwName), s = e.visible.map((f) => e.phases[f]).filter(Boolean), n = s.length, i = s.filter((f) => f.started && !ei(f)).at(-1), o = s.find((f) => f.outcome === "fail"), l = (f) => `step ${s.indexOf(f) + 1} of ${n}, ${f.name.replace(/_/g, " ")}`, a = (f) => `${f} step${f === 1 ? "" : "s"}`;
  switch (e.status) {
    case "running":
      return i ? `Running now: ${t} -- ${l(i)}` : n === 0 ? `Running now: ${t} -- starting up` : `Running now: ${t} -- between steps, ${s.filter((f) => f.outcome).length} of ${n} done`;
    case "success":
      return `Finished: ${t} -- all ${a(n)} passed`;
    case "fail":
      return o ? `Failed: ${t} -- stopped at ${l(o)}` : `Failed: ${t} -- after ${a(n)}`;
    case "interrupted":
      return i ? `Stopped: ${t} -- its process ended during ${l(i)}` : `Stopped: ${t} -- its process ended without finishing`;
    default:
      return `${t} -- ${a(n)}`;
  }
}
function ql(e, t, s, n) {
  var i;
  const r = s.mode === "phase" ? (i = n.runs[s.runId]) == null ? void 0 : i.phases[s.instanceId] : void 0;
  return {
    headline: Kl(e),
    modeLabel: kl[t],
    filterLabel: s.mode === "all" ? "All events" : `Run ${s.runId} -- phase ${(r == null ? void 0 : r.name) ?? s.instanceId} (${s.instanceId}${r != null && r.attempt ? `, attempt ${r.attempt}` : ""})`,
    clearLabel: e ? `Clear displayed logs for ${e.runId}` : "Clear displayed logs",
    clearDisabledReason: e ? "" : "No ADW run is selected, so there is nothing run-scoped to clear."
  };
}
class Gl {
  constructor(t) {
    Q(this, "state", $l());
    Q(this, "selected", { runId: null, pinReleased: !1 });
    Q(this, "filter", { mode: "all" });
    Q(this, "connection", { status: "connecting" });
    Q(this, "timeoutSeconds", 120);
    Q(this, "lastDelayMs", null);
    Q(this, "renderError", "");
    Q(this, "tick", null);
    Q(this, "unsubscribe", null);
    Q(this, "listeners", /* @__PURE__ */ new Set());
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
      Ul(
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
      ...ql(t, s, this.filter, this.state)
    };
  }
  publish() {
    this.deps.legacy.setVisible(this.filter.mode === "all");
    const t = this.view();
    for (const s of this.listeners) s(t);
  }
}
class Jl {
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
class zl {
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
class Yl {
  async getJSON(t) {
    const s = await fetch(t, { cache: "no-store" });
    if (!s.ok) throw new Error(`HTTP ${s.status} from ${t}`);
    return s.json();
  }
}
class Xl {
  set(t, s) {
    return window.setTimeout(t, s);
  }
  clear(t) {
    window.clearTimeout(t);
  }
}
class Zl {
  constructor() {
    Q(this, "offset", 0);
  }
  align(t) {
    const s = Date.parse(t);
    Number.isNaN(s) || (this.offset = s - Date.now());
  }
  now() {
    return Date.now() + this.offset;
  }
}
class Ql {
  setVisible() {
  }
}
class ec {
  get() {
    return 0;
  }
  set() {
  }
}
class tc {
  constructor(t, s, n) {
    Q(this, "listeners", /* @__PURE__ */ new Set());
    Q(this, "cursor", null);
    Q(this, "handle", null);
    Q(this, "running", !1);
    Q(this, "inflight", !1);
    Q(this, "failures", 0);
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
class sc {
  constructor() {
    Q(this, "lastGood", { runId: "", columns: [], rows: [] });
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
const nc = { class: "adwdbg-log" }, rc = { class: "adwdbg-log-head" }, ic = { class: "adwdbg-log-label" }, oc = {
  key: 0,
  class: "adwdbg-log-empty"
}, lc = ["data-kind", "data-run"], cc = /* @__PURE__ */ Ge({
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
    }, { immediate: !0 }), (i, o) => (F(), V("div", nc, [
      k("div", rc, [
        k("span", ic, Y(i.label), 1),
        k("span", null, Y(i.lines.length) + " line" + Y(i.lines.length === 1 ? "" : "s") + Y(n.value ? "" : " · paused (scroll to bottom to follow)"), 1)
      ]),
      k("div", {
        ref_key: "host",
        ref: s,
        class: Ve(["adwdbg-log-lines", { "adwdbg-log-tall": i.tall }]),
        role: "log",
        onScroll: r
      }, [
        i.lines.length === 0 ? (F(), V("div", oc, "No ADW events to show.")) : Oe("", !0),
        (F(!0), V(ee, null, at(i.lines, (l) => (F(), V("div", {
          key: l.eventId,
          class: "adwdbg-log-line",
          "data-kind": l.kind,
          "data-run": l.runId
        }, Y(l.text), 9, lc))), 128))
      ], 34)
    ]));
  }
}), It = 78, ac = 170, Nt = 40, an = 22, Es = 11;
function Us(e, t) {
  return (e + 0.5) / Math.max(1, t) * 100;
}
function uc(e) {
  return 100 / Math.max(1, e);
}
function is(e) {
  return an + e * Nt + Nt * 0.62;
}
function ni(e) {
  return an * 2 + Math.max(1, e) * Nt;
}
function fc(e, t, s) {
  const n = is(e) - Es, r = t === null ? ni(s) - an / 2 : is(Math.max(e, t)) + Es;
  return { top: n, height: Math.max(Es * 2, r - n) };
}
function dc(e, t) {
  return e === t ? "self" : e < t ? "right" : "left";
}
const hc = ["data-status"], pc = /* @__PURE__ */ Ge({
  __name: "ActivationBar",
  props: {
    from: {},
    to: {},
    rows: {},
    status: {}
  },
  setup(e) {
    const t = e, s = nt(() => fc(t.from, t.to, t.rows));
    return (n, r) => (F(), V("span", {
      class: Ve(["sd-bar", { "sd-bar-open": n.to === null }]),
      "data-status": n.status,
      style: pe({ top: `${s.value.top}px`, height: `${s.value.height}px` })
    }, null, 14, hc));
  }
}), gc = ["data-lifeline"], mc = /* @__PURE__ */ Ge({
  __name: "Lifeline",
  props: {
    column: {},
    centre: {},
    rows: {}
  },
  setup(e) {
    return (t, s) => (F(), V("div", {
      class: "sd-lifeline-track",
      "data-lifeline": t.column.instanceId,
      style: pe({ left: `${t.centre}%` })
    }, [
      s[0] || (s[0] = k("span", { class: "sd-lifeline" }, null, -1)),
      t.column.activeFrom !== null && t.column.activeFrom !== void 0 ? (F(), tt(pc, {
        key: 0,
        from: t.column.activeFrom,
        to: t.column.activeTo ?? null,
        rows: t.rows,
        status: t.column.status
      }, null, 8, ["from", "to", "rows", "status"])) : Oe("", !0)
    ], 12, gc));
  }
}), _c = ["data-kind", "data-row"], bc = ["title"], wc = { class: "sd-label-text" }, yc = /* @__PURE__ */ Ge({
  __name: "MessageArrow",
  props: {
    row: {},
    index: {},
    count: {}
  },
  setup(e) {
    const t = e, s = nt(() => dc(t.row.from, t.row.to)), n = nt(() => {
      const r = `${is(t.index) - Nt * 0.62}px`, i = `${Nt}px`, o = Us(t.row.from, t.count);
      if (s.value === "self") {
        const a = t.row.from === t.count - 1 ? 0.46 : 0.92;
        return { top: r, height: i, left: `${o}%`, width: `${uc(t.count) * a}%` };
      }
      const l = Us(t.row.to, t.count);
      return { top: r, height: i, left: `${Math.min(o, l)}%`, width: `${Math.abs(l - o)}%` };
    });
    return (r, i) => (F(), V("div", {
      class: Ve(["sd-message", [`sd-${s.value}`, { "sd-dashed": r.row.dashed }]]),
      "data-kind": r.row.kind,
      "data-row": r.index,
      style: pe(n.value)
    }, [
      k("div", {
        class: "sd-label",
        title: r.row.text
      }, [
        k("span", wc, Y(r.row.text), 1)
      ], 8, bc),
      i[0] || (i[0] = k("div", { class: "sd-line" }, [
        k("span", { class: "sd-head" })
      ], -1))
    ], 14, _c));
  }
}), vc = ["data-status", "data-instance", "data-edge", "data-participant", "title", "aria-pressed"], xc = { class: "sd-name" }, Sc = { class: "sd-status" }, Vn = /* @__PURE__ */ Ge({
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
    return (i, o) => (F(), V("button", {
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
      k("span", xc, [
        St(Y(i.column.name), 1),
        i.column.attempt && i.column.attempt > 1 ? (F(), V(ee, { key: 0 }, [
          St(" · attempt " + Y(i.column.attempt), 1)
        ], 64)) : Oe("", !0)
      ]),
      k("span", Sc, [
        St(Y(i.column.statusLabel), 1),
        i.column.detail ? (F(), V(ee, { key: 0 }, [
          St(" · " + Y(i.column.detail), 1)
        ], 64)) : Oe("", !0)
      ])
    ], 10, vc));
  }
}), Ic = /* @__PURE__ */ Ge({
  __name: "TimeAxis",
  props: {
    rows: {}
  },
  setup(e) {
    return (t, s) => (F(), V("div", {
      class: "sd-axis",
      style: pe({ width: `${He(It)}px` }),
      "aria-hidden": "true"
    }, [
      (F(!0), V(ee, null, at(t.rows, (n, r) => (F(), V("span", {
        key: n.id,
        class: "sd-tick",
        style: pe({ top: `${He(is)(r)}px` })
      }, Y(n.elapsed), 5))), 128))
    ], 4));
  }
}), Ac = { class: "sd" }, Cc = { class: "sd-tools" }, $c = { class: "sd-zoom-value" }, Tc = { class: "sd-hint" }, Ec = { class: "sd-frozen" }, Rc = /* @__PURE__ */ Ge({
  __name: "SequenceDiagram",
  props: {
    model: {},
    hint: { default: "Click a phase box to filter the events below; click the ADW box for all events." }
  },
  emits: ["phase-click", "runner-click"],
  setup(e, { emit: t }) {
    const s = e, n = t, r = et(1), i = et(null), o = et(null), l = et(!1);
    let a = null;
    $r(() => {
      typeof IntersectionObserver > "u" || !i.value || !o.value || (a = new IntersectionObserver(([x]) => {
        l.value = x.isIntersecting;
      }, { root: i.value }), a.observe(o.value));
    }), rn(() => a == null ? void 0 : a.disconnect());
    const f = nt(() => Math.max(1, s.model.columns.length)), d = nt(() => s.model.rows.length), p = nt(() => `${It + f.value * ac}px`);
    function m(x) {
      x.kind === "runner" ? n("runner-click") : n("phase-click", x.instanceId);
    }
    return (x, M) => (F(), V("div", Ac, [
      k("div", Cc, [
        k("button", {
          type: "button",
          class: "sd-zoom",
          "aria-label": "Zoom out",
          onClick: M[0] || (M[0] = (C) => r.value = Math.max(0.4, r.value - 0.1))
        }, "-"),
        k("span", $c, Y(Math.round(r.value * 100)) + "%", 1),
        k("button", {
          type: "button",
          class: "sd-zoom",
          "aria-label": "Zoom in",
          onClick: M[1] || (M[1] = (C) => r.value = Math.min(2, r.value + 0.1))
        }, "+"),
        k("button", {
          type: "button",
          class: "sd-zoom",
          onClick: M[2] || (M[2] = (C) => r.value = 1)
        }, "Reset"),
        k("span", Tc, Y(x.hint), 1)
      ]),
      k("div", {
        ref_key: "scroller",
        ref: i,
        class: "sd-scroll"
      }, [
        k("div", {
          class: "sd-canvas",
          style: pe({ zoom: r.value, minWidth: p.value })
        }, [
          k("div", Ec, [
            k("div", {
              class: Ve(["sd-titles sd-titles-top", { "sd-pinned": !l.value }]),
              style: pe({ paddingLeft: `${He(It)}px` })
            }, [
              (F(!0), V(ee, null, at(x.model.columns, (C) => (F(), tt(Vn, {
                key: C.instanceId,
                column: C,
                edge: "top",
                onSelect: m
              }, null, 8, ["column"]))), 128))
            ], 6),
            k("div", {
              class: "sd-body",
              style: pe({ height: `${He(ni)(d.value)}px` })
            }, [
              be(Ic, {
                rows: x.model.rows
              }, null, 8, ["rows"]),
              k("div", {
                class: "sd-plot",
                style: pe({ left: `${He(It)}px` })
              }, [
                (F(!0), V(ee, null, at(x.model.columns, (C, K) => (F(), tt(mc, {
                  key: C.instanceId,
                  column: C,
                  centre: He(Us)(K, f.value),
                  rows: d.value
                }, null, 8, ["column", "centre", "rows"]))), 128)),
                (F(!0), V(ee, null, at(x.model.rows, (C, K) => (F(), tt(yc, {
                  key: C.id,
                  row: C,
                  index: K,
                  count: f.value
                }, null, 8, ["row", "index", "count"]))), 128))
              ], 4)
            ], 4)
          ]),
          k("div", {
            ref_key: "bottomRow",
            ref: o,
            class: "sd-titles sd-titles-bottom",
            style: pe({ marginLeft: `${He(It)}px` })
          }, [
            (F(!0), V(ee, null, at(x.model.columns, (C) => (F(), tt(Vn, {
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
}), Mc = {
  key: 0,
  class: "adwseq",
  "aria-label": "ADW run sequence diagram"
}, Pc = { class: "adwseq-head" }, Oc = { "data-field": "headline" }, Dc = ["data-run-status"], Fc = {
  key: 0,
  class: "adwdbg-warn",
  "data-warning": "connection",
  role: "status"
}, Nc = {
  key: 1,
  class: "adwdbg-warn",
  "data-warning": "feed",
  role: "status"
}, Lc = {
  key: 2,
  class: "adwdbg-warn",
  "data-warning": "render",
  role: "alert"
}, kc = { class: "adwseq-stage" }, Hc = {
  key: 1,
  class: "adwdbg-idle",
  "data-field": "idle"
}, jc = ["aria-label"], Kn = "@all", Bc = /* @__PURE__ */ Ge({
  __name: "RunSequencePanel",
  props: {
    controller: {}
  },
  setup(e) {
    const t = e, s = Wi(null), n = et(null), r = t.controller.subscribe((l) => {
      s.value = l;
    });
    rn(r), Er((l) => (t.controller.reportRenderError(l instanceof Error ? l.message : String(l)), !1));
    function i(l) {
      if (n.value === l) {
        n.value = null, t.controller.allEvents();
        return;
      }
      n.value = l, l === Kn ? t.controller.allEvents() : t.controller.selectPhase(l);
    }
    function o() {
      n.value && i(n.value);
    }
    return (l, a) => s.value ? (F(), V("section", Mc, [
      k("header", Pc, [
        k("strong", Oc, Y(s.value.headline), 1),
        s.value.runStatus ? (F(), V("span", {
          key: 0,
          class: "adwdbg-chip",
          "data-run-status": s.value.runStatus,
          "data-field": "status"
        }, Y(s.value.runStatus), 9, Dc)) : Oe("", !0)
      ]),
      s.value.connection.status === "disconnected" ? (F(), V("p", Fc, " Event feed disconnected (attempt " + Y(s.value.connection.attempts) + "): " + Y(s.value.connection.reason) + ". Showing the last events received. ", 1)) : s.value.connection.status === "degraded" ? (F(), V("p", Nc, " The ADW trace cannot be read: " + Y(s.value.connection.reason), 1)) : Oe("", !0),
      s.value.renderError ? (F(), V("p", Lc, " Diagram could not be redrawn (" + Y(s.value.renderError) + "). Showing the last good diagram. ", 1)) : Oe("", !0),
      k("div", kc, [
        s.value.diagram.columns.length ? (F(), tt(Rc, {
          key: 0,
          model: s.value.diagram,
          hint: "Click a phase to open its console; click it again to close.",
          onPhaseClick: a[0] || (a[0] = (f) => i(f)),
          onRunnerClick: a[1] || (a[1] = (f) => i(Kn))
        }, null, 8, ["model"])) : (F(), V("p", Hc, Y(s.value.connection.status === "connecting" ? "Loading the run…" : "This run has not started a step yet."), 1)),
        n.value ? (F(), V("div", {
          key: 2,
          class: "adwseq-popup",
          "data-field": "popup",
          role: "dialog",
          "aria-label": s.value.filterLabel
        }, [
          k("button", {
            type: "button",
            class: "adwseq-close",
            "aria-label": "Close console",
            onClick: a[2] || (a[2] = (f) => o())
          }, "×"),
          be(cc, {
            lines: s.value.lines,
            label: s.value.filterLabel,
            tall: !1
          }, null, 8, ["lines", "label"])
        ], 8, jc)) : Oe("", !0)
      ])
    ])) : Oe("", !0);
  }
});
function Vc(e, t) {
  const s = new Xl();
  let n = !0;
  const r = new Gl({
    source: new tc(new Yl(), s, {
      url: t.url,
      activeMs: 1500,
      idleMs: 15e3,
      retryStepMs: 2e3,
      retryMaxMs: 15e3,
      isActive: () => n && document.visibilityState !== "hidden"
    }),
    selection: new Jl(t.runId),
    stall: new zl(),
    renderer: new sc(),
    cleared: new ec(),
    legacy: new Ql(),
    clock: new Zl(),
    timer: s
  }), i = r.subscribe((l) => {
    n = l.runStatus === "running" || l.runStatus === null;
  }), o = xl(Bc, { controller: r });
  return o.mount(e), r.start(), {
    controller: r,
    unmount() {
      i(), r.dispose(), o.unmount();
    }
  };
}
export {
  Vc as mountRunSequence
};
