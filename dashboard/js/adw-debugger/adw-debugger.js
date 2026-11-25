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
function Vs(e) {
  const t = /* @__PURE__ */ Object.create(null);
  for (const s of e.split(",")) t[s] = 1;
  return (s) => s in t;
}
const K = {}, ft = [], Te = () => {
}, li = () => !1, os = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && // uppercase letter
(e.charCodeAt(2) > 122 || e.charCodeAt(2) < 97), Ks = (e) => e.startsWith("onUpdate:"), re = Object.assign, Gs = (e, t) => {
  const s = e.indexOf(t);
  s > -1 && e.splice(s, 1);
}, ci = Object.prototype.hasOwnProperty, L = (e, t) => ci.call(e, t), R = Array.isArray, dt = (e) => ls(e) === "[object Map]", Kn = (e) => ls(e) === "[object Set]", P = (e) => typeof e == "function", Q = (e) => typeof e == "string", Ue = (e) => typeof e == "symbol", J = (e) => e !== null && typeof e == "object", Gn = (e) => (J(e) || P(e)) && P(e.then) && P(e.catch), qn = Object.prototype.toString, ls = (e) => qn.call(e), ai = (e) => ls(e).slice(8, -1), Jn = (e) => ls(e) === "[object Object]", qs = (e) => Q(e) && e !== "NaN" && e[0] !== "-" && "" + parseInt(e, 10) === e, At = /* @__PURE__ */ Vs(
  // the leading comma is intentional so empty string "" is also included
  ",key,ref,ref_for,ref_key,onVnodeBeforeMount,onVnodeMounted,onVnodeBeforeUpdate,onVnodeUpdated,onVnodeBeforeUnmount,onVnodeUnmounted"
), cs = (e) => {
  const t = /* @__PURE__ */ Object.create(null);
  return (s) => t[s] || (t[s] = e(s));
}, ui = /-(\w)/g, We = cs(
  (e) => e.replace(ui, (t, s) => s ? s.toUpperCase() : "")
), fi = /\B([A-Z])/g, lt = cs(
  (e) => e.replace(fi, "-$1").toLowerCase()
), zn = cs((e) => e.charAt(0).toUpperCase() + e.slice(1)), _s = cs(
  (e) => e ? `on${zn(e)}` : ""
), Be = (e, t) => !Object.is(e, t), bs = (e, ...t) => {
  for (let s = 0; s < e.length; s++)
    e[s](...t);
}, Yn = (e, t, s, n = !1) => {
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
const as = () => gn || (gn = typeof globalThis < "u" ? globalThis : typeof self < "u" ? self : typeof window < "u" ? window : typeof global < "u" ? global : {});
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
  } else if (Q(e) || J(e))
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
function Ve(e) {
  let t = "";
  if (Q(e))
    t = e;
  else if (R(e))
    for (let s = 0; s < e.length; s++) {
      const n = Ve(e[s]);
      n && (t += n + " ");
    }
  else if (J(e))
    for (const s in e)
      e[s] && (t += s + " ");
  return t.trim();
}
const _i = "itemscope,allowfullscreen,formnovalidate,ismap,nomodule,novalidate,readonly", bi = /* @__PURE__ */ Vs(_i);
function Xn(e) {
  return !!e || e === "";
}
const Zn = (e) => !!(e && e.__v_isRef === !0), j = (e) => Q(e) ? e : e == null ? "" : R(e) || J(e) && (e.toString === qn || !P(e.toString)) ? Zn(e) ? j(e.value) : JSON.stringify(e, Qn, 2) : String(e), Qn = (e, t) => Zn(t) ? Qn(e, t.value) : dt(t) ? {
  [`Map(${t.size})`]: [...t.entries()].reduce(
    (s, [n, r], i) => (s[ws(n, i) + " =>"] = r, s),
    {}
  )
} : Kn(t) ? {
  [`Set(${t.size})`]: [...t.values()].map((s) => ws(s))
} : Ue(t) ? ws(t) : J(t) && !R(t) && !Jn(t) ? String(t) : t, ws = (e, t = "") => {
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
const ys = /* @__PURE__ */ new WeakSet();
class er {
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
    this.flags & 2 && !(this.flags & 32) || this.flags & 8 || sr(this);
  }
  run() {
    if (!(this.flags & 1))
      return this.fn();
    this.flags |= 2, mn(this), nr(this);
    const t = V, s = _e;
    V = this, _e = !0;
    try {
      return this.fn();
    } finally {
      rr(this), V = t, _e = s, this.flags &= -3;
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
let tr = 0, Ct, $t;
function sr(e, t = !1) {
  if (e.flags |= 8, t) {
    e.next = $t, $t = e;
    return;
  }
  e.next = Ct, Ct = e;
}
function Js() {
  tr++;
}
function zs() {
  if (--tr > 0)
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
function nr(e) {
  for (let t = e.deps; t; t = t.nextDep)
    t.version = -1, t.prevActiveLink = t.dep.activeLink, t.dep.activeLink = t;
}
function rr(e) {
  let t, s = e.depsTail, n = s;
  for (; n; ) {
    const r = n.prevDep;
    n.version === -1 ? (n === s && (s = r), Ys(n), vi(n)) : t = n, n.dep.activeLink = n.prevActiveLink, n.prevActiveLink = void 0, n = r;
  }
  e.deps = t, e.depsTail = s;
}
function Rs(e) {
  for (let t = e.deps; t; t = t.nextDep)
    if (t.dep.version !== t.version || t.dep.computed && (ir(t.dep.computed) || t.dep.version !== t.version))
      return !0;
  return !!e._dirty;
}
function ir(e) {
  if (e.flags & 4 && !(e.flags & 16) || (e.flags &= -17, e.globalVersion === Mt))
    return;
  e.globalVersion = Mt;
  const t = e.dep;
  if (e.flags |= 2, t.version > 0 && !e.isSSR && e.deps && !Rs(e)) {
    e.flags &= -3;
    return;
  }
  const s = V, n = _e;
  V = e, _e = !0;
  try {
    nr(e);
    const r = e.fn(e._value);
    (t.version === 0 || Be(r, e._value)) && (e._value = r, t.version++);
  } catch (r) {
    throw t.version++, r;
  } finally {
    V = s, _e = n, rr(e), e.flags &= -3;
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
function vi(e) {
  const { prevDep: t, nextDep: s } = e;
  t && (t.nextDep = s, e.prevDep = void 0), s && (s.prevDep = t, e.nextDep = void 0);
}
let _e = !0;
const or = [];
function Ke() {
  or.push(_e), _e = !1;
}
function Ge() {
  const e = or.pop();
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
class Xs {
  constructor(t) {
    this.computed = t, this.version = 0, this.activeLink = void 0, this.subs = void 0, this.map = void 0, this.key = void 0, this.sc = 0;
  }
  track(t) {
    if (!V || !_e || V === this.computed)
      return;
    let s = this.activeLink;
    if (s === void 0 || s.sub !== V)
      s = this.activeLink = new xi(V, this), V.deps ? (s.prevDep = V.depsTail, V.depsTail.nextDep = s, V.depsTail = s) : V.deps = V.depsTail = s, lr(s);
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
    Js();
    try {
      for (let s = this.subs; s; s = s.prevSub)
        s.sub.notify() && s.sub.dep.notify();
    } finally {
      zs();
    }
  }
}
function lr(e) {
  if (e.dep.sc++, e.sub.flags & 4) {
    const t = e.dep.computed;
    if (t && !e.dep.subs) {
      t.flags |= 20;
      for (let n = t.deps; n; n = n.nextDep)
        lr(n);
    }
    const s = e.dep.subs;
    s !== e && (e.prevSub = s, s && (s.nextSub = e)), e.dep.subs = e;
  }
}
const Ms = /* @__PURE__ */ new WeakMap(), nt = Symbol(
  ""
), Ps = Symbol(
  ""
), Pt = Symbol(
  ""
);
function te(e, t, s) {
  if (_e && V) {
    let n = Ms.get(e);
    n || Ms.set(e, n = /* @__PURE__ */ new Map());
    let r = n.get(s);
    r || (n.set(s, r = new Xs()), r.map = n, r.key = s), r.track();
  }
}
function Oe(e, t, s, n, r, i) {
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
    const a = R(e), f = a && qs(s);
    if (a && s === "length") {
      const d = Number(n);
      o.forEach((p, m) => {
        (m === "length" || m === Pt || !Ue(m) && m >= d) && l(p);
      });
    } else
      switch ((s !== void 0 || o.has(void 0)) && l(o.get(s)), f && l(o.get(Pt)), t) {
        case "add":
          a ? f && l(o.get("length")) : (l(o.get(nt)), dt(e) && l(o.get(Ps)));
          break;
        case "delete":
          a || (l(o.get(nt)), dt(e) && l(o.get(Ps)));
          break;
        case "set":
          dt(e) && l(o.get(nt));
          break;
      }
  }
  zs();
}
function ct(e) {
  const t = k(e);
  return t === e ? t : (te(t, "iterate", Pt), me(e) ? t : t.map(se));
}
function us(e) {
  return te(e = k(e), "iterate", Pt), e;
}
const Si = {
  __proto__: null,
  [Symbol.iterator]() {
    return vs(this, Symbol.iterator, se);
  },
  concat(...e) {
    return ct(this).concat(
      ...e.map((t) => R(t) ? ct(t) : t)
    );
  },
  entries() {
    return vs(this, "entries", (e) => (e[1] = se(e[1]), e));
  },
  every(e, t) {
    return Me(this, "every", e, t, void 0, arguments);
  },
  filter(e, t) {
    return Me(this, "filter", e, t, (s) => s.map(se), arguments);
  },
  find(e, t) {
    return Me(this, "find", e, t, se, arguments);
  },
  findIndex(e, t) {
    return Me(this, "findIndex", e, t, void 0, arguments);
  },
  findLast(e, t) {
    return Me(this, "findLast", e, t, se, arguments);
  },
  findLastIndex(e, t) {
    return Me(this, "findLastIndex", e, t, void 0, arguments);
  },
  // flat, flatMap could benefit from ARRAY_ITERATE but are not straight-forward to implement
  forEach(e, t) {
    return Me(this, "forEach", e, t, void 0, arguments);
  },
  includes(...e) {
    return xs(this, "includes", e);
  },
  indexOf(...e) {
    return xs(this, "indexOf", e);
  },
  join(e) {
    return ct(this).join(e);
  },
  // keys() iterator only reads `length`, no optimisation required
  lastIndexOf(...e) {
    return xs(this, "lastIndexOf", e);
  },
  map(e, t) {
    return Me(this, "map", e, t, void 0, arguments);
  },
  pop() {
    return vt(this, "pop");
  },
  push(...e) {
    return vt(this, "push", e);
  },
  reduce(e, ...t) {
    return _n(this, "reduce", e, t);
  },
  reduceRight(e, ...t) {
    return _n(this, "reduceRight", e, t);
  },
  shift() {
    return vt(this, "shift");
  },
  // slice could use ARRAY_ITERATE but also seems to beg for range tracking
  some(e, t) {
    return Me(this, "some", e, t, void 0, arguments);
  },
  splice(...e) {
    return vt(this, "splice", e);
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
    return vt(this, "unshift", e);
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
const Ii = Array.prototype;
function Me(e, t, s, n, r, i) {
  const o = us(e), l = o !== e && !me(e), a = o[t];
  if (a !== Ii[t]) {
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
  const n = k(e);
  te(n, "iterate", Pt);
  const r = n[t](...s);
  return (r === -1 || r === !1) && tn(s[0]) ? (s[0] = k(s[0]), n[t](...s)) : r;
}
function vt(e, t, s = []) {
  Ke(), Js();
  const n = k(e)[t].apply(e, s);
  return zs(), Ge(), n;
}
const Ai = /* @__PURE__ */ Vs("__proto__,__v_isRef,__isVue"), cr = new Set(
  /* @__PURE__ */ Object.getOwnPropertyNames(Symbol).filter((e) => e !== "arguments" && e !== "caller").map((e) => Symbol[e]).filter(Ue)
);
function Ci(e) {
  Ue(e) || (e = String(e));
  const t = k(this);
  return te(t, "has", e), t.hasOwnProperty(e);
}
class ar {
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
      return n === (r ? i ? Ni : hr : i ? dr : fr).get(t) || // receiver is not the reactive proxy, but has the same prototype
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
    return (Ue(s) ? cr.has(s) : Ai(s)) || (r || te(t, "get", s), i) ? l : ne(l) ? o && qs(s) ? l : l.value : J(l) ? r ? pr(l) : Qs(l) : l;
  }
}
class ur extends ar {
  constructor(t = !1) {
    super(!1, t);
  }
  set(t, s, n, r) {
    let i = t[s];
    if (!this._isShallow) {
      const a = it(i);
      if (!me(n) && !it(n) && (i = k(i), n = k(n)), !R(t) && ne(i) && !ne(n))
        return a ? !1 : (i.value = n, !0);
    }
    const o = R(t) && qs(s) ? Number(s) < t.length : L(t, s), l = Reflect.set(
      t,
      s,
      n,
      ne(t) ? t : r
    );
    return t === k(r) && (o ? Be(n, i) && Oe(t, "set", s, n) : Oe(t, "add", s, n)), l;
  }
  deleteProperty(t, s) {
    const n = L(t, s);
    t[s];
    const r = Reflect.deleteProperty(t, s);
    return r && n && Oe(t, "delete", s, void 0), r;
  }
  has(t, s) {
    const n = Reflect.has(t, s);
    return (!Ue(s) || !cr.has(s)) && te(t, "has", s), n;
  }
  ownKeys(t) {
    return te(
      t,
      "iterate",
      R(t) ? "length" : nt
    ), Reflect.ownKeys(t);
  }
}
class $i extends ar {
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
const Ei = /* @__PURE__ */ new ur(), Ti = /* @__PURE__ */ new $i(), Ri = /* @__PURE__ */ new ur(!0);
const Os = (e) => e, Vt = (e) => Reflect.getPrototypeOf(e);
function Mi(e, t, s) {
  return function(...n) {
    const r = this.__v_raw, i = k(r), o = dt(i), l = e === "entries" || e === Symbol.iterator && o, a = e === "keys" && o, f = r[e](...n), d = s ? Os : t ? Ds : se;
    return !t && te(
      i,
      "iterate",
      a ? Ps : nt
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
function Pi(e, t) {
  const s = {
    get(r) {
      const i = this.__v_raw, o = k(i), l = k(r);
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
      return !e && te(k(r), "iterate", nt), Reflect.get(r, "size", r);
    },
    has(r) {
      const i = this.__v_raw, o = k(i), l = k(r);
      return e || (Be(r, l) && te(o, "has", r), te(o, "has", l)), r === l ? i.has(r) : i.has(r) || i.has(l);
    },
    forEach(r, i) {
      const o = this, l = o.__v_raw, a = k(l), f = t ? Os : e ? Ds : se;
      return !e && te(a, "iterate", nt), l.forEach((d, p) => r.call(i, f(d), f(p), o));
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
        !t && !me(r) && !it(r) && (r = k(r));
        const i = k(this);
        return Vt(i).has.call(i, r) || (i.add(r), Oe(i, "add", r, r)), this;
      },
      set(r, i) {
        !t && !me(i) && !it(i) && (i = k(i));
        const o = k(this), { has: l, get: a } = Vt(o);
        let f = l.call(o, r);
        f || (r = k(r), f = l.call(o, r));
        const d = a.call(o, r);
        return o.set(r, i), f ? Be(i, d) && Oe(o, "set", r, i) : Oe(o, "add", r, i), this;
      },
      delete(r) {
        const i = k(this), { has: o, get: l } = Vt(i);
        let a = o.call(i, r);
        a || (r = k(r), a = o.call(i, r)), l && l.call(i, r);
        const f = i.delete(r);
        return a && Oe(i, "delete", r, void 0), f;
      },
      clear() {
        const r = k(this), i = r.size !== 0, o = r.clear();
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
    s[r] = Mi(r, e, t);
  }), s;
}
function Zs(e, t) {
  const s = Pi(e, t);
  return (n, r, i) => r === "__v_isReactive" ? !e : r === "__v_isReadonly" ? e : r === "__v_raw" ? n : Reflect.get(
    L(s, r) && r in n ? s : n,
    r,
    i
  );
}
const Oi = {
  get: /* @__PURE__ */ Zs(!1, !1)
}, Di = {
  get: /* @__PURE__ */ Zs(!1, !0)
}, Fi = {
  get: /* @__PURE__ */ Zs(!0, !1)
};
const fr = /* @__PURE__ */ new WeakMap(), dr = /* @__PURE__ */ new WeakMap(), hr = /* @__PURE__ */ new WeakMap(), Ni = /* @__PURE__ */ new WeakMap();
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
function Li(e) {
  return e.__v_skip || !Object.isExtensible(e) ? 0 : ki(ai(e));
}
function Qs(e) {
  return it(e) ? e : en(
    e,
    !1,
    Ei,
    Oi,
    fr
  );
}
function Hi(e) {
  return en(
    e,
    !1,
    Ri,
    Di,
    dr
  );
}
function pr(e) {
  return en(
    e,
    !0,
    Ti,
    Fi,
    hr
  );
}
function en(e, t, s, n, r) {
  if (!J(e) || e.__v_raw && !(t && e.__v_isReactive))
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
function ht(e) {
  return it(e) ? ht(e.__v_raw) : !!(e && e.__v_isReactive);
}
function it(e) {
  return !!(e && e.__v_isReadonly);
}
function me(e) {
  return !!(e && e.__v_isShallow);
}
function tn(e) {
  return e ? !!e.__v_raw : !1;
}
function k(e) {
  const t = e && e.__v_raw;
  return t ? k(t) : e;
}
function ji(e) {
  return !L(e, "__v_skip") && Object.isExtensible(e) && Yn(e, "__v_skip", !0), e;
}
const se = (e) => J(e) ? Qs(e) : e, Ds = (e) => J(e) ? pr(e) : e;
function ne(e) {
  return e ? e.__v_isRef === !0 : !1;
}
function ut(e) {
  return gr(e, !1);
}
function Bi(e) {
  return gr(e, !0);
}
function gr(e, t) {
  return ne(e) ? e : new Wi(e, t);
}
class Wi {
  constructor(t, s) {
    this.dep = new Xs(), this.__v_isRef = !0, this.__v_isShallow = !1, this._rawValue = s ? t : k(t), this._value = s ? t : se(t), this.__v_isShallow = s;
  }
  get value() {
    return this.dep.track(), this._value;
  }
  set value(t) {
    const s = this._rawValue, n = this.__v_isShallow || me(t) || it(t);
    t = n ? t : k(t), Be(t, s) && (this._rawValue = t, this._value = n ? t : se(t), this.dep.trigger());
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
function mr(e) {
  return ht(e) ? e : new Proxy(e, Ui);
}
class Vi {
  constructor(t, s, n) {
    this.fn = t, this.setter = s, this._value = void 0, this.dep = new Xs(this), this.__v_isRef = !0, this.deps = void 0, this.depsTail = void 0, this.flags = 16, this.globalVersion = Mt - 1, this.next = void 0, this.effect = this, this.__v_isReadonly = !s, this.isSSR = n;
  }
  /**
   * @internal
   */
  notify() {
    if (this.flags |= 16, !(this.flags & 8) && // avoid infinite self recursion
    V !== this)
      return sr(this, !0), !0;
  }
  get value() {
    const t = this.dep.track();
    return ir(this), t && (t.version = this.dep.version), this._value;
  }
  set value(t) {
    this.setter && this.setter(t);
  }
}
function Ki(e, t, s = !1) {
  let n, r;
  return P(e) ? n = e : (n = e.get, r = e.set), new Vi(n, r, s);
}
const Gt = {}, Zt = /* @__PURE__ */ new WeakMap();
let Qe;
function Gi(e, t = !1, s = Qe) {
  if (s) {
    let n = Zt.get(s);
    n || Zt.set(s, n = []), n.push(e);
  }
}
function qi(e, t, s = K) {
  const { immediate: n, deep: r, once: i, scheduler: o, augmentJob: l, call: a } = s, f = (E) => r ? E : me(E) || r === !1 || r === 0 ? je(E, 1) : je(E);
  let d, p, m, x, M = !1, C = !1;
  if (ne(e) ? (p = () => e.value, M = me(e)) : ht(e) ? (p = () => f(e), M = !0) : R(e) ? (C = !0, M = e.some((E) => ht(E) || me(E)), p = () => e.map((E) => {
    if (ne(E))
      return E.value;
    if (ht(E))
      return f(E);
    if (P(E))
      return a ? a(E, 2) : E();
  })) : P(e) ? t ? p = a ? () => a(e, 2) : e : p = () => {
    if (m) {
      Ke();
      try {
        m();
      } finally {
        Ge();
      }
    }
    const E = Qe;
    Qe = d;
    try {
      return a ? a(e, 3, [x]) : e(x);
    } finally {
      Qe = E;
    }
  } : p = Te, t && r) {
    const E = p, ee = r === !0 ? 1 / 0 : r;
    p = () => je(E(), ee);
  }
  const G = yi(), N = () => {
    d.stop(), G && G.active && Gs(G.effects, d);
  };
  if (i && t) {
    const E = t;
    t = (...ee) => {
      E(...ee), N();
    };
  }
  let z = C ? new Array(e.length).fill(Gt) : Gt;
  const Y = (E) => {
    if (!(!(d.flags & 1) || !d.dirty && !E))
      if (t) {
        const ee = d.run();
        if (r || M || (C ? ee.some((Fe, we) => Be(Fe, z[we])) : Be(ee, z))) {
          m && m();
          const Fe = Qe;
          Qe = d;
          try {
            const we = [
              ee,
              // pass undefined as the old value when it's changed for the first time
              z === Gt ? void 0 : C && z[0] === Gt ? [] : z,
              x
            ];
            a ? a(t, 3, we) : (
              // @ts-expect-error
              t(...we)
            ), z = ee;
          } finally {
            Qe = Fe;
          }
        }
      } else
        d.run();
  };
  return l && l(Y), d = new er(p), d.scheduler = o ? () => o(Y, !1) : Y, x = (E) => Gi(E, !1, d), m = d.onStop = () => {
    const E = Zt.get(d);
    if (E) {
      if (a)
        a(E, 4);
      else
        for (const ee of E) ee();
      Zt.delete(d);
    }
  }, t ? n ? Y(!0) : z = d.run() : o ? o(Y.bind(null, !0), !0) : d.run(), N.pause = d.pause.bind(d), N.resume = d.resume.bind(d), N.stop = N, N;
}
function je(e, t = 1 / 0, s) {
  if (t <= 0 || !J(e) || e.__v_skip || (s = s || /* @__PURE__ */ new Set(), s.has(e)))
    return e;
  if (s.add(e), t--, ne(e))
    je(e.value, t, s);
  else if (R(e))
    for (let n = 0; n < e.length; n++)
      je(e[n], t, s);
  else if (Kn(e) || dt(e))
    e.forEach((n) => {
      je(n, t, s);
    });
  else if (Jn(e)) {
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
function Re(e, t, s, n) {
  if (P(e)) {
    const r = kt(e, t, s, n);
    return r && Gn(r) && r.catch((i) => {
      fs(i, t, s);
    }), r;
  }
  if (R(e)) {
    const r = [];
    for (let i = 0; i < e.length; i++)
      r.push(Re(e[i], t, s, n));
    return r;
  }
}
function fs(e, t, s, n = !0) {
  const r = t ? t.vnode : null, { errorHandler: i, throwUnhandledErrorInProduction: o } = t && t.appContext.config || K;
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
      Ke(), kt(i, null, 10, [
        e,
        a,
        f
      ]), Ge();
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
const pt = [];
let ke = null, at = 0;
const _r = /* @__PURE__ */ Promise.resolve();
let Qt = null;
function br(e) {
  const t = Qt || _r;
  return e ? t.then(this ? e.bind(this) : e) : t;
}
function zi(e) {
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
    !(e.flags & 2) && t >= Ot(s) ? le.push(e) : le.splice(zi(t), 0, e), e.flags |= 1, wr();
  }
}
function wr() {
  Qt || (Qt = _r.then(vr));
}
function Yi(e) {
  R(e) ? pt.push(...e) : ke && e.id === -1 ? ke.splice(at + 1, 0, e) : e.flags & 1 || (pt.push(e), e.flags |= 1), wr();
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
function yr(e) {
  if (pt.length) {
    const t = [...new Set(pt)].sort(
      (s, n) => Ot(s) - Ot(n)
    );
    if (pt.length = 0, ke) {
      ke.push(...t);
      return;
    }
    for (ke = t, at = 0; at < ke.length; at++) {
      const s = ke[at];
      s.flags & 4 && (s.flags &= -2), s.flags & 8 || s(), s.flags &= -2;
    }
    ke = null, at = 0;
  }
}
const Ot = (e) => e.id == null ? e.flags & 2 ? -1 : 1 / 0 : e.id;
function vr(e) {
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
    Ae = -1, le.length = 0, yr(), Qt = null, (le.length || pt.length) && vr();
  }
}
let Ee = null, xr = null;
function es(e) {
  const t = Ee;
  return Ee = e, xr = e && e.type.__scopeId || null, t;
}
function Xi(e, t = Ee, s) {
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
    a && (Ke(), Re(a, s, 8, [
      e.el,
      l,
      e,
      t
    ]), Ge());
  }
}
const Zi = Symbol("_vte"), Qi = (e) => e.__isTeleport;
function nn(e, t) {
  e.shapeFlag & 6 && e.component ? (e.transition = t, nn(e.component.subTree, t)) : e.shapeFlag & 128 ? (e.ssContent.transition = t.clone(e.ssContent), e.ssFallback.transition = t.clone(e.ssFallback)) : e.transition = t;
}
/*! #__NO_SIDE_EFFECTS__ */
// @__NO_SIDE_EFFECTS__
function qe(e, t) {
  return P(e) ? (
    // #8236: extend call and options.name access are considered side-effects
    // by Rollup, so we have to wrap it in a pure-annotated IIFE.
    re({ name: e.name }, t, { setup: e })
  ) : e;
}
function Sr(e) {
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
  if (Et(n) && !r) {
    n.shapeFlag & 512 && n.type.__asyncResolved && n.component.subTree.component && ts(e, t, s, n.component.subTree);
    return;
  }
  const i = n.shapeFlag & 4 ? cn(n.component) : n.el, o = r ? null : i, { i: l, r: a } = e, f = t && t.r, d = l.refs === K ? l.refs = {} : l.refs, p = l.setupState, m = k(p), x = p === K ? () => !1 : (M) => L(m, M);
  if (f != null && f !== a && (Q(f) ? (d[f] = null, x(f) && (p[f] = null)) : ne(f) && (f.value = null)), P(a))
    kt(a, l, 12, [o, d]);
  else {
    const M = Q(a), C = ne(a);
    if (M || C) {
      const G = () => {
        if (e.f) {
          const N = M ? x(a) ? p[a] : d[a] : a.value;
          r ? R(N) && Gs(N, i) : R(N) ? N.includes(i) || N.push(i) : M ? (d[a] = [i], x(a) && (p[a] = d[a])) : (a.value = [i], e.k && (d[e.k] = a.value));
        } else M ? (d[a] = o, x(a) && (p[a] = o)) : C && (a.value = o, e.k && (d[e.k] = o));
      };
      o ? (G.id = -1, de(G, s)) : G();
    }
  }
}
as().requestIdleCallback;
as().cancelIdleCallback;
const Et = (e) => !!e.type.__asyncLoader, Ir = (e) => e.type.__isKeepAlive;
function eo(e, t) {
  Ar(e, "a", t);
}
function to(e, t) {
  Ar(e, "da", t);
}
function Ar(e, t, s = ce) {
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
      Ir(r.parent.vnode) && so(n, t, s, r), r = r.parent;
  }
}
function so(e, t, s, n) {
  const r = ds(
    t,
    e,
    n,
    !0
    /* prepend */
  );
  $r(() => {
    Gs(n[t], r);
  }, s);
}
function ds(e, t, s = ce, n = !1) {
  if (s) {
    const r = s[e] || (s[e] = []), i = t.__weh || (t.__weh = (...o) => {
      Ke();
      const l = Lt(s), a = Re(t, s, e, o);
      return l(), Ge(), a;
    });
    return n ? r.unshift(i) : r.push(i), i;
  }
}
const De = (e) => (t, s = ce) => {
  (!Ft || e === "sp") && ds(e, (...n) => t(...n), s);
}, no = De("bm"), Cr = De("m"), ro = De(
  "bu"
), io = De("u"), rn = De(
  "bum"
), $r = De("um"), oo = De(
  "sp"
), lo = De("rtg"), co = De("rtc");
function Er(e, t = ce) {
  ds("ec", e, t);
}
const ao = Symbol.for("v-ndc");
function et(e, t, s, n) {
  let r;
  const i = s, o = R(e);
  if (o || Q(e)) {
    const l = o && ht(e);
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
  } else if (J(e))
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
const Fs = (e) => e ? Yr(e) ? cn(e) : Fs(e.parent) : null, Tt = (
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
    $options: (e) => Rr(e),
    $forceUpdate: (e) => e.f || (e.f = () => {
      sn(e.update);
    }),
    $nextTick: (e) => e.n || (e.n = br.bind(e.proxy)),
    $watch: (e) => Po.bind(e)
  })
), Ss = (e, t) => e !== K && !e.__isScriptSetup && L(e, t), uo = {
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
        if (r !== K && L(r, t))
          return o[t] = 2, r[t];
        if (
          // only cache other properties when instance has declared (thus stable)
          // props
          (f = e.propsOptions[0]) && L(f, t)
        )
          return o[t] = 3, i[t];
        if (s !== K && L(s, t))
          return o[t] = 4, s[t];
        Ns && (o[t] = 0);
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
    return Ss(r, t) ? (r[t] = s, !0) : n !== K && L(n, t) ? (n[t] = s, !0) : L(e.props, t) || t[0] === "$" && t.slice(1) in e ? !1 : (i[t] = s, !0);
  },
  has({
    _: { data: e, setupState: t, accessCache: s, ctx: n, appContext: r, propsOptions: i }
  }, o) {
    let l;
    return !!s[o] || e !== K && L(e, o) || Ss(t, o) || (l = i[0]) && L(l, o) || L(n, o) || L(Tt, o) || L(r.config.globalProperties, o);
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
function fo(e) {
  const t = Rr(e), s = e.proxy, n = e.ctx;
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
    deactivated: G,
    beforeDestroy: N,
    beforeUnmount: z,
    destroyed: Y,
    unmounted: E,
    render: ee,
    renderTracked: Fe,
    renderTriggered: we,
    errorCaptured: Ne,
    serverPrefetch: Ht,
    // public API
    expose: Je,
    inheritAttrs: _t,
    // assets
    components: jt,
    directives: Bt,
    filters: gs
  } = t;
  if (f && ho(f, n, null), o)
    for (const q in o) {
      const W = o[q];
      P(W) && (n[q] = W.bind(s));
    }
  if (r) {
    const q = r.call(s, s);
    J(q) && (e.data = Qs(q));
  }
  if (Ns = !0, i)
    for (const q in i) {
      const W = i[q], ze = P(W) ? W.bind(s, s) : P(W.get) ? W.get.bind(s, s) : Te, Wt = !P(W) && P(W.set) ? W.set.bind(s) : Te, Ye = rt({
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
      Tr(l[q], n, s, q);
  if (a) {
    const q = P(a) ? a.call(s) : a;
    Reflect.ownKeys(q).forEach((W) => {
      wo(W, q[W]);
    });
  }
  d && yn(d, e, "c");
  function ie(q, W) {
    R(W) ? W.forEach((ze) => q(ze.bind(s))) : W && q(W.bind(s));
  }
  if (ie(no, p), ie(Cr, m), ie(ro, x), ie(io, M), ie(eo, C), ie(to, G), ie(Er, Ne), ie(co, Fe), ie(lo, we), ie(rn, z), ie($r, E), ie(oo, Ht), R(Je))
    if (Je.length) {
      const q = e.exposed || (e.exposed = {});
      Je.forEach((W) => {
        Object.defineProperty(q, W, {
          get: () => s[W],
          set: (ze) => s[W] = ze
        });
      });
    } else e.exposed || (e.exposed = {});
  ee && e.render === Te && (e.render = ee), _t != null && (e.inheritAttrs = _t), jt && (e.components = jt), Bt && (e.directives = Bt), Ht && Sr(e);
}
function ho(e, t, s = Te) {
  R(e) && (e = ks(e));
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
  Re(
    R(e) ? e.map((n) => n.bind(t.proxy)) : e.bind(t.proxy),
    t,
    s
  );
}
function Tr(e, t, s, n) {
  let r = n.includes(".") ? Vr(s, n) : () => s[n];
  if (Q(e)) {
    const i = t[e];
    P(i) && zt(r, i);
  } else if (P(e))
    zt(r, e.bind(s));
  else if (J(e))
    if (R(e))
      e.forEach((i) => Tr(i, t, s, n));
    else {
      const i = P(e.handler) ? e.handler.bind(s) : t[e.handler];
      P(i) && zt(r, i, e);
    }
}
function Rr(e) {
  const t = e.type, { mixins: s, extends: n } = t, {
    mixins: r,
    optionsCache: i,
    config: { optionMergeStrategies: o }
  } = e.appContext, l = i.get(t);
  let a;
  return l ? a = l : !r.length && !s && !n ? a = t : (a = {}, r.length && r.forEach(
    (f) => ss(a, f, o, !0)
  ), ss(a, t, o)), J(t) && i.set(t, a), a;
}
function ss(e, t, s, n = !1) {
  const { mixins: r, extends: i } = t;
  i && ss(e, i, s, !0), r && r.forEach(
    (o) => ss(e, o, s, !0)
  );
  for (const o in t)
    if (!(n && o === "expose")) {
      const l = po[o] || s && s[o];
      e[o] = l ? l(e[o], t[o]) : t[o];
    }
  return e;
}
const po = {
  data: vn,
  props: xn,
  emits: xn,
  // objects
  methods: St,
  computed: St,
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
  components: St,
  directives: St,
  // watch
  watch: mo,
  // provide / inject
  provide: vn,
  inject: go
};
function vn(e, t) {
  return t ? e ? function() {
    return re(
      P(e) ? e.call(this, this) : e,
      P(t) ? t.call(this, this) : t
    );
  } : t : e;
}
function go(e, t) {
  return St(ks(e), ks(t));
}
function ks(e) {
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
function St(e, t) {
  return e ? re(/* @__PURE__ */ Object.create(null), e, t) : t;
}
function xn(e, t) {
  return e ? R(e) && R(t) ? [.../* @__PURE__ */ new Set([...e, ...t])] : re(
    /* @__PURE__ */ Object.create(null),
    wn(e),
    wn(t ?? {})
  ) : t;
}
function mo(e, t) {
  if (!e) return t;
  if (!t) return e;
  const s = re(/* @__PURE__ */ Object.create(null), e);
  for (const n in t)
    s[n] = oe(e[n], t[n]);
  return s;
}
function Mr() {
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
let _o = 0;
function bo(e, t) {
  return function(n, r = null) {
    P(n) || (n = re({}, n)), r != null && !J(r) && (r = null);
    const i = Mr(), o = /* @__PURE__ */ new WeakSet(), l = [];
    let a = !1;
    const f = i.app = {
      _uid: _o++,
      _component: n,
      _props: r,
      _container: null,
      _context: i,
      _instance: null,
      version: Zo,
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
        a && (Re(
          l,
          f._instance,
          16
        ), e(null, f._container), delete f._container.__vue_app__);
      },
      provide(d, p) {
        return i.provides[d] = p, f;
      },
      runWithContext(d) {
        const p = gt;
        gt = f;
        try {
          return d();
        } finally {
          gt = p;
        }
      }
    };
    return f;
  };
}
let gt = null;
function wo(e, t) {
  if (ce) {
    let s = ce.provides;
    const n = ce.parent && ce.parent.provides;
    n === s && (s = ce.provides = Object.create(n)), s[e] = t;
  }
}
function Jt(e, t, s = !1) {
  const n = ce || Ee;
  if (n || gt) {
    const r = gt ? gt._context.provides : n ? n.parent == null ? n.vnode.appContext && n.vnode.appContext.provides : n.parent.provides : void 0;
    if (r && e in r)
      return r[e];
    if (arguments.length > 1)
      return s && P(t) ? t.call(n && n.proxy) : t;
  }
}
const Pr = {}, Or = () => Object.create(Pr), Dr = (e) => Object.getPrototypeOf(e) === Pr;
function yo(e, t, s, n = !1) {
  const r = {}, i = Or();
  e.propsDefaults = /* @__PURE__ */ Object.create(null), Fr(e, t, r, i);
  for (const o in e.propsOptions[0])
    o in r || (r[o] = void 0);
  s ? e.props = n ? r : Hi(r) : e.type.props ? e.props = r : e.props = i, e.attrs = i;
}
function vo(e, t, s, n) {
  const {
    props: r,
    attrs: i,
    vnode: { patchFlag: o }
  } = e, l = k(r), [a] = e.propsOptions;
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
            r[M] = Ls(
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
    Fr(e, t, r, i) && (f = !0);
    let d;
    for (const p in l)
      (!t || // for camelCase
      !L(t, p) && // it's possible the original props was passed in as kebab-case
      // and converted to camelCase (#955)
      ((d = lt(p)) === p || !L(t, d))) && (a ? s && // for camelCase
      (s[p] !== void 0 || // for kebab-case
      s[d] !== void 0) && (r[p] = Ls(
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
  f && Oe(e.attrs, "set", "");
}
function Fr(e, t, s, n) {
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
    const a = k(s), f = l || K;
    for (let d = 0; d < i.length; d++) {
      const p = i[d];
      s[p] = Ls(
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
function Ls(e, t, s, n, r, i) {
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
          const d = Lt(r);
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
    ] && (n === "" || n === lt(s)) && (n = !0));
  }
  return n;
}
const xo = /* @__PURE__ */ new WeakMap();
function Nr(e, t, s = !1) {
  const n = s ? xo : t.propsCache, r = n.get(e);
  if (r)
    return r;
  const i = e.props, o = {}, l = [];
  let a = !1;
  if (!P(e)) {
    const d = (p) => {
      a = !0;
      const [m, x] = Nr(p, t, !0);
      re(o, m), x && l.push(...x);
    };
    !s && t.mixins.length && t.mixins.forEach(d), e.extends && d(e.extends), e.mixins && e.mixins.forEach(d);
  }
  if (!i && !a)
    return J(e) && n.set(e, ft), ft;
  if (R(i))
    for (let d = 0; d < i.length; d++) {
      const p = We(i[d]);
      Sn(p) && (o[p] = K);
    }
  else if (i)
    for (const d in i) {
      const p = We(d);
      if (Sn(p)) {
        const m = i[d], x = o[p] = R(m) || P(m) ? { type: m } : re({}, m), M = x.type;
        let C = !1, G = !0;
        if (R(M))
          for (let N = 0; N < M.length; ++N) {
            const z = M[N], Y = P(z) && z.name;
            if (Y === "Boolean") {
              C = !0;
              break;
            } else Y === "String" && (G = !1);
          }
        else
          C = P(M) && M.name === "Boolean";
        x[
          0
          /* shouldCast */
        ] = C, x[
          1
          /* shouldCastTrue */
        ] = G, (C || L(x, "default")) && l.push(p);
      }
    }
  const f = [o, l];
  return J(e) && n.set(e, f), f;
}
function Sn(e) {
  return e[0] !== "$" && !At(e);
}
const kr = (e) => e[0] === "_" || e === "$stable", on = (e) => R(e) ? e.map($e) : [$e(e)], So = (e, t, s) => {
  if (t._n)
    return t;
  const n = Xi((...r) => on(t(...r)), s);
  return n._c = !1, n;
}, Lr = (e, t, s) => {
  const n = e._ctx;
  for (const r in e) {
    if (kr(r)) continue;
    const i = e[r];
    if (P(i))
      t[r] = So(r, i, n);
    else if (i != null) {
      const o = on(i);
      t[r] = () => o;
    }
  }
}, Hr = (e, t) => {
  const s = on(t);
  e.slots.default = () => s;
}, jr = (e, t, s) => {
  for (const n in t)
    (s || n !== "_") && (e[n] = t[n]);
}, Io = (e, t, s) => {
  const n = e.slots = Or();
  if (e.vnode.shapeFlag & 32) {
    const r = t._;
    r ? (jr(n, t, s), s && Yn(n, "_", r, !0)) : Lr(t, n);
  } else t && Hr(e, t);
}, Ao = (e, t, s) => {
  const { vnode: n, slots: r } = e;
  let i = !0, o = K;
  if (n.shapeFlag & 32) {
    const l = t._;
    l ? s && l === 1 ? i = !1 : jr(r, t, s) : (i = !t.$stable, Lr(t, r)), o = t;
  } else t && (Hr(e, t), o = { default: 1 });
  if (i)
    for (const l in r)
      !kr(l) && o[l] == null && delete r[l];
}, de = Ho;
function Co(e) {
  return $o(e);
}
function $o(e, t) {
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
    c && !xt(c, u) && (b = Ut(c), ye(c, g, _, !0), c = null), u.patchFlag === -2 && (y = !1, u.dynamicChildren = null);
    const { type: w, ref: $, shapeFlag: I } = u;
    switch (w) {
      case ps:
        G(c, u, h, b);
        break;
      case ot:
        N(c, u, h, b);
        break;
      case As:
        c == null && z(u, h, b, S);
        break;
      case Z:
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
        I & 1 ? ee(
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
          wt
        );
    }
    $ != null && g && ts($, c && c.ref, _, u || c, !u);
  }, G = (c, u, h, b) => {
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
  }, N = (c, u, h, b) => {
    c == null ? n(
      u.el = a(u.children || ""),
      h,
      b
    ) : u.el = c.el;
  }, z = (c, u, h, b) => {
    [c.el, c.anchor] = M(
      c.children,
      u,
      h,
      b,
      c.el,
      c.anchor
    );
  }, Y = ({ el: c, anchor: u }, h, b) => {
    let g;
    for (; c && c !== u; )
      g = m(c), n(c, h, b), c = g;
    n(u, h, b);
  }, E = ({ el: c, anchor: u }) => {
    let h;
    for (; c && c !== u; )
      h = m(c), r(c), c = h;
    r(u);
  }, ee = (c, u, h, b, g, _, S, v, y) => {
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
    const { props: $, shapeFlag: I, transition: A, dirs: T } = c;
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
    ), T && Xe(c, null, b, "created"), we(y, c, c.scopeId, S, b), $) {
      for (const U in $)
        U !== "value" && !At(U) && i(y, U, null, $[U], _, b);
      "value" in $ && i(y, "value", null, $.value, _), (w = $.onVnodeBeforeMount) && Ie(w, b, c);
    }
    T && Xe(c, null, b, "beforeMount");
    const D = Eo(g, A);
    D && A.beforeEnter(y), n(y, u, h), ((w = $ && $.onVnodeMounted) || D || T) && de(() => {
      w && Ie(w, b, c), D && A.enter(y), T && Xe(c, null, b, "mounted");
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
      const $ = c[w] = v ? Le(c[w]) : $e(c[w]);
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
    const I = c.props || K, A = u.props || K;
    let T;
    if (h && Ze(h, !1), (T = A.onVnodeBeforeUpdate) && Ie(T, h, u, c), $ && Xe(u, c, h, "beforeUpdate"), h && Ze(h, !0), (I.innerHTML && A.innerHTML == null || I.textContent && A.textContent == null) && d(v, ""), w ? Je(
      c.dynamicChildren,
      w,
      v,
      h,
      b,
      Is(u, g),
      _
    ) : S || W(
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
        _t(v, I, A, h, g);
      else if (y & 2 && I.class !== A.class && i(v, "class", null, A.class, g), y & 4 && i(v, "style", I.style, A.style, g), y & 8) {
        const D = u.dynamicProps;
        for (let U = 0; U < D.length; U++) {
          const H = D[U], ue = I[H], ae = A[H];
          (ae !== ue || H === "value") && i(v, H, ue, ae, g, h);
        }
      }
      y & 1 && c.children !== u.children && d(v, u.children);
    } else !S && w == null && _t(v, I, A, h, g);
    ((T = A.onVnodeUpdated) || $) && de(() => {
      T && Ie(T, h, u, c), $ && Xe(u, c, h, "updated");
    }, b);
  }, Je = (c, u, h, b, g, _, S) => {
    for (let v = 0; v < u.length; v++) {
      const y = c[v], w = u[v], $ = (
        // oldVNode may be an errored async setup() component inside Suspense
        // which will not have a mounted element
        y.el && // - In the case of a Fragment, we need to provide the actual parent
        // of the Fragment itself so it can move its children.
        (y.type === Z || // - In the case of different nodes, there is going to be a replacement
        // which also requires the correct parent container
        !xt(y, w) || // - In the case of a component, it could contain anything.
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
  }, _t = (c, u, h, b, g) => {
    if (u !== h) {
      if (u !== K)
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
    let { patchFlag: I, dynamicChildren: A, slotScopeIds: T } = u;
    T && (v = v ? v.concat(T) : T), c == null ? (n(w, h, b), n($, h, b), Ne(
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
    (u.key != null || g && u === g.subTree) && Br(
      c,
      u,
      !0
      /* shallow */
    )) : W(
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
    if (Ir(c) && (v.ctx.renderer = wt), qo(v, !1, S), v.asyncDep) {
      if (g && g.registerDep(v, ie, S), !c.el) {
        const y = v.subTree = be(ot);
        N(null, y, u, h);
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
        let { next: I, bu: A, u: T, parent: D, vnode: U } = c;
        {
          const xe = Wr(c);
          if (xe) {
            I && (I.el = U.el, q(c, I, S)), xe.asyncDep.then(() => {
              c.isUnmounted || v();
            });
            return;
          }
        }
        let H = I, ue;
        Ze(c, !1), I ? (I.el = U.el, q(c, I, S)) : I = U, A && bs(A), (ue = I.props && I.props.onVnodeBeforeUpdate) && Ie(ue, D, I, U), Ze(c, !0);
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
        ), I.el = ae.el, H === null && Lo(c, ae.el), T && de(T, g), (ue = I.props && I.props.onVnodeUpdated) && de(
          () => Ie(ue, D, I, U),
          g
        );
      } else {
        let I;
        const { el: A, props: T } = u, { bm: D, m: U, parent: H, root: ue, type: ae } = c, ve = Et(u);
        Ze(c, !1), D && bs(D), !ve && (I = T && T.onVnodeBeforeMount) && Ie(I, H, u), Ze(c, !0);
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
        if (U && de(U, g), !ve && (I = T && T.onVnodeMounted)) {
          const xe = u;
          de(
            () => Ie(I, H, xe),
            g
          );
        }
        (u.shapeFlag & 256 || H && Et(H.vnode) && H.vnode.shapeFlag & 256) && c.a && de(c.a, g), c.isMounted = !0, u = h = b = null;
      }
    };
    c.scope.on();
    const y = c.effect = new er(v);
    c.scope.off();
    const w = c.update = y.run.bind(y), $ = c.job = y.runIfDirty.bind(y);
    $.i = c, $.id = c.uid, y.scheduler = () => sn($), Ze(c, !0), w();
  }, q = (c, u, h) => {
    u.component = c;
    const b = c.vnode.props;
    c.vnode = u, c.next = null, vo(c, u.props, b, h), Ao(c, u.children, h), Ke(), bn(c), Ge();
  }, W = (c, u, h, b, g, _, S, v, y = !1) => {
    const w = c && c.children, $ = c ? c.shapeFlag : 0, I = u.children, { patchFlag: A, shapeFlag: T } = u;
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
    T & 8 ? ($ & 16 && bt(w, g, _), I !== w && d(h, I)) : $ & 16 ? T & 16 ? Wt(
      w,
      I,
      h,
      b,
      g,
      _,
      S,
      v,
      y
    ) : bt(w, g, _, !0) : ($ & 8 && d(h, ""), T & 16 && Ne(
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
    c = c || ft, u = u || ft;
    const w = c.length, $ = u.length, I = Math.min(w, $);
    let A;
    for (A = 0; A < I; A++) {
      const T = u[A] = y ? Le(u[A]) : $e(u[A]);
      C(
        c[A],
        T,
        h,
        null,
        g,
        _,
        S,
        v,
        y
      );
    }
    w > $ ? bt(
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
      const T = c[w], D = u[w] = y ? Le(u[w]) : $e(u[w]);
      if (xt(T, D))
        C(
          T,
          D,
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
      const T = c[I], D = u[A] = y ? Le(u[A]) : $e(u[A]);
      if (xt(T, D))
        C(
          T,
          D,
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
        const T = A + 1, D = T < $ ? u[T].el : b;
        for (; w <= A; )
          C(
            null,
            u[w] = y ? Le(u[w]) : $e(u[w]),
            h,
            D,
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
      const T = w, D = w, U = /* @__PURE__ */ new Map();
      for (w = D; w <= A; w++) {
        const fe = u[w] = y ? Le(u[w]) : $e(u[w]);
        fe.key != null && U.set(fe.key, w);
      }
      let H, ue = 0;
      const ae = A - D + 1;
      let ve = !1, xe = 0;
      const yt = new Array(ae);
      for (w = 0; w < ae; w++) yt[w] = 0;
      for (w = T; w <= I; w++) {
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
            if (yt[H - D] === 0 && xt(fe, u[H])) {
              Se = H;
              break;
            }
        Se === void 0 ? ye(fe, g, _, !0) : (yt[Se - D] = w + 1, Se >= xe ? xe = Se : ve = !0, C(
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
      const hn = ve ? To(yt) : ft;
      for (H = hn.length - 1, w = ae - 1; w >= 0; w--) {
        const fe = D + w, Se = u[fe], pn = fe + 1 < $ ? u[fe + 1].el : b;
        yt[w] === 0 ? C(
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
      S.move(c, u, h, wt);
      return;
    }
    if (S === Z) {
      n(_, u, h);
      for (let I = 0; I < y.length; I++)
        Ye(y[I], u, h, b);
      n(c.anchor, u, h);
      return;
    }
    if (S === As) {
      Y(c, u, h);
      return;
    }
    if (b !== 2 && w & 1 && v)
      if (b === 0)
        v.beforeEnter(_), n(_, u, h), de(() => v.enter(_), g);
      else {
        const { leave: I, delayLeave: A, afterLeave: T } = v, D = () => n(_, u, h), U = () => {
          I(_, () => {
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
      props: S,
      ref: v,
      children: y,
      dynamicChildren: w,
      shapeFlag: $,
      patchFlag: I,
      dirs: A,
      cacheIndex: T
    } = c;
    if (I === -2 && (g = !1), v != null && ts(v, null, h, c, !0), T != null && (u.renderCache[T] = void 0), $ & 256) {
      u.ctx.deactivate(c);
      return;
    }
    const D = $ & 1 && A, U = !Et(c);
    let H;
    if (U && (H = S && S.onVnodeBeforeUnmount) && Ie(H, u, c), $ & 6)
      ri(c.component, h, b);
    else {
      if ($ & 128) {
        c.suspense.unmount(h, b);
        return;
      }
      D && Xe(c, null, u, "beforeUnmount"), $ & 64 ? c.type.remove(
        c,
        u,
        h,
        wt,
        b
      ) : w && // #5154
      // when v-once is used inside a block, setBlockTracking(-1) marks the
      // parent block with hasOnce: true
      // so that it doesn't take the fast path during unmount - otherwise
      // components nested in v-once are never unmounted.
      !w.hasOnce && // #1153: fast path should not be taken for non-stable (v-for) fragments
      (_ !== Z || I > 0 && I & 64) ? bt(
        w,
        u,
        h,
        !1,
        !0
      ) : (_ === Z && I & 384 || !g && $ & 16) && bt(y, u, h), b && fn(c);
    }
    (U && (H = S && S.onVnodeUnmounted) || D) && de(() => {
      H && Ie(H, u, c), D && Xe(c, null, u, "unmounted");
    }, h);
  }, fn = (c) => {
    const { type: u, el: h, anchor: b, transition: g } = c;
    if (u === Z) {
      ni(h, b);
      return;
    }
    if (u === As) {
      E(c);
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
  }, ni = (c, u) => {
    let h;
    for (; c !== u; )
      h = m(c), r(c), c = h;
    r(u);
  }, ri = (c, u, h) => {
    const { bum: b, scope: g, job: _, subTree: S, um: v, m: y, a: w } = c;
    In(y), In(w), b && bs(b), g.stop(), _ && (_.flags |= 8, ye(S, c, u, h)), v && de(v, u), de(() => {
      c.isUnmounted = !0;
    }, u), u && u.pendingBranch && !u.isUnmounted && c.asyncDep && !c.asyncResolved && c.suspenseId === u.pendingId && (u.deps--, u.deps === 0 && u.resolve());
  }, bt = (c, u, h, b = !1, g = !1, _ = 0) => {
    for (let S = _; S < c.length; S++)
      ye(c[S], u, h, b, g);
  }, Ut = (c) => {
    if (c.shapeFlag & 6)
      return Ut(c.component.subTree);
    if (c.shapeFlag & 128)
      return c.suspense.next();
    const u = m(c.anchor || c.el), h = u && u[Zi];
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
    ), u._vnode = c, ms || (ms = !0, bn(), yr(), ms = !1);
  }, wt = {
    p: C,
    um: ye,
    m: Ye,
    r: fn,
    mt: gs,
    mc: Ne,
    pc: W,
    pbc: Je,
    n: Ut,
    o: e
  };
  return {
    render: dn,
    hydrate: void 0,
    createApp: bo(dn)
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
function Br(e, t, s = !1) {
  const n = e.children, r = t.children;
  if (R(n) && R(r))
    for (let i = 0; i < n.length; i++) {
      const o = n[i];
      let l = r[i];
      l.shapeFlag & 1 && !l.dynamicChildren && ((l.patchFlag <= 0 || l.patchFlag === 32) && (l = r[i] = Le(r[i]), l.el = o.el), !s && l.patchFlag !== -2 && Br(o, l)), l.type === ps && (l.el = o.el);
    }
}
function To(e) {
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
function Wr(e) {
  const t = e.subTree.component;
  if (t)
    return t.asyncDep && !t.asyncResolved ? t : Wr(t);
}
function In(e) {
  if (e)
    for (let t = 0; t < e.length; t++)
      e[t].flags |= 8;
}
const Ro = Symbol.for("v-scx"), Mo = () => Jt(Ro);
function zt(e, t, s) {
  return Ur(e, t, s);
}
function Ur(e, t, s = K) {
  const { immediate: n, deep: r, flush: i, once: o } = s, l = re({}, s), a = t && n || !t && i !== "post";
  let f;
  if (Ft) {
    if (i === "sync") {
      const x = Mo();
      f = x.__watcherHandles || (x.__watcherHandles = []);
    } else if (!a) {
      const x = () => {
      };
      return x.stop = Te, x.resume = Te, x.pause = Te, x;
    }
  }
  const d = ce;
  l.call = (x, M, C) => Re(x, d, M, C);
  let p = !1;
  i === "post" ? l.scheduler = (x) => {
    de(x, d && d.suspense);
  } : i !== "sync" && (p = !0, l.scheduler = (x, M) => {
    M ? x() : sn(x);
  }), l.augmentJob = (x) => {
    t && (x.flags |= 4), p && (x.flags |= 2, d && (x.id = d.uid, x.i = d));
  };
  const m = qi(e, t, l);
  return Ft && (f ? f.push(m) : a && m()), m;
}
function Po(e, t, s) {
  const n = this.proxy, r = Q(e) ? e.includes(".") ? Vr(n, e) : () => n[e] : e.bind(n, n);
  let i;
  P(t) ? i = t : (i = t.handler, s = t);
  const o = Lt(this), l = Ur(r, i.bind(n), s);
  return o(), l;
}
function Vr(e, t) {
  const s = t.split(".");
  return () => {
    let n = e;
    for (let r = 0; r < s.length && n; r++)
      n = n[s[r]];
    return n;
  };
}
const Oo = (e, t) => t === "modelValue" || t === "model-value" ? e.modelModifiers : e[`${t}Modifiers`] || e[`${We(t)}Modifiers`] || e[`${lt(t)}Modifiers`];
function Do(e, t, ...s) {
  if (e.isUnmounted) return;
  const n = e.vnode.props || K;
  let r = s;
  const i = t.startsWith("update:"), o = i && Oo(n, t.slice(7));
  o && (o.trim && (r = s.map((d) => Q(d) ? d.trim() : d)), o.number && (r = s.map(di)));
  let l, a = n[l = _s(t)] || // also try camelCase event handler (#2249)
  n[l = _s(We(t))];
  !a && i && (a = n[l = _s(lt(t))]), a && Re(
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
    e.emitted[l] = !0, Re(
      f,
      e,
      6,
      r
    );
  }
}
function Kr(e, t, s = !1) {
  const n = t.emitsCache, r = n.get(e);
  if (r !== void 0)
    return r;
  const i = e.emits;
  let o = {}, l = !1;
  if (!P(e)) {
    const a = (f) => {
      const d = Kr(f, t, !0);
      d && (l = !0, re(o, d));
    };
    !s && t.mixins.length && t.mixins.forEach(a), e.extends && a(e.extends), e.mixins && e.mixins.forEach(a);
  }
  return !i && !l ? (J(e) && n.set(e, null), null) : (R(i) ? i.forEach((a) => o[a] = null) : re(o, i), J(e) && n.set(e, o), o);
}
function hs(e, t) {
  return !e || !os(t) ? !1 : (t = t.slice(2).replace(/Once$/, ""), L(e, t[0].toLowerCase() + t.slice(1)) || L(e, lt(t)) || L(e, t));
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
  } = e, G = es(e);
  let N, z;
  try {
    if (s.shapeFlag & 4) {
      const E = r || n, ee = E;
      N = $e(
        f.call(
          ee,
          E,
          d,
          p,
          x,
          m,
          M
        )
      ), z = l;
    } else {
      const E = t;
      N = $e(
        E.length > 1 ? E(
          p,
          { attrs: l, slots: o, emit: a }
        ) : E(
          p,
          null
        )
      ), z = t.props ? l : Fo(l);
    }
  } catch (E) {
    Rt.length = 0, fs(E, e, 1), N = be(ot);
  }
  let Y = N;
  if (z && C !== !1) {
    const E = Object.keys(z), { shapeFlag: ee } = Y;
    E.length && ee & 7 && (i && E.some(Ks) && (z = No(
      z,
      i
    )), Y = mt(Y, z, !1, !0));
  }
  return s.dirs && (Y = mt(Y, null, !1, !0), Y.dirs = Y.dirs ? Y.dirs.concat(s.dirs) : s.dirs), s.transition && nn(Y, s.transition), N = Y, es(G), N;
}
const Fo = (e) => {
  let t;
  for (const s in e)
    (s === "class" || s === "style" || os(s)) && ((t || (t = {}))[s] = e[s]);
  return t;
}, No = (e, t) => {
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
function Lo({ vnode: e, parent: t }, s) {
  for (; t; ) {
    const n = t.subTree;
    if (n.suspense && n.suspense.activeBranch === e && (n.el = e.el), n === e)
      (e = t.vnode).el = s, t = t.parent;
    else
      break;
  }
}
const Gr = (e) => e.__isSuspense;
function Ho(e, t) {
  t && t.pendingBranch ? R(e) ? t.effects.push(...e) : t.effects.push(e) : Yi(e);
}
const Z = Symbol.for("v-fgt"), ps = Symbol.for("v-txt"), ot = Symbol.for("v-cmt"), As = Symbol.for("v-stc"), Rt = [];
let ge = null;
function F(e = !1) {
  Rt.push(ge = e ? null : []);
}
function jo() {
  Rt.pop(), ge = Rt[Rt.length - 1] || null;
}
let Dt = 1;
function $n(e, t = !1) {
  Dt += e, e < 0 && ge && t && (ge.hasOnce = !0);
}
function qr(e) {
  return e.dynamicChildren = Dt > 0 ? ge || ft : null, jo(), Dt > 0 && ge && ge.push(e), e;
}
function B(e, t, s, n, r, i) {
  return qr(
    O(
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
  return qr(
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
function Jr(e) {
  return e ? e.__v_isVNode === !0 : !1;
}
function xt(e, t) {
  return e.type === t.type && e.key === t.key;
}
const zr = ({ key: e }) => e ?? null, Yt = ({
  ref: e,
  ref_key: t,
  ref_for: s
}) => (typeof e == "number" && (e = "" + e), e != null ? Q(e) || ne(e) || P(e) ? { i: Ee, r: e, k: t, f: !!s } : e : null);
function O(e, t = null, s = null, n = 0, r = null, i = e === Z ? 0 : 1, o = !1, l = !1) {
  const a = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e,
    props: t,
    key: t && zr(t),
    ref: t && Yt(t),
    scopeId: xr,
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
  return l ? (ln(a, s), i & 128 && e.normalize(a)) : s && (a.shapeFlag |= Q(s) ? 8 : 16), Dt > 0 && // avoid a block node from tracking itself
  !o && // has current parent block
  ge && // presence of a patch flag indicates this node needs patching on updates.
  // component nodes also should always be patched, because even if the
  // component doesn't need to update, it needs to persist the instance on to
  // the next vnode so that it can be properly unmounted later.
  (a.patchFlag > 0 || i & 6) && // the EVENTS flag is only for hydration and if it is the only flag, the
  // vnode should not be considered dynamic due to handler caching.
  a.patchFlag !== 32 && ge.push(a), a;
}
const be = Bo;
function Bo(e, t = null, s = null, n = 0, r = null, i = !1) {
  if ((!e || e === ao) && (e = ot), Jr(e)) {
    const l = mt(
      e,
      t,
      !0
      /* mergeRef: true */
    );
    return s && ln(l, s), Dt > 0 && !i && ge && (l.shapeFlag & 6 ? ge[ge.indexOf(e)] = l : ge.push(l)), l.patchFlag = -2, l;
  }
  if (Xo(e) && (e = e.__vccOpts), t) {
    t = Wo(t);
    let { class: l, style: a } = t;
    l && !Q(l) && (t.class = Ve(l)), J(a) && (tn(a) && !R(a) && (a = re({}, a)), t.style = pe(a));
  }
  const o = Q(e) ? 1 : Gr(e) ? 128 : Qi(e) ? 64 : J(e) ? 4 : P(e) ? 2 : 0;
  return O(
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
function Wo(e) {
  return e ? tn(e) || Dr(e) ? re({}, e) : e : null;
}
function mt(e, t, s = !1, n = !1) {
  const { props: r, ref: i, patchFlag: o, children: l, transition: a } = e, f = t ? Uo(r || {}, t) : r, d = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e.type,
    props: f,
    key: f && zr(f),
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
    ssContent: e.ssContent && mt(e.ssContent),
    ssFallback: e.ssFallback && mt(e.ssFallback),
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
function st(e = " ", t = 0) {
  return be(ps, null, e, t);
}
function Ce(e = "", t = !1) {
  return t ? (F(), tt(ot, null, e)) : be(ot, null, e);
}
function $e(e) {
  return e == null || typeof e == "boolean" ? be(ot) : R(e) ? be(
    Z,
    null,
    // #3666, avoid reference pollution when reusing vnode
    e.slice()
  ) : Jr(e) ? Le(e) : be(ps, null, String(e));
}
function Le(e) {
  return e.el === null && e.patchFlag !== -1 || e.memo ? e : mt(e);
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
      !r && !Dr(t) ? t._ctx = Ee : r === 3 && Ee && (Ee.slots._ === 1 ? t._ = 1 : (t._ = 2, e.patchFlag |= 1024));
    }
  else P(t) ? (t = { default: t, _ctx: Ee }, s = 32) : (t = String(t), n & 64 ? (s = 16, t = [st(t)]) : s = 8);
  e.children = t, e.shapeFlag |= s;
}
function Uo(...e) {
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
  Re(e, t, 7, [
    s,
    n
  ]);
}
const Vo = Mr();
let Ko = 0;
function Go(e, t, s) {
  const n = e.type, r = (t ? t.appContext : e.appContext) || Vo, i = {
    uid: Ko++,
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
    emitsOptions: Kr(n, r),
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
  return i.ctx = { _: i }, i.root = t ? t.root : i, i.emit = Do.bind(null, i), e.ce && e.ce(i), i;
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
const Lt = (e) => {
  const t = ce;
  return ns(e), e.scope.on(), () => {
    e.scope.off(), ns(t);
  };
}, En = () => {
  ce && ce.scope.off(), ns(null);
};
function Yr(e) {
  return e.vnode.shapeFlag & 4;
}
let Ft = !1;
function qo(e, t = !1, s = !1) {
  t && Hs(t);
  const { props: n, children: r } = e.vnode, i = Yr(e);
  yo(e, n, i, t), Io(e, r, s);
  const o = i ? Jo(e, t) : void 0;
  return t && Hs(!1), o;
}
function Jo(e, t) {
  const s = e.type;
  e.accessCache = /* @__PURE__ */ Object.create(null), e.proxy = new Proxy(e.ctx, uo);
  const { setup: n } = s;
  if (n) {
    Ke();
    const r = e.setupContext = n.length > 1 ? Yo(e) : null, i = Lt(e), o = kt(
      n,
      e,
      0,
      [
        e.props,
        r
      ]
    ), l = Gn(o);
    if (Ge(), i(), (l || e.sp) && !Et(e) && Sr(e), l) {
      if (o.then(En, En), t)
        return o.then((a) => {
          Tn(e, a);
        }).catch((a) => {
          fs(a, e, 0);
        });
      e.asyncDep = o;
    } else
      Tn(e, o);
  } else
    Xr(e);
}
function Tn(e, t, s) {
  P(t) ? e.type.__ssrInlineRender ? e.ssrRender = t : e.render = t : J(t) && (e.setupState = mr(t)), Xr(e);
}
function Xr(e, t, s) {
  const n = e.type;
  e.render || (e.render = n.render || Te);
  {
    const r = Lt(e);
    Ke();
    try {
      fo(e);
    } finally {
      Ge(), r();
    }
  }
}
const zo = {
  get(e, t) {
    return te(e, "get", ""), e[t];
  }
};
function Yo(e) {
  const t = (s) => {
    e.exposed = s || {};
  };
  return {
    attrs: new Proxy(e.attrs, zo),
    slots: e.slots,
    emit: e.emit,
    expose: t
  };
}
function cn(e) {
  return e.exposed ? e.exposeProxy || (e.exposeProxy = new Proxy(mr(ji(e.exposed)), {
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
function Xo(e) {
  return P(e) && "__vccOpts" in e;
}
const rt = (e, t) => Ki(e, t, Ft), Zo = "3.5.13";
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
const Zr = js ? (e) => js.createHTML(e) : (e) => e, Qo = "http://www.w3.org/2000/svg", el = "http://www.w3.org/1998/Math/MathML", Pe = typeof document < "u" ? document : null, Mn = Pe && /* @__PURE__ */ Pe.createElement("template"), tl = {
  insert: (e, t, s) => {
    t.insertBefore(e, s || null);
  },
  remove: (e) => {
    const t = e.parentNode;
    t && t.removeChild(e);
  },
  createElement: (e, t, s, n) => {
    const r = t === "svg" ? Pe.createElementNS(Qo, e) : t === "mathml" ? Pe.createElementNS(el, e) : s ? Pe.createElement(e, { is: s }) : Pe.createElement(e);
    return e === "select" && n && n.multiple != null && r.setAttribute("multiple", n.multiple), r;
  },
  createText: (e) => Pe.createTextNode(e),
  createComment: (e) => Pe.createComment(e),
  setText: (e, t) => {
    e.nodeValue = t;
  },
  setElementText: (e, t) => {
    e.textContent = t;
  },
  parentNode: (e) => e.parentNode,
  nextSibling: (e) => e.nextSibling,
  querySelector: (e) => Pe.querySelector(e),
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
      Mn.innerHTML = Zr(
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
}, sl = Symbol("_vtc");
function nl(e, t, s) {
  const n = e[sl];
  n && (t = (t ? [t, ...n] : [...n]).join(" ")), t == null ? e.removeAttribute("class") : s ? e.setAttribute("class", t) : e.className = t;
}
const Pn = Symbol("_vod"), rl = Symbol("_vsh"), il = Symbol(""), ol = /(^|;)\s*display\s*:/;
function ll(e, t, s) {
  const n = e.style, r = Q(s);
  let i = !1;
  if (s && !r) {
    if (t)
      if (Q(t))
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
      const o = n[il];
      o && (s += ";" + o), n.cssText = s, i = ol.test(s);
    }
  } else t && e.removeAttribute("style");
  Pn in e && (e[Pn] = i ? n.display : "", e[rl] && (n.display = "none"));
}
const On = /\s*!important$/;
function Xt(e, t, s) {
  if (R(s))
    s.forEach((n) => Xt(e, t, n));
  else if (s == null && (s = ""), t.startsWith("--"))
    e.setProperty(t, s);
  else {
    const n = cl(e, t);
    On.test(s) ? e.setProperty(
      lt(n),
      s.replace(On, ""),
      "important"
    ) : e[n] = s;
  }
}
const Dn = ["Webkit", "Moz", "ms"], Cs = {};
function cl(e, t) {
  const s = Cs[t];
  if (s)
    return s;
  let n = We(t);
  if (n !== "filter" && n in e)
    return Cs[t] = n;
  n = zn(n);
  for (let r = 0; r < Dn.length; r++) {
    const i = Dn[r] + n;
    if (i in e)
      return Cs[t] = i;
  }
  return t;
}
const Fn = "http://www.w3.org/1999/xlink";
function Nn(e, t, s, n, r, i = bi(t)) {
  n && t.startsWith("xlink:") ? s == null ? e.removeAttributeNS(Fn, t.slice(6, t.length)) : e.setAttributeNS(Fn, t, s) : s == null || i && !Xn(s) ? e.removeAttribute(t) : e.setAttribute(
    t,
    i ? "" : Ue(s) ? String(s) : s
  );
}
function kn(e, t, s, n, r) {
  if (t === "innerHTML" || t === "textContent") {
    s != null && (e[t] = t === "innerHTML" ? Zr(s) : s);
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
    l === "boolean" ? s = Xn(s) : s == null && l === "string" ? (s = "", o = !0) : l === "number" && (s = 0, o = !0);
  }
  try {
    e[t] = s;
  } catch {
  }
  o && e.removeAttribute(r || t);
}
function al(e, t, s, n) {
  e.addEventListener(t, s, n);
}
function ul(e, t, s, n) {
  e.removeEventListener(t, s, n);
}
const Ln = Symbol("_vei");
function fl(e, t, s, n, r = null) {
  const i = e[Ln] || (e[Ln] = {}), o = i[t];
  if (n && o)
    o.value = n;
  else {
    const [l, a] = dl(t);
    if (n) {
      const f = i[t] = gl(
        n,
        r
      );
      al(e, l, f, a);
    } else o && (ul(e, l, o, a), i[t] = void 0);
  }
}
const Hn = /(?:Once|Passive|Capture)$/;
function dl(e) {
  let t;
  if (Hn.test(e)) {
    t = {};
    let n;
    for (; n = e.match(Hn); )
      e = e.slice(0, e.length - n[0].length), t[n[0].toLowerCase()] = !0;
  }
  return [e[2] === ":" ? e.slice(3) : lt(e.slice(2)), t];
}
let $s = 0;
const hl = /* @__PURE__ */ Promise.resolve(), pl = () => $s || (hl.then(() => $s = 0), $s = Date.now());
function gl(e, t) {
  const s = (n) => {
    if (!n._vts)
      n._vts = Date.now();
    else if (n._vts <= s.attached)
      return;
    Re(
      ml(n, s.value),
      t,
      5,
      [n]
    );
  };
  return s.value = e, s.attached = pl(), s;
}
function ml(e, t) {
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
e.charCodeAt(2) > 96 && e.charCodeAt(2) < 123, _l = (e, t, s, n, r, i) => {
  const o = r === "svg";
  t === "class" ? nl(e, n, o) : t === "style" ? ll(e, s, n) : os(t) ? Ks(t) || fl(e, t, s, n, i) : (t[0] === "." ? (t = t.slice(1), !0) : t[0] === "^" ? (t = t.slice(1), !1) : bl(e, t, n, o)) ? (kn(e, t, n), !e.tagName.includes("-") && (t === "value" || t === "checked" || t === "selected") && Nn(e, t, n, o, i, t !== "value")) : /* #11081 force set props for possible async custom element */ e._isVueCE && (/[A-Z]/.test(t) || !Q(n)) ? kn(e, We(t), n, i, t) : (t === "true-value" ? e._trueValue = n : t === "false-value" && (e._falseValue = n), Nn(e, t, n, o));
};
function bl(e, t, s, n) {
  if (n)
    return !!(t === "innerHTML" || t === "textContent" || t in e && jn(t) && P(s));
  if (t === "spellcheck" || t === "draggable" || t === "translate" || t === "form" || t === "list" && e.tagName === "INPUT" || t === "type" && e.tagName === "TEXTAREA")
    return !1;
  if (t === "width" || t === "height") {
    const r = e.tagName;
    if (r === "IMG" || r === "VIDEO" || r === "CANVAS" || r === "SOURCE")
      return !1;
  }
  return jn(t) && Q(s) ? !1 : t in e;
}
const wl = /* @__PURE__ */ re({ patchProp: _l }, tl);
let Bn;
function yl() {
  return Bn || (Bn = Co(wl));
}
const vl = (...e) => {
  const t = yl().createApp(...e), { mount: s } = t;
  return t.mount = (n) => {
    const r = Sl(n);
    if (!r) return;
    const i = t._component;
    !P(i) && !i.render && !i.template && (i.template = r.innerHTML), r.nodeType === 1 && (r.textContent = "");
    const o = s(r, !1, xl(r));
    return r instanceof Element && (r.removeAttribute("v-cloak"), r.setAttribute("data-v-app", "")), o;
  }, t;
};
function xl(e) {
  if (e instanceof SVGElement)
    return "svg";
  if (typeof MathMLElement == "function" && e instanceof MathMLElement)
    return "mathml";
}
function Sl(e) {
  return Q(e) ? document.querySelector(e) : e;
}
function Il(e, t, s) {
  return e.logs.filter((n) => {
    if (n.cursor <= s.get(n.runId)) return !1;
    if (t.mode === "all") return !0;
    if (n.runId !== t.runId) return !1;
    const r = e.runs[n.runId];
    return (n.phaseId && (r == null ? void 0 : r.instanceOfPhase[n.phaseId]) || n.instanceId || n.phaseId) === t.instanceId;
  });
}
function Al(e, t, s) {
  s.set(t, Math.max(s.get(t), e.maxCursor));
}
const Bs = "@runner", Wn = 5e3;
function Cl() {
  return { runs: {}, logs: [], seen: {}, maxCursor: 0 };
}
function Qr(e) {
  return e.outcome !== null || e.abandoned;
}
function $l(e) {
  return Object.values(e.phases).sort((t, s) => t.order - s.order);
}
function qt(e) {
  e.visible = $l(e).map((t) => t.instanceId);
}
function El(e, t, s) {
  e.visible = e.visible.map((n) => n === t ? s : n);
  for (const n of e.arrows)
    n.from === t && (n.from = s), n.to === t && (n.to = s);
}
const Tl = /* @__PURE__ */ new Set([
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
function Rl(e, t) {
  return t.phase_id && e.instanceOfPhase[t.phase_id] ? e.instanceOfPhase[t.phase_id] : t.instance_id || t.phase_id;
}
function Ml(e, t) {
  const s = t.instance_id, n = e.phases[t.phase_id], r = e.phases[s] ?? ei(t, s);
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
function Pl(e, t, s) {
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
function Ol(e, t) {
  if (!e || !t) return "";
  const s = Math.max(0, t - e);
  return s < 1e3 ? `${Math.round(s)} ms` : `${(s / 1e3).toFixed(1)}s`;
}
function Dl(e, t) {
  var i;
  const s = Date.parse(t.recorded_at) || 0, n = Rl(e, t);
  if (!n) return;
  let r;
  if (t.kind === "bound" ? r = Ml(e, t) : ((i = e.phases)[n] ?? (i[n] = ei(t, n)), r = e.phases[n]), t.attempt !== null && t.attempt !== void 0 && (r.attempt = t.attempt), Pl(e, t, r.instanceId), t.kind === "constructed" ? (r.constructed = !0, r.className = t.message) : t.kind === "purpose" ? r.purpose = t.message : t.kind === "cleanup" ? (r.cleanup = t.message, !r.started && r.outcome === null && (r.abandoned = !0)) : t.kind === "error" && (r.error = t.message), r.outcome !== null || r.abandoned) {
    qt(e);
    return;
  }
  if (t.kind === "phase_end" && t.status && t.status !== "running") {
    r.outcome = t.status, r.endedAt = s, r.started = !0, rs(
      e,
      t,
      r.instanceId,
      Bs,
      [t.status, Ol(r.startedAt, s), r.error].filter(Boolean).join(" · "),
      !0
    ), qt(e);
    return;
  }
  if (t.kind === "waiting" ? (r.waitDeadlineAt = t.deadline_at ? Date.parse(t.deadline_at) : null, r.waitReason = t.message, r.lastProgressAt = s) : Tl.has(t.kind) && (r.waitDeadlineAt = null, r.waitReason = "", r.lastProgressAt = s), (t.kind === "phase_start" || t.kind === "bound") && !r.started) {
    r.started = !0, r.startedAt = s, t.kind === "phase_start" && (r.phaseId = t.phase_id), rs(e, t, Bs, r.instanceId, r.name, !1), qt(e);
    return;
  }
  qt(e);
}
function Fl(e) {
  const t = [e.run_id, e.phase_name, e.kind].filter(Boolean).join(" ");
  return `${e.recorded_at} [${t}] ${e.message}`;
}
function Nl(e, t) {
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
    Dl(d, f), r.logs.push({
      cursor: f.cursor,
      eventId: f.event_id,
      runId: f.run_id,
      phaseId: f.phase_id,
      instanceId: f.instance_id,
      recordedAt: f.recorded_at,
      kind: f.kind,
      text: Fl(f)
    });
  }
  return r.logs.sort((f, d) => f.cursor - d.cursor), r.logs.length > Wn && r.logs.splice(0, r.logs.length - Wn), r;
}
const kl = {
  idle: "Idle -- no ADW run recorded yet",
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
function Ws(e, t) {
  if (!e) return "";
  const s = Math.max(0, Math.round((t - e) / 1e3));
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
}
function Ll(e, t, s, n, r, i) {
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
        terminal: Qr(e),
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
    statusLabel: ti[o],
    detail: l,
    purpose: e.purpose,
    selected: i
  };
}
const Hl = {
  running: "running",
  success: "pass",
  fail: "fail",
  interrupted: "stalled"
};
function jl(e, t) {
  const s = Hl[e.status] ?? "waiting", n = Date.parse(e.startedAt) || 0, r = e.endedAt && Date.parse(e.endedAt) || t;
  return {
    instanceId: Bs,
    kind: "runner",
    name: e.adwName,
    attempt: null,
    status: s,
    statusLabel: ti[s],
    detail: Ws(n, r),
    purpose: `ADW run ${e.runId}: starts each phase and receives its outcome`,
    selected: !1
  };
}
function Bl(e, t) {
  if (!e || !t) return "";
  const s = Math.max(0, t - e);
  return s >= 1e4 ? `+${(s / 1e3).toFixed(1)} s` : `+${s} ms`;
}
function Wl(e, t, s, n, r) {
  var p;
  if (!e) return { runId: "", columns: [], rows: [] };
  const i = e.visible.map((m) => e.phases[m]).filter(Boolean).map((m) => ({
    ...Ll(
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
  const o = [jl(e, t), ...i], l = new Map(
    o.map((m, x) => [m.instanceId, x])
  ), a = Date.parse(e.startedAt) || (((p = e.arrows[0]) == null ? void 0 : p.at) ?? 0), d = e.arrows.filter((m) => l.has(m.from) && l.has(m.to)).sort((m, x) => m.cursor - x.cursor).map((m) => ({
    id: m.id,
    from: l.get(m.from),
    to: l.get(m.to),
    text: m.text,
    dashed: m.dashed,
    kind: m.kind,
    elapsed: Bl(a, m.at)
  }));
  for (const m of o) {
    if (m.kind === "runner") {
      m.activeFrom = d.length ? 0 : null, m.activeTo = e.status === "running" ? null : d.length - 1;
      continue;
    }
    const x = l.get(m.instanceId), M = d.findIndex((N) => N.to === x || N.from === x), C = d.findIndex(
      (N) => N.kind === "phase_end" && N.from === x
    ), G = e.phases[m.instanceId];
    m.activeFrom = G != null && G.started && M >= 0 ? M : null, m.activeTo = C >= 0 ? C : null;
  }
  return { runId: e.runId, columns: o, rows: d };
}
function Ul(e) {
  const t = e.replace(/\.py$/, "").replace(/^adw_/, "").replace(/^(interface|op)_/, "").replace(/_/g, " ").trim();
  return t ? t[0].toUpperCase() + t.slice(1) : "An ADW";
}
function Vl(e) {
  if (!e) return "No ADW has run yet -- the next one started will show here";
  const t = Ul(e.adwName), s = e.visible.map((f) => e.phases[f]).filter(Boolean), n = s.length, i = s.filter((f) => f.started && !Qr(f)).at(-1), o = s.find((f) => f.outcome === "fail"), l = (f) => `step ${s.indexOf(f) + 1} of ${n}, ${f.name.replace(/_/g, " ")}`, a = (f) => `${f} step${f === 1 ? "" : "s"}`;
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
function Kl(e, t, s, n) {
  var i;
  const r = s.mode === "phase" ? (i = n.runs[s.runId]) == null ? void 0 : i.phases[s.instanceId] : void 0;
  return {
    headline: Vl(e),
    modeLabel: kl[t],
    filterLabel: s.mode === "all" ? "All events" : `Run ${s.runId} -- phase ${(r == null ? void 0 : r.name) ?? s.instanceId} (${s.instanceId}${r != null && r.attempt ? `, attempt ${r.attempt}` : ""})`,
    clearLabel: e ? `Clear displayed logs for ${e.runId}` : "Clear displayed logs",
    clearDisabledReason: e ? "" : "No ADW run is selected, so there is nothing run-scoped to clear."
  };
}
class Gl {
  constructor(t) {
    X(this, "state", Cl());
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
    this.selected.runId && (Al(this.state, this.selected.runId, this.deps.cleared), this.publish());
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
    if (this.state = Nl(this.state, t), !t.bootstrap && this.state !== s && t.events.length > 0) {
      const i = Date.parse(
        t.events[t.events.length - 1].recorded_at
      );
      Number.isNaN(i) || (this.lastDelayMs = Math.max(0, this.deps.clock.now() - i));
    }
    this.follow(this.deps.selection.select(this.selected, this.runs())), this.publish();
  }
  view() {
    const t = this.selected.runId ? this.state.runs[this.selected.runId] : void 0, s = this.deps.selection.mode(this.selected, this.runs()), n = this.filter.mode === "phase" && this.filter.runId === (t == null ? void 0 : t.runId) ? this.filter.instanceId : null, r = this.deps.renderer.render(
      Wl(
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
      lines: Il(this.state, this.filter, this.deps.cleared),
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
function ql(e, t) {
  return e.startedAt.localeCompare(t.startedAt) || e.runId.localeCompare(t.runId);
}
class Jl {
  select(t, s) {
    const n = [...s].sort(ql).at(-1);
    return n ? n.runId === t.runId ? t : { runId: n.runId, pinReleased: !1 } : { runId: null, pinReleased: !1 };
  }
  followLive(t, s) {
    return this.select(t, s);
  }
  mode(t, s) {
    const n = s.find((r) => r.runId === t.runId);
    return n ? n.status === "running" ? "live" : "completed" : "idle";
  }
}
function Es(e) {
  return `${Math.max(0, Math.round(e / 1e3))}s`;
}
class zl {
  evaluate(t, s, n) {
    if (!t.started || t.terminal) return null;
    if (t.waitDeadlineAt !== null) {
      const i = s - t.waitDeadlineAt;
      return i > 0 ? {
        reason: `wait deadline passed ${Es(i)} ago: ${t.waitReason}`
      } : null;
    }
    const r = s - t.lastProgressAt;
    return r > n ? {
      reason: `no progress for ${Es(r)} (timeout ${Es(n)})`
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
class Ql {
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
class ec {
  constructor(t) {
    this.node = t;
  }
  setVisible(t) {
    this.node && (this.node.style.display = t ? "" : "none");
  }
}
class tc {
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
const nc = { class: "adwdbg-log" }, rc = { class: "adwdbg-log-head" }, ic = { class: "adwdbg-log-label" }, oc = {
  key: 0,
  class: "adwdbg-log-empty"
}, lc = ["data-kind", "data-run"], cc = /* @__PURE__ */ qe({
  __name: "LogPane",
  props: {
    lines: {},
    label: {},
    tall: { type: Boolean }
  },
  setup(e) {
    const t = e, s = ut(null), n = ut(!0);
    function r() {
      const i = s.value;
      i && (n.value = i.scrollHeight - i.scrollTop - i.clientHeight <= 8);
    }
    return zt(() => t.lines.length, async () => {
      n.value && (await br(), s.value && (s.value.scrollTop = s.value.scrollHeight));
    }, { immediate: !0 }), (i, o) => (F(), B("div", nc, [
      O("div", rc, [
        O("span", ic, j(i.label), 1),
        O("span", null, j(i.lines.length) + " line" + j(i.lines.length === 1 ? "" : "s") + j(n.value ? "" : " · paused (scroll to bottom to follow)"), 1)
      ]),
      O("div", {
        ref_key: "host",
        ref: s,
        class: Ve(["adwdbg-log-lines", { "adwdbg-log-tall": i.tall }]),
        role: "log",
        onScroll: r
      }, [
        i.lines.length === 0 ? (F(), B("div", oc, "No ADW events to show.")) : Ce("", !0),
        (F(!0), B(Z, null, et(i.lines, (l) => (F(), B("div", {
          key: l.eventId,
          class: "adwdbg-log-line",
          "data-kind": l.kind,
          "data-run": l.runId
        }, j(l.text), 9, lc))), 128))
      ], 34)
    ]));
  }
}), It = 78, ac = 170, Nt = 40, an = 22, Ts = 11;
function Us(e, t) {
  return (e + 0.5) / Math.max(1, t) * 100;
}
function uc(e) {
  return 100 / Math.max(1, e);
}
function is(e) {
  return an + e * Nt + Nt * 0.62;
}
function si(e) {
  return an * 2 + Math.max(1, e) * Nt;
}
function fc(e, t, s) {
  const n = is(e) - Ts, r = t === null ? si(s) - an / 2 : is(Math.max(e, t)) + Ts;
  return { top: n, height: Math.max(Ts * 2, r - n) };
}
function dc(e, t) {
  return e === t ? "self" : e < t ? "right" : "left";
}
const hc = ["data-status"], pc = /* @__PURE__ */ qe({
  __name: "ActivationBar",
  props: {
    from: {},
    to: {},
    rows: {},
    status: {}
  },
  setup(e) {
    const t = e, s = rt(() => fc(t.from, t.to, t.rows));
    return (n, r) => (F(), B("span", {
      class: Ve(["sd-bar", { "sd-bar-open": n.to === null }]),
      "data-status": n.status,
      style: pe({ top: `${s.value.top}px`, height: `${s.value.height}px` })
    }, null, 14, hc));
  }
}), gc = ["data-lifeline"], mc = /* @__PURE__ */ qe({
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
      s[0] || (s[0] = O("span", { class: "sd-lifeline" }, null, -1)),
      t.column.activeFrom !== null && t.column.activeFrom !== void 0 ? (F(), tt(pc, {
        key: 0,
        from: t.column.activeFrom,
        to: t.column.activeTo ?? null,
        rows: t.rows,
        status: t.column.status
      }, null, 8, ["from", "to", "rows", "status"])) : Ce("", !0)
    ], 12, gc));
  }
}), _c = ["data-kind", "data-row"], bc = ["title"], wc = { class: "sd-label-text" }, yc = /* @__PURE__ */ qe({
  __name: "MessageArrow",
  props: {
    row: {},
    index: {},
    count: {}
  },
  setup(e) {
    const t = e, s = rt(() => dc(t.row.from, t.row.to)), n = rt(() => {
      const r = `${is(t.index) - Nt * 0.62}px`, i = `${Nt}px`, o = Us(t.row.from, t.count);
      if (s.value === "self") {
        const a = t.row.from === t.count - 1 ? 0.46 : 0.92;
        return { top: r, height: i, left: `${o}%`, width: `${uc(t.count) * a}%` };
      }
      const l = Us(t.row.to, t.count);
      return { top: r, height: i, left: `${Math.min(o, l)}%`, width: `${Math.abs(l - o)}%` };
    });
    return (r, i) => (F(), B("div", {
      class: Ve(["sd-message", [`sd-${s.value}`, { "sd-dashed": r.row.dashed }]]),
      "data-kind": r.row.kind,
      "data-row": r.index,
      style: pe(n.value)
    }, [
      O("div", {
        class: "sd-label",
        title: r.row.text
      }, [
        O("span", wc, j(r.row.text), 1)
      ], 8, bc),
      i[0] || (i[0] = O("div", { class: "sd-line" }, [
        O("span", { class: "sd-head" })
      ], -1))
    ], 14, _c));
  }
}), vc = ["data-status", "data-instance", "data-edge", "data-participant", "title", "aria-pressed"], xc = { class: "sd-name" }, Sc = { class: "sd-status" }, Vn = /* @__PURE__ */ qe({
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
      class: Ve(["sd-box", { "sd-selected": i.column.selected, "sd-runner": i.column.kind === "runner" }]),
      "data-status": i.column.status,
      "data-instance": i.column.instanceId,
      "data-edge": i.edge,
      "data-participant": i.column.kind ?? "phase",
      title: r(),
      "aria-pressed": i.column.selected,
      onClick: o[0] || (o[0] = (l) => n("select", i.column))
    }, [
      O("span", xc, [
        st(j(i.column.name), 1),
        i.column.attempt && i.column.attempt > 1 ? (F(), B(Z, { key: 0 }, [
          st(" · attempt " + j(i.column.attempt), 1)
        ], 64)) : Ce("", !0)
      ]),
      O("span", Sc, [
        st(j(i.column.statusLabel), 1),
        i.column.detail ? (F(), B(Z, { key: 0 }, [
          st(" · " + j(i.column.detail), 1)
        ], 64)) : Ce("", !0)
      ])
    ], 10, vc));
  }
}), Ic = /* @__PURE__ */ qe({
  __name: "TimeAxis",
  props: {
    rows: {}
  },
  setup(e) {
    return (t, s) => (F(), B("div", {
      class: "sd-axis",
      style: pe({ width: `${He(It)}px` }),
      "aria-hidden": "true"
    }, [
      (F(!0), B(Z, null, et(t.rows, (n, r) => (F(), B("span", {
        key: n.id,
        class: "sd-tick",
        style: pe({ top: `${He(is)(r)}px` })
      }, j(n.elapsed), 5))), 128))
    ], 4));
  }
}), Ac = { class: "sd" }, Cc = { class: "sd-tools" }, $c = { class: "sd-zoom-value" }, Ec = { class: "sd-hint" }, Tc = { class: "sd-frozen" }, Rc = /* @__PURE__ */ qe({
  __name: "SequenceDiagram",
  props: {
    model: {},
    hint: { default: "Click a phase box to filter the events below; click the ADW box for all events." }
  },
  emits: ["phase-click", "runner-click"],
  setup(e, { emit: t }) {
    const s = e, n = t, r = ut(1), i = ut(null), o = ut(null), l = ut(!1);
    let a = null;
    Cr(() => {
      typeof IntersectionObserver > "u" || !i.value || !o.value || (a = new IntersectionObserver(([x]) => {
        l.value = x.isIntersecting;
      }, { root: i.value }), a.observe(o.value));
    }), rn(() => a == null ? void 0 : a.disconnect());
    const f = rt(() => Math.max(1, s.model.columns.length)), d = rt(() => s.model.rows.length), p = rt(() => `${It + f.value * ac}px`);
    function m(x) {
      x.kind === "runner" ? n("runner-click") : n("phase-click", x.instanceId);
    }
    return (x, M) => (F(), B("div", Ac, [
      O("div", Cc, [
        O("button", {
          type: "button",
          class: "sd-zoom",
          "aria-label": "Zoom out",
          onClick: M[0] || (M[0] = (C) => r.value = Math.max(0.4, r.value - 0.1))
        }, "-"),
        O("span", $c, j(Math.round(r.value * 100)) + "%", 1),
        O("button", {
          type: "button",
          class: "sd-zoom",
          "aria-label": "Zoom in",
          onClick: M[1] || (M[1] = (C) => r.value = Math.min(2, r.value + 0.1))
        }, "+"),
        O("button", {
          type: "button",
          class: "sd-zoom",
          onClick: M[2] || (M[2] = (C) => r.value = 1)
        }, "Reset"),
        O("span", Ec, j(x.hint), 1)
      ]),
      O("div", {
        ref_key: "scroller",
        ref: i,
        class: "sd-scroll"
      }, [
        O("div", {
          class: "sd-canvas",
          style: pe({ zoom: r.value, minWidth: p.value })
        }, [
          O("div", Tc, [
            O("div", {
              class: Ve(["sd-titles sd-titles-top", { "sd-pinned": !l.value }]),
              style: pe({ paddingLeft: `${He(It)}px` })
            }, [
              (F(!0), B(Z, null, et(x.model.columns, (C) => (F(), tt(Vn, {
                key: C.instanceId,
                column: C,
                edge: "top",
                onSelect: m
              }, null, 8, ["column"]))), 128))
            ], 6),
            O("div", {
              class: "sd-body",
              style: pe({ height: `${He(si)(d.value)}px` })
            }, [
              be(Ic, {
                rows: x.model.rows
              }, null, 8, ["rows"]),
              O("div", {
                class: "sd-plot",
                style: pe({ left: `${He(It)}px` })
              }, [
                (F(!0), B(Z, null, et(x.model.columns, (C, G) => (F(), tt(mc, {
                  key: C.instanceId,
                  column: C,
                  centre: He(Us)(G, f.value),
                  rows: d.value
                }, null, 8, ["column", "centre", "rows"]))), 128)),
                (F(!0), B(Z, null, et(x.model.rows, (C, G) => (F(), tt(yc, {
                  key: C.id,
                  row: C,
                  index: G,
                  count: f.value
                }, null, 8, ["row", "index", "count"]))), 128))
              ], 4)
            ], 4)
          ]),
          O("div", {
            ref_key: "bottomRow",
            ref: o,
            class: "sd-titles sd-titles-bottom",
            style: pe({ marginLeft: `${He(It)}px` })
          }, [
            (F(!0), B(Z, null, et(x.model.columns, (C) => (F(), tt(Vn, {
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
  class: "adwdbg",
  "aria-label": "Live ADW sequence debugger"
}, Pc = { class: "adwdbg-head" }, Oc = ["title"], Dc = {
  "data-field": "adw",
  class: "adwdbg-note"
}, Fc = {
  "data-field": "run",
  class: "adwdbg-note"
}, Nc = ["data-run-status"], kc = ["data-mode"], Lc = {
  class: "adwdbg-legend",
  "aria-label": "Status colours"
}, Hc = ["data-status"], jc = {
  key: 0,
  class: "adwdbg-warn",
  "data-warning": "connection",
  role: "status"
}, Bc = {
  key: 1,
  class: "adwdbg-warn",
  "data-warning": "feed",
  role: "status"
}, Wc = {
  key: 2,
  class: "adwdbg-warn",
  "data-warning": "render",
  role: "alert"
}, Uc = {
  key: 4,
  class: "adwdbg-idle",
  "data-field": "idle"
}, Vc = { class: "adwdbg-bar" }, Kc = ["disabled"], Gc = ["disabled", "title"], qc = {
  key: 0,
  class: "adwdbg-note"
}, Jc = {
  class: "adwdbg-note",
  "data-field": "timing"
}, zc = /* @__PURE__ */ qe({
  __name: "DebuggerPanel",
  props: {
    controller: {}
  },
  setup(e) {
    const t = e, s = Bi(null), n = t.controller.subscribe((i) => {
      s.value = i;
    });
    rn(n), Er((i) => (t.controller.reportRenderError(i instanceof Error ? i.message : String(i)), !1));
    const r = [
      ["waiting", "Waiting"],
      ["running", "Running"],
      ["stalled", "Stalled"],
      ["fail", "Fail"],
      ["pass", "Pass"]
    ];
    return (i, o) => s.value ? (F(), B("section", Mc, [
      O("header", Pc, [
        O("strong", {
          class: "adwdbg-title",
          "data-field": "headline",
          title: s.value.adwName || void 0,
          "aria-live": "polite"
        }, j(s.value.headline), 9, Oc),
        s.value.runId ? (F(), B(Z, { key: 0 }, [
          O("span", Dc, j(s.value.adwName), 1),
          O("span", Fc, "run " + j(s.value.runId), 1),
          O("span", {
            class: "adwdbg-chip",
            "data-run-status": s.value.runStatus,
            "data-field": "status"
          }, j(s.value.runStatus), 9, Nc)
        ], 64)) : Ce("", !0),
        O("span", {
          class: "adwdbg-chip",
          "data-mode": s.value.mode,
          "data-field": "mode"
        }, j(s.value.modeLabel), 9, kc),
        O("span", Lc, [
          (F(), B(Z, null, et(r, ([l, a]) => O("span", {
            key: l,
            class: "adwdbg-key",
            "data-status": l
          }, j(a), 9, Hc)), 64)),
          o[5] || (o[5] = O("span", { class: "adwdbg-key adwdbg-key-selected" }, "Selected", -1))
        ])
      ]),
      s.value.connection.status === "disconnected" ? (F(), B("p", jc, " Event feed disconnected (attempt " + j(s.value.connection.attempts) + "): " + j(s.value.connection.reason) + ". The diagram shows the last events received; this is a connection problem, not an ADW failure. ", 1)) : s.value.connection.status === "degraded" ? (F(), B("p", Bc, " The dashboard cannot read the ADW trace: " + j(s.value.connection.reason), 1)) : Ce("", !0),
      s.value.renderError ? (F(), B("p", Wc, " Diagram could not be redrawn (" + j(s.value.renderError) + "). Showing the last good diagram; the terminal is unaffected. ", 1)) : Ce("", !0),
      s.value.diagram.columns.length ? (F(), tt(Rc, {
        key: 3,
        model: s.value.diagram,
        onPhaseClick: o[0] || (o[0] = (l) => t.controller.selectPhase(l)),
        onRunnerClick: o[1] || (o[1] = (l) => t.controller.allEvents())
      }, null, 8, ["model"])) : (F(), B("p", Uc, j(s.value.runId ? "This run has not started a step yet." : "No ADW run has been recorded yet."), 1)),
      O("div", Vc, [
        O("button", {
          type: "button",
          class: "am-btn",
          "data-action": "follow-live",
          onClick: o[2] || (o[2] = (l) => t.controller.followLive())
        }, "Follow live"),
        O("button", {
          type: "button",
          class: "am-btn",
          "data-action": "all-events",
          disabled: !s.value.phaseSelected,
          onClick: o[3] || (o[3] = (l) => t.controller.allEvents())
        }, "All events", 8, Kc),
        O("button", {
          type: "button",
          class: "am-btn",
          "data-action": "clear-run",
          disabled: !!s.value.clearDisabledReason,
          title: s.value.clearDisabledReason,
          onClick: o[4] || (o[4] = (l) => t.controller.clearSelectedRun())
        }, j(s.value.clearLabel), 9, Gc),
        s.value.clearDisabledReason ? (F(), B("span", qc, j(s.value.clearDisabledReason), 1)) : Ce("", !0),
        O("span", Jc, [
          st(" stall timeout " + j(s.value.stallTimeoutSeconds) + "s", 1),
          s.value.lastDelayMs !== null ? (F(), B(Z, { key: 0 }, [
            st(" · last event shown " + j(s.value.lastDelayMs) + " ms after it was recorded", 1)
          ], 64)) : Ce("", !0)
        ])
      ]),
      be(cc, {
        lines: s.value.lines,
        label: `ADW events — ${s.value.filterLabel}`,
        tall: s.value.phaseSelected
      }, null, 8, ["lines", "label", "tall"])
    ])) : Ce("", !0);
  }
});
function Yc(e = document) {
  const t = e.getElementById("terminal"), s = e.getElementById("terminal-stream"), n = (t == null ? void 0 : t.querySelector(".terminal-toolbar")) ?? s;
  if (!t || !s || !n || e.getElementById("adw-debugger-root"))
    return null;
  const r = e.createElement("div");
  r.id = "adw-debugger-root", n.parentNode.insertBefore(r, n);
  const i = new Xl(), o = new Gl({
    source: new tc(new Yl(), i, {
      url: "/api/adw-debugger/feed",
      activeMs: 500,
      idleMs: 5e3,
      retryStepMs: 1e3,
      retryMaxMs: 5e3,
      isActive: () => t.classList.contains("active") && e.visibilityState !== "hidden"
    }),
    selection: new Jl(),
    stall: new zl(),
    renderer: new sc(),
    cleared: new Ql(),
    legacy: new ec(s),
    clock: new Zl(),
    timer: i
  }), l = vl(zc, { controller: o });
  l.mount(r), o.start();
  const a = () => o.wake(), f = new MutationObserver(a);
  return f.observe(t, { attributes: !0, attributeFilter: ["class"] }), e.addEventListener("visibilitychange", a), {
    controller: o,
    unmount() {
      f.disconnect(), e.removeEventListener("visibilitychange", a), o.dispose(), l.unmount(), r.remove();
    }
  };
}
window.adwDebugger = Yc();
export {
  Yc as mountAdwDebugger
};
