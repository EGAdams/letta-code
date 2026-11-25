var ii = Object.defineProperty;
var oi = (e, t, s) => t in e ? ii(e, t, { enumerable: !0, configurable: !0, writable: !0, value: s }) : e[t] = s;
var Q = (e, t, s) => oi(e, typeof t != "symbol" ? t + "" : t, s);
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
const U = {}, at = [], Te = () => {
}, li = () => !1, os = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && // uppercase letter
(e.charCodeAt(2) > 122 || e.charCodeAt(2) < 97), Ks = (e) => e.startsWith("onUpdate:"), re = Object.assign, qs = (e, t) => {
  const s = e.indexOf(t);
  s > -1 && e.splice(s, 1);
}, ci = Object.prototype.hasOwnProperty, L = (e, t) => ci.call(e, t), E = Array.isArray, ut = (e) => ls(e) === "[object Map]", Kn = (e) => ls(e) === "[object Set]", M = (e) => typeof e == "function", X = (e) => typeof e == "string", Ue = (e) => typeof e == "symbol", q = (e) => e !== null && typeof e == "object", qn = (e) => (q(e) || M(e)) && M(e.then) && M(e.catch), Gn = Object.prototype.toString, ls = (e) => Gn.call(e), ai = (e) => ls(e).slice(8, -1), Jn = (e) => ls(e) === "[object Object]", Gs = (e) => X(e) && e !== "NaN" && e[0] !== "-" && "" + parseInt(e, 10) === e, It = /* @__PURE__ */ Vs(
  // the leading comma is intentional so empty string "" is also included
  ",key,ref,ref_for,ref_key,onVnodeBeforeMount,onVnodeMounted,onVnodeBeforeUpdate,onVnodeUpdated,onVnodeBeforeUnmount,onVnodeUnmounted"
), cs = (e) => {
  const t = /* @__PURE__ */ Object.create(null);
  return (s) => t[s] || (t[s] = e(s));
}, ui = /-(\w)/g, We = cs(
  (e) => e.replace(ui, (t, s) => s ? s.toUpperCase() : "")
), fi = /\B([A-Z])/g, rt = cs(
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
let pn;
const as = () => pn || (pn = typeof globalThis < "u" ? globalThis : typeof self < "u" ? self : typeof window < "u" ? window : typeof global < "u" ? global : {});
function pe(e) {
  if (E(e)) {
    const t = {};
    for (let s = 0; s < e.length; s++) {
      const n = e[s], r = X(n) ? mi(n) : pe(n);
      if (r)
        for (const i in r)
          t[i] = r[i];
    }
    return t;
  } else if (X(e) || q(e))
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
function it(e) {
  let t = "";
  if (X(e))
    t = e;
  else if (E(e))
    for (let s = 0; s < e.length; s++) {
      const n = it(e[s]);
      n && (t += n + " ");
    }
  else if (q(e))
    for (const s in e)
      e[s] && (t += s + " ");
  return t.trim();
}
const _i = "itemscope,allowfullscreen,formnovalidate,ismap,nomodule,novalidate,readonly", bi = /* @__PURE__ */ Vs(_i);
function Xn(e) {
  return !!e || e === "";
}
const Zn = (e) => !!(e && e.__v_isRef === !0), z = (e) => X(e) ? e : e == null ? "" : E(e) || q(e) && (e.toString === Gn || !M(e.toString)) ? Zn(e) ? z(e.value) : JSON.stringify(e, Qn, 2) : String(e), Qn = (e, t) => Zn(t) ? Qn(e, t.value) : ut(t) ? {
  [`Map(${t.size})`]: [...t.entries()].reduce(
    (s, [n, r], i) => (s[ws(n, i) + " =>"] = r, s),
    {}
  )
} : Kn(t) ? {
  [`Set(${t.size})`]: [...t.values()].map((s) => ws(s))
} : Ue(t) ? ws(t) : q(t) && !E(t) && !Jn(t) ? String(t) : t, ws = (e, t = "") => {
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
let W;
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
    this.flags |= 2, gn(this), nr(this);
    const t = W, s = _e;
    W = this, _e = !0;
    try {
      return this.fn();
    } finally {
      rr(this), W = t, _e = s, this.flags &= -3;
    }
  }
  stop() {
    if (this.flags & 1) {
      for (let t = this.deps; t; t = t.nextDep)
        Ys(t);
      this.deps = this.depsTail = void 0, gn(this), this.onStop && this.onStop(), this.flags &= -2;
    }
  }
  trigger() {
    this.flags & 64 ? ys.add(this) : this.scheduler ? this.scheduler() : this.runIfDirty();
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
let tr = 0, At, Ct;
function sr(e, t = !1) {
  if (e.flags |= 8, t) {
    e.next = Ct, Ct = e;
    return;
  }
  e.next = At, At = e;
}
function Js() {
  tr++;
}
function zs() {
  if (--tr > 0)
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
function Ms(e) {
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
  if (e.flags |= 2, t.version > 0 && !e.isSSR && e.deps && !Ms(e)) {
    e.flags &= -3;
    return;
  }
  const s = W, n = _e;
  W = e, _e = !0;
  try {
    nr(e);
    const r = e.fn(e._value);
    (t.version === 0 || Be(r, e._value)) && (e._value = r, t.version++);
  } catch (r) {
    throw t.version++, r;
  } finally {
    W = s, _e = n, rr(e), e.flags &= -3;
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
function Ve() {
  or.push(_e), _e = !1;
}
function Ke() {
  const e = or.pop();
  _e = e === void 0 ? !0 : e;
}
function gn(e) {
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
    if (!W || !_e || W === this.computed)
      return;
    let s = this.activeLink;
    if (s === void 0 || s.sub !== W)
      s = this.activeLink = new xi(W, this), W.deps ? (s.prevDep = W.depsTail, W.depsTail.nextDep = s, W.depsTail = s) : W.deps = W.depsTail = s, lr(s);
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
const Ps = /* @__PURE__ */ new WeakMap(), et = Symbol(
  ""
), Rs = Symbol(
  ""
), Pt = Symbol(
  ""
);
function te(e, t, s) {
  if (_e && W) {
    let n = Ps.get(e);
    n || Ps.set(e, n = /* @__PURE__ */ new Map());
    let r = n.get(s);
    r || (n.set(s, r = new Xs()), r.map = n, r.key = s), r.track();
  }
}
function Re(e, t, s, n, r, i) {
  const o = Ps.get(e);
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
    const a = E(e), f = a && Gs(s);
    if (a && s === "length") {
      const d = Number(n);
      o.forEach((p, m) => {
        (m === "length" || m === Pt || !Ue(m) && m >= d) && l(p);
      });
    } else
      switch ((s !== void 0 || o.has(void 0)) && l(o.get(s)), f && l(o.get(Pt)), t) {
        case "add":
          a ? f && l(o.get("length")) : (l(o.get(et)), ut(e) && l(o.get(Rs)));
          break;
        case "delete":
          a || (l(o.get(et)), ut(e) && l(o.get(Rs)));
          break;
        case "set":
          ut(e) && l(o.get(et));
          break;
      }
  }
  zs();
}
function ot(e) {
  const t = N(e);
  return t === e ? t : (te(t, "iterate", Pt), me(e) ? t : t.map(se));
}
function us(e) {
  return te(e = N(e), "iterate", Pt), e;
}
const Si = {
  __proto__: null,
  [Symbol.iterator]() {
    return vs(this, Symbol.iterator, se);
  },
  concat(...e) {
    return ot(this).concat(
      ...e.map((t) => E(t) ? ot(t) : t)
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
    return ot(this).join(e);
  },
  // keys() iterator only reads `length`, no optimisation required
  lastIndexOf(...e) {
    return xs(this, "lastIndexOf", e);
  },
  map(e, t) {
    return Me(this, "map", e, t, void 0, arguments);
  },
  pop() {
    return wt(this, "pop");
  },
  push(...e) {
    return wt(this, "push", e);
  },
  reduce(e, ...t) {
    return mn(this, "reduce", e, t);
  },
  reduceRight(e, ...t) {
    return mn(this, "reduceRight", e, t);
  },
  shift() {
    return wt(this, "shift");
  },
  // slice could use ARRAY_ITERATE but also seems to beg for range tracking
  some(e, t) {
    return Me(this, "some", e, t, void 0, arguments);
  },
  splice(...e) {
    return wt(this, "splice", e);
  },
  toReversed() {
    return ot(this).toReversed();
  },
  toSorted(e) {
    return ot(this).toSorted(e);
  },
  toSpliced(...e) {
    return ot(this).toSpliced(...e);
  },
  unshift(...e) {
    return wt(this, "unshift", e);
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
function mn(e, t, s, n) {
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
function wt(e, t, s = []) {
  Ve(), Js();
  const n = N(e)[t].apply(e, s);
  return zs(), Ke(), n;
}
const Ai = /* @__PURE__ */ Vs("__proto__,__v_isRef,__isVue"), cr = new Set(
  /* @__PURE__ */ Object.getOwnPropertyNames(Symbol).filter((e) => e !== "arguments" && e !== "caller").map((e) => Symbol[e]).filter(Ue)
);
function Ci(e) {
  Ue(e) || (e = String(e));
  const t = N(this);
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
    const o = E(t);
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
    return (Ue(s) ? cr.has(s) : Ai(s)) || (r || te(t, "get", s), i) ? l : ne(l) ? o && Gs(s) ? l : l.value : q(l) ? r ? pr(l) : Qs(l) : l;
  }
}
class ur extends ar {
  constructor(t = !1) {
    super(!1, t);
  }
  set(t, s, n, r) {
    let i = t[s];
    if (!this._isShallow) {
      const a = st(i);
      if (!me(n) && !st(n) && (i = N(i), n = N(n)), !E(t) && ne(i) && !ne(n))
        return a ? !1 : (i.value = n, !0);
    }
    const o = E(t) && Gs(s) ? Number(s) < t.length : L(t, s), l = Reflect.set(
      t,
      s,
      n,
      ne(t) ? t : r
    );
    return t === N(r) && (o ? Be(n, i) && Re(t, "set", s, n) : Re(t, "add", s, n)), l;
  }
  deleteProperty(t, s) {
    const n = L(t, s);
    t[s];
    const r = Reflect.deleteProperty(t, s);
    return r && n && Re(t, "delete", s, void 0), r;
  }
  has(t, s) {
    const n = Reflect.has(t, s);
    return (!Ue(s) || !cr.has(s)) && te(t, "has", s), n;
  }
  ownKeys(t) {
    return te(
      t,
      "iterate",
      E(t) ? "length" : et
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
const Ti = /* @__PURE__ */ new ur(), Ei = /* @__PURE__ */ new $i(), Mi = /* @__PURE__ */ new ur(!0);
const Os = (e) => e, Ut = (e) => Reflect.getPrototypeOf(e);
function Pi(e, t, s) {
  return function(...n) {
    const r = this.__v_raw, i = N(r), o = ut(i), l = e === "entries" || e === Symbol.iterator && o, a = e === "keys" && o, f = r[e](...n), d = s ? Os : t ? Ds : se;
    return !t && te(
      i,
      "iterate",
      a ? Rs : et
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
function Vt(e) {
  return function(...t) {
    return e === "delete" ? !1 : e === "clear" ? void 0 : this;
  };
}
function Ri(e, t) {
  const s = {
    get(r) {
      const i = this.__v_raw, o = N(i), l = N(r);
      e || (Be(r, l) && te(o, "get", r), te(o, "get", l));
      const { has: a } = Ut(o), f = t ? Os : e ? Ds : se;
      if (a.call(o, r))
        return f(i.get(r));
      if (a.call(o, l))
        return f(i.get(l));
      i !== o && i.get(r);
    },
    get size() {
      const r = this.__v_raw;
      return !e && te(N(r), "iterate", et), Reflect.get(r, "size", r);
    },
    has(r) {
      const i = this.__v_raw, o = N(i), l = N(r);
      return e || (Be(r, l) && te(o, "has", r), te(o, "has", l)), r === l ? i.has(r) : i.has(r) || i.has(l);
    },
    forEach(r, i) {
      const o = this, l = o.__v_raw, a = N(l), f = t ? Os : e ? Ds : se;
      return !e && te(a, "iterate", et), l.forEach((d, p) => r.call(i, f(d), f(p), o));
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
        !t && !me(r) && !st(r) && (r = N(r));
        const i = N(this);
        return Ut(i).has.call(i, r) || (i.add(r), Re(i, "add", r, r)), this;
      },
      set(r, i) {
        !t && !me(i) && !st(i) && (i = N(i));
        const o = N(this), { has: l, get: a } = Ut(o);
        let f = l.call(o, r);
        f || (r = N(r), f = l.call(o, r));
        const d = a.call(o, r);
        return o.set(r, i), f ? Be(i, d) && Re(o, "set", r, i) : Re(o, "add", r, i), this;
      },
      delete(r) {
        const i = N(this), { has: o, get: l } = Ut(i);
        let a = o.call(i, r);
        a || (r = N(r), a = o.call(i, r)), l && l.call(i, r);
        const f = i.delete(r);
        return a && Re(i, "delete", r, void 0), f;
      },
      clear() {
        const r = N(this), i = r.size !== 0, o = r.clear();
        return i && Re(
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
  const s = Ri(e, t);
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
function Li(e) {
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
function ki(e) {
  return e.__v_skip || !Object.isExtensible(e) ? 0 : Li(ai(e));
}
function Qs(e) {
  return st(e) ? e : en(
    e,
    !1,
    Ti,
    Oi,
    fr
  );
}
function Hi(e) {
  return en(
    e,
    !1,
    Mi,
    Di,
    dr
  );
}
function pr(e) {
  return en(
    e,
    !0,
    Ei,
    Fi,
    hr
  );
}
function en(e, t, s, n, r) {
  if (!q(e) || e.__v_raw && !(t && e.__v_isReactive))
    return e;
  const i = r.get(e);
  if (i)
    return i;
  const o = ki(e);
  if (o === 0)
    return e;
  const l = new Proxy(
    e,
    o === 2 ? n : s
  );
  return r.set(e, l), l;
}
function ft(e) {
  return st(e) ? ft(e.__v_raw) : !!(e && e.__v_isReactive);
}
function st(e) {
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
function ji(e) {
  return !L(e, "__v_skip") && Object.isExtensible(e) && Yn(e, "__v_skip", !0), e;
}
const se = (e) => q(e) ? Qs(e) : e, Ds = (e) => q(e) ? pr(e) : e;
function ne(e) {
  return e ? e.__v_isRef === !0 : !1;
}
function Xt(e) {
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
    this.dep = new Xs(), this.__v_isRef = !0, this.__v_isShallow = !1, this._rawValue = s ? t : N(t), this._value = s ? t : se(t), this.__v_isShallow = s;
  }
  get value() {
    return this.dep.track(), this._value;
  }
  set value(t) {
    const s = this._rawValue, n = this.__v_isShallow || me(t) || st(t);
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
function mr(e) {
  return ft(e) ? e : new Proxy(e, Ui);
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
    W !== this)
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
  return M(e) ? n = e : (n = e.get, r = e.set), new Vi(n, r, s);
}
const Kt = {}, Zt = /* @__PURE__ */ new WeakMap();
let Ze;
function qi(e, t = !1, s = Ze) {
  if (s) {
    let n = Zt.get(s);
    n || Zt.set(s, n = []), n.push(e);
  }
}
function Gi(e, t, s = U) {
  const { immediate: n, deep: r, once: i, scheduler: o, augmentJob: l, call: a } = s, f = ($) => r ? $ : me($) || r === !1 || r === 0 ? je($, 1) : je($);
  let d, p, m, I, R = !1, P = !1;
  if (ne(e) ? (p = () => e.value, R = me(e)) : ft(e) ? (p = () => f(e), R = !0) : E(e) ? (P = !0, R = e.some(($) => ft($) || me($)), p = () => e.map(($) => {
    if (ne($))
      return $.value;
    if (ft($))
      return f($);
    if (M($))
      return a ? a($, 2) : $();
  })) : M(e) ? t ? p = a ? () => a(e, 2) : e : p = () => {
    if (m) {
      Ve();
      try {
        m();
      } finally {
        Ke();
      }
    }
    const $ = Ze;
    Ze = d;
    try {
      return a ? a(e, 3, [I]) : e(I);
    } finally {
      Ze = $;
    }
  } : p = Te, t && r) {
    const $ = p, Z = r === !0 ? 1 / 0 : r;
    p = () => je($(), Z);
  }
  const Y = yi(), D = () => {
    d.stop(), Y && Y.active && qs(Y.effects, d);
  };
  if (i && t) {
    const $ = t;
    t = (...Z) => {
      $(...Z), D();
    };
  }
  let G = P ? new Array(e.length).fill(Kt) : Kt;
  const J = ($) => {
    if (!(!(d.flags & 1) || !d.dirty && !$))
      if (t) {
        const Z = d.run();
        if (r || R || (P ? Z.some((Fe, we) => Be(Fe, G[we])) : Be(Z, G))) {
          m && m();
          const Fe = Ze;
          Ze = d;
          try {
            const we = [
              Z,
              // pass undefined as the old value when it's changed for the first time
              G === Kt ? void 0 : P && G[0] === Kt ? [] : G,
              I
            ];
            a ? a(t, 3, we) : (
              // @ts-expect-error
              t(...we)
            ), G = Z;
          } finally {
            Ze = Fe;
          }
        }
      } else
        d.run();
  };
  return l && l(J), d = new er(p), d.scheduler = o ? () => o(J, !1) : J, I = ($) => qi($, !1, d), m = d.onStop = () => {
    const $ = Zt.get(d);
    if ($) {
      if (a)
        a($, 4);
      else
        for (const Z of $) Z();
      Zt.delete(d);
    }
  }, t ? n ? J(!0) : G = d.run() : o ? o(J.bind(null, !0), !0) : d.run(), D.pause = d.pause.bind(d), D.resume = d.resume.bind(d), D.stop = D, D;
}
function je(e, t = 1 / 0, s) {
  if (t <= 0 || !q(e) || e.__v_skip || (s = s || /* @__PURE__ */ new Set(), s.has(e)))
    return e;
  if (s.add(e), t--, ne(e))
    je(e.value, t, s);
  else if (E(e))
    for (let n = 0; n < e.length; n++)
      je(e[n], t, s);
  else if (Kn(e) || ut(e))
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
function Nt(e, t, s, n) {
  try {
    return n ? e(...n) : e();
  } catch (r) {
    fs(r, t, s);
  }
}
function Ee(e, t, s, n) {
  if (M(e)) {
    const r = Nt(e, t, s, n);
    return r && qn(r) && r.catch((i) => {
      fs(i, t, s);
    }), r;
  }
  if (E(e)) {
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
      Ve(), Nt(i, null, 10, [
        e,
        a,
        f
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
const dt = [];
let Le = null, lt = 0;
const _r = /* @__PURE__ */ Promise.resolve();
let Qt = null;
function br(e) {
  const t = Qt || _r;
  return e ? t.then(this ? e.bind(this) : e) : t;
}
function zi(e) {
  let t = Ae + 1, s = le.length;
  for (; t < s; ) {
    const n = t + s >>> 1, r = le[n], i = Rt(r);
    i < e || i === e && r.flags & 2 ? t = n + 1 : s = n;
  }
  return t;
}
function sn(e) {
  if (!(e.flags & 1)) {
    const t = Rt(e), s = le[le.length - 1];
    !s || // fast path when the job id is larger than the tail
    !(e.flags & 2) && t >= Rt(s) ? le.push(e) : le.splice(zi(t), 0, e), e.flags |= 1, wr();
  }
}
function wr() {
  Qt || (Qt = _r.then(vr));
}
function Yi(e) {
  E(e) ? dt.push(...e) : Le && e.id === -1 ? Le.splice(lt + 1, 0, e) : e.flags & 1 || (dt.push(e), e.flags |= 1), wr();
}
function _n(e, t, s = Ae + 1) {
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
  if (dt.length) {
    const t = [...new Set(dt)].sort(
      (s, n) => Rt(s) - Rt(n)
    );
    if (dt.length = 0, Le) {
      Le.push(...t);
      return;
    }
    for (Le = t, lt = 0; lt < Le.length; lt++) {
      const s = Le[lt];
      s.flags & 4 && (s.flags &= -2), s.flags & 8 || s(), s.flags &= -2;
    }
    Le = null, lt = 0;
  }
}
const Rt = (e) => e.id == null ? e.flags & 2 ? -1 : 1 / 0 : e.id;
function vr(e) {
  try {
    for (Ae = 0; Ae < le.length; Ae++) {
      const t = le[Ae];
      t && !(t.flags & 8) && (t.flags & 4 && (t.flags &= -2), Nt(
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
    Ae = -1, le.length = 0, yr(), Qt = null, (le.length || dt.length) && vr();
  }
}
let $e = null, xr = null;
function es(e) {
  const t = $e;
  return $e = e, xr = e && e.type.__scopeId || null, t;
}
function Xi(e, t = $e, s) {
  if (!t || e._n)
    return e;
  const n = (...r) => {
    n._d && Cn(-1);
    const i = es(t);
    let o;
    try {
      o = e(...r);
    } finally {
      es(i), n._d && Cn(1);
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
    a && (Ve(), Ee(a, s, 8, [
      e.el,
      l,
      e,
      t
    ]), Ke());
  }
}
const Zi = Symbol("_vte"), Qi = (e) => e.__isTeleport;
function nn(e, t) {
  e.shapeFlag & 6 && e.component ? (e.transition = t, nn(e.component.subTree, t)) : e.shapeFlag & 128 ? (e.ssContent.transition = t.clone(e.ssContent), e.ssFallback.transition = t.clone(e.ssFallback)) : e.transition = t;
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
function Sr(e) {
  e.ids = [e.ids[0] + e.ids[2]++ + "-", 0, 0];
}
function ts(e, t, s, n, r = !1) {
  if (E(e)) {
    e.forEach(
      (R, P) => ts(
        R,
        t && (E(t) ? t[P] : t),
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
  const i = n.shapeFlag & 4 ? ln(n.component) : n.el, o = r ? null : i, { i: l, r: a } = e, f = t && t.r, d = l.refs === U ? l.refs = {} : l.refs, p = l.setupState, m = N(p), I = p === U ? () => !1 : (R) => L(m, R);
  if (f != null && f !== a && (X(f) ? (d[f] = null, I(f) && (p[f] = null)) : ne(f) && (f.value = null)), M(a))
    Nt(a, l, 12, [o, d]);
  else {
    const R = X(a), P = ne(a);
    if (R || P) {
      const Y = () => {
        if (e.f) {
          const D = R ? I(a) ? p[a] : d[a] : a.value;
          r ? E(D) && qs(D, i) : E(D) ? D.includes(i) || D.push(i) : R ? (d[a] = [i], I(a) && (p[a] = d[a])) : (a.value = [i], e.k && (d[e.k] = a.value));
        } else R ? (d[a] = o, I(a) && (p[a] = o)) : P && (a.value = o, e.k && (d[e.k] = o));
      };
      o ? (Y.id = -1, de(Y, s)) : Y();
    }
  }
}
as().requestIdleCallback;
as().cancelIdleCallback;
const $t = (e) => !!e.type.__asyncLoader, Ir = (e) => e.type.__isKeepAlive;
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
    qs(n[t], r);
  }, s);
}
function ds(e, t, s = ce, n = !1) {
  if (s) {
    const r = s[e] || (s[e] = []), i = t.__weh || (t.__weh = (...o) => {
      Ve();
      const l = Lt(s), a = Ee(t, s, e, o);
      return l(), Ke(), a;
    });
    return n ? r.unshift(i) : r.push(i), i;
  }
}
const De = (e) => (t, s = ce) => {
  (!Dt || e === "sp") && ds(e, (...n) => t(...n), s);
}, no = De("bm"), ro = De("m"), io = De(
  "bu"
), oo = De("u"), Cr = De(
  "bum"
), $r = De("um"), lo = De(
  "sp"
), co = De("rtg"), ao = De("rtc");
function Tr(e, t = ce) {
  ds("ec", e, t);
}
const uo = Symbol.for("v-ndc");
function ct(e, t, s, n) {
  let r;
  const i = s, o = E(e);
  if (o || X(e)) {
    const l = o && ft(e);
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
  } else if (q(e))
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
const Fs = (e) => e ? Yr(e) ? ln(e) : Fs(e.parent) : null, Tt = (
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
    $nextTick: (e) => e.n || (e.n = br.bind(e.proxy)),
    $watch: (e) => Oo.bind(e)
  })
), Ss = (e, t) => e !== U && !e.__isScriptSetup && L(e, t), fo = {
  get({ _: e }, t) {
    if (t === "__v_skip")
      return !0;
    const { ctx: s, setupState: n, data: r, props: i, accessCache: o, type: l, appContext: a } = e;
    let f;
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
    const d = Tt[t];
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
    return !!s[o] || e !== U && L(e, o) || Ss(t, o) || (l = i[0]) && L(l, o) || L(n, o) || L(Tt, o) || L(r.config.globalProperties, o);
  },
  defineProperty(e, t, s) {
    return s.get != null ? e._.accessCache[t] = 0 : L(s, "value") && this.set(e, t, s.value, null), Reflect.defineProperty(e, t, s);
  }
};
function bn(e) {
  return E(e) ? e.reduce(
    (t, s) => (t[s] = null, t),
    {}
  ) : e;
}
let Ns = !0;
function ho(e) {
  const t = Mr(e), s = e.proxy, n = e.ctx;
  Ns = !1, t.beforeCreate && wn(t.beforeCreate, e, "bc");
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
    beforeUpdate: I,
    updated: R,
    activated: P,
    deactivated: Y,
    beforeDestroy: D,
    beforeUnmount: G,
    destroyed: J,
    unmounted: $,
    render: Z,
    renderTracked: Fe,
    renderTriggered: we,
    errorCaptured: Ne,
    serverPrefetch: kt,
    // public API
    expose: Ge,
    inheritAttrs: gt,
    // assets
    components: Ht,
    directives: jt,
    filters: gs
  } = t;
  if (f && po(f, n, null), o)
    for (const K in o) {
      const j = o[K];
      M(j) && (n[K] = j.bind(s));
    }
  if (r) {
    const K = r.call(s, s);
    q(K) && (e.data = Qs(K));
  }
  if (Ns = !0, i)
    for (const K in i) {
      const j = i[K], Je = M(j) ? j.bind(s, s) : M(j.get) ? j.get.bind(s, s) : Te, Bt = !M(j) && M(j.set) ? j.set.bind(s) : Te, ze = tt({
        get: Je,
        set: Bt
      });
      Object.defineProperty(n, K, {
        enumerable: !0,
        configurable: !0,
        get: () => ze.value,
        set: (ye) => ze.value = ye
      });
    }
  if (l)
    for (const K in l)
      Er(l[K], n, s, K);
  if (a) {
    const K = M(a) ? a.call(s) : a;
    Reflect.ownKeys(K).forEach((j) => {
      yo(j, K[j]);
    });
  }
  d && wn(d, e, "c");
  function ie(K, j) {
    E(j) ? j.forEach((Je) => K(Je.bind(s))) : j && K(j.bind(s));
  }
  if (ie(no, p), ie(ro, m), ie(io, I), ie(oo, R), ie(eo, P), ie(to, Y), ie(Tr, Ne), ie(ao, Fe), ie(co, we), ie(Cr, G), ie($r, $), ie(lo, kt), E(Ge))
    if (Ge.length) {
      const K = e.exposed || (e.exposed = {});
      Ge.forEach((j) => {
        Object.defineProperty(K, j, {
          get: () => s[j],
          set: (Je) => s[j] = Je
        });
      });
    } else e.exposed || (e.exposed = {});
  Z && e.render === Te && (e.render = Z), gt != null && (e.inheritAttrs = gt), Ht && (e.components = Ht), jt && (e.directives = jt), kt && Sr(e);
}
function po(e, t, s = Te) {
  E(e) && (e = Ls(e));
  for (const n in e) {
    const r = e[n];
    let i;
    q(r) ? "default" in r ? i = Gt(
      r.from || n,
      r.default,
      !0
    ) : i = Gt(r.from || n) : i = Gt(r), ne(i) ? Object.defineProperty(t, n, {
      enumerable: !0,
      configurable: !0,
      get: () => i.value,
      set: (o) => i.value = o
    }) : t[n] = i;
  }
}
function wn(e, t, s) {
  Ee(
    E(e) ? e.map((n) => n.bind(t.proxy)) : e.bind(t.proxy),
    t,
    s
  );
}
function Er(e, t, s, n) {
  let r = n.includes(".") ? Vr(s, n) : () => s[n];
  if (X(e)) {
    const i = t[e];
    M(i) && Jt(r, i);
  } else if (M(e))
    Jt(r, e.bind(s));
  else if (q(e))
    if (E(e))
      e.forEach((i) => Er(i, t, s, n));
    else {
      const i = M(e.handler) ? e.handler.bind(s) : t[e.handler];
      M(i) && Jt(r, i, e);
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
  ), ss(a, t, o)), q(t) && i.set(t, a), a;
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
  data: yn,
  props: vn,
  emits: vn,
  // objects
  methods: vt,
  computed: vt,
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
  components: vt,
  directives: vt,
  // watch
  watch: _o,
  // provide / inject
  provide: yn,
  inject: mo
};
function yn(e, t) {
  return t ? e ? function() {
    return re(
      M(e) ? e.call(this, this) : e,
      M(t) ? t.call(this, this) : t
    );
  } : t : e;
}
function mo(e, t) {
  return vt(Ls(e), Ls(t));
}
function Ls(e) {
  if (E(e)) {
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
function vt(e, t) {
  return e ? re(/* @__PURE__ */ Object.create(null), e, t) : t;
}
function vn(e, t) {
  return e ? E(e) && E(t) ? [.../* @__PURE__ */ new Set([...e, ...t])] : re(
    /* @__PURE__ */ Object.create(null),
    bn(e),
    bn(t ?? {})
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
        if (!a) {
          const I = f._ceVNode || be(n, r);
          return I.appContext = i, m === !0 ? m = "svg" : m === !1 && (m = void 0), e(I, d, m), a = !0, f._container = d, d.__vue_app__ = f, ln(I.component);
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
        const p = ht;
        ht = f;
        try {
          return d();
        } finally {
          ht = p;
        }
      }
    };
    return f;
  };
}
let ht = null;
function yo(e, t) {
  if (ce) {
    let s = ce.provides;
    const n = ce.parent && ce.parent.provides;
    n === s && (s = ce.provides = Object.create(n)), s[e] = t;
  }
}
function Gt(e, t, s = !1) {
  const n = ce || $e;
  if (n || ht) {
    const r = ht ? ht._context.provides : n ? n.parent == null ? n.vnode.appContext && n.vnode.appContext.provides : n.parent.provides : void 0;
    if (r && e in r)
      return r[e];
    if (arguments.length > 1)
      return s && M(t) ? t.call(n && n.proxy) : t;
  }
}
const Rr = {}, Or = () => Object.create(Rr), Dr = (e) => Object.getPrototypeOf(e) === Rr;
function vo(e, t, s, n = !1) {
  const r = {}, i = Or();
  e.propsDefaults = /* @__PURE__ */ Object.create(null), Fr(e, t, r, i);
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
        const I = t[m];
        if (a)
          if (L(i, m))
            I !== i[m] && (i[m] = I, f = !0);
          else {
            const R = We(m);
            r[R] = ks(
              a,
              l,
              R,
              I,
              e,
              !1
            );
          }
        else
          I !== i[m] && (i[m] = I, f = !0);
      }
    }
  } else {
    Fr(e, t, r, i) && (f = !0);
    let d;
    for (const p in l)
      (!t || // for camelCase
      !L(t, p) && // it's possible the original props was passed in as kebab-case
      // and converted to camelCase (#955)
      ((d = rt(p)) === p || !L(t, d))) && (a ? s && // for camelCase
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
  f && Re(e.attrs, "set", "");
}
function Fr(e, t, s, n) {
  const [r, i] = e.propsOptions;
  let o = !1, l;
  if (t)
    for (let a in t) {
      if (It(a))
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
      if (o.type !== Function && !o.skipFactory && M(a)) {
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
    ] && (n === "" || n === rt(s)) && (n = !0));
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
    const d = (p) => {
      a = !0;
      const [m, I] = Nr(p, t, !0);
      re(o, m), I && l.push(...I);
    };
    !s && t.mixins.length && t.mixins.forEach(d), e.extends && d(e.extends), e.mixins && e.mixins.forEach(d);
  }
  if (!i && !a)
    return q(e) && n.set(e, at), at;
  if (E(i))
    for (let d = 0; d < i.length; d++) {
      const p = We(i[d]);
      xn(p) && (o[p] = U);
    }
  else if (i)
    for (const d in i) {
      const p = We(d);
      if (xn(p)) {
        const m = i[d], I = o[p] = E(m) || M(m) ? { type: m } : re({}, m), R = I.type;
        let P = !1, Y = !0;
        if (E(R))
          for (let D = 0; D < R.length; ++D) {
            const G = R[D], J = M(G) && G.name;
            if (J === "Boolean") {
              P = !0;
              break;
            } else J === "String" && (Y = !1);
          }
        else
          P = M(R) && R.name === "Boolean";
        I[
          0
          /* shouldCast */
        ] = P, I[
          1
          /* shouldCastTrue */
        ] = Y, (P || L(I, "default")) && l.push(p);
      }
    }
  const f = [o, l];
  return q(e) && n.set(e, f), f;
}
function xn(e) {
  return e[0] !== "$" && !It(e);
}
const Lr = (e) => e[0] === "_" || e === "$stable", rn = (e) => E(e) ? e.map(Ce) : [Ce(e)], Io = (e, t, s) => {
  if (t._n)
    return t;
  const n = Xi((...r) => rn(t(...r)), s);
  return n._c = !1, n;
}, kr = (e, t, s) => {
  const n = e._ctx;
  for (const r in e) {
    if (Lr(r)) continue;
    const i = e[r];
    if (M(i))
      t[r] = Io(r, i, n);
    else if (i != null) {
      const o = rn(i);
      t[r] = () => o;
    }
  }
}, Hr = (e, t) => {
  const s = rn(t);
  e.slots.default = () => s;
}, jr = (e, t, s) => {
  for (const n in t)
    (s || n !== "_") && (e[n] = t[n]);
}, Ao = (e, t, s) => {
  const n = e.slots = Or();
  if (e.vnode.shapeFlag & 32) {
    const r = t._;
    r ? (jr(n, t, s), s && Yn(n, "_", r, !0)) : kr(t, n);
  } else t && Hr(e, t);
}, Co = (e, t, s) => {
  const { vnode: n, slots: r } = e;
  let i = !0, o = U;
  if (n.shapeFlag & 32) {
    const l = t._;
    l ? s && l === 1 ? i = !1 : jr(r, t, s) : (i = !t.$stable, kr(t, r)), o = t;
  } else t && (Hr(e, t), o = { default: 1 });
  if (i)
    for (const l in r)
      !Lr(l) && o[l] == null && delete r[l];
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
    setScopeId: I = Te,
    insertStaticContent: R
  } = e, P = (c, u, h, b = null, g = null, _ = null, x = void 0, v = null, y = !!u.dynamicChildren) => {
    if (c === u)
      return;
    c && !yt(c, u) && (b = Wt(c), ye(c, g, _, !0), c = null), u.patchFlag === -2 && (y = !1, u.dynamicChildren = null);
    const { type: w, ref: C, shapeFlag: S } = u;
    switch (w) {
      case ps:
        Y(c, u, h, b);
        break;
      case nt:
        D(c, u, h, b);
        break;
      case As:
        c == null && G(u, h, b, x);
        break;
      case ee:
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
        S & 1 ? Z(
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
          _t
        );
    }
    C != null && g && ts(C, c && c.ref, _, u || c, !u);
  }, Y = (c, u, h, b) => {
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
  }, G = (c, u, h, b) => {
    [c.el, c.anchor] = R(
      c.children,
      u,
      h,
      b,
      c.el,
      c.anchor
    );
  }, J = ({ el: c, anchor: u }, h, b) => {
    let g;
    for (; c && c !== u; )
      g = m(c), n(c, h, b), c = g;
    n(u, h, b);
  }, $ = ({ el: c, anchor: u }) => {
    let h;
    for (; c && c !== u; )
      h = m(c), r(c), c = h;
    r(u);
  }, Z = (c, u, h, b, g, _, x, v, y) => {
    u.type === "svg" ? x = "svg" : u.type === "math" && (x = "mathml"), c == null ? Fe(
      u,
      h,
      b,
      g,
      _,
      x,
      v,
      y
    ) : kt(
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
    ), S & 8 ? d(y, c.children) : S & 16 && Ne(
      c.children,
      y,
      null,
      b,
      g,
      Is(c, _),
      x,
      v
    ), T && Ye(c, null, b, "created"), we(y, c, c.scopeId, x, b), C) {
      for (const B in C)
        B !== "value" && !It(B) && i(y, B, null, C[B], _, b);
      "value" in C && i(y, "value", null, C.value, _), (w = C.onVnodeBeforeMount) && Ie(w, b, c);
    }
    T && Ye(c, null, b, "beforeMount");
    const O = Eo(g, A);
    O && A.beforeEnter(y), n(y, u, h), ((w = C && C.onVnodeMounted) || O || T) && de(() => {
      w && Ie(w, b, c), O && A.enter(y), T && Ye(c, null, b, "mounted");
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
  }, Ne = (c, u, h, b, g, _, x, v, y = 0) => {
    for (let w = y; w < c.length; w++) {
      const C = c[w] = v ? ke(c[w]) : Ce(c[w]);
      P(
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
  }, kt = (c, u, h, b, g, _, x) => {
    const v = u.el = c.el;
    let { patchFlag: y, dynamicChildren: w, dirs: C } = u;
    y |= c.patchFlag & 16;
    const S = c.props || U, A = u.props || U;
    let T;
    if (h && Xe(h, !1), (T = A.onVnodeBeforeUpdate) && Ie(T, h, u, c), C && Ye(u, c, h, "beforeUpdate"), h && Xe(h, !0), (S.innerHTML && A.innerHTML == null || S.textContent && A.textContent == null) && d(v, ""), w ? Ge(
      c.dynamicChildren,
      w,
      v,
      h,
      b,
      Is(u, g),
      _
    ) : x || j(
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
        gt(v, S, A, h, g);
      else if (y & 2 && S.class !== A.class && i(v, "class", null, A.class, g), y & 4 && i(v, "style", S.style, A.style, g), y & 8) {
        const O = u.dynamicProps;
        for (let B = 0; B < O.length; B++) {
          const k = O[B], ue = S[k], ae = A[k];
          (ae !== ue || k === "value") && i(v, k, ue, ae, g, h);
        }
      }
      y & 1 && c.children !== u.children && d(v, u.children);
    } else !x && w == null && gt(v, S, A, h, g);
    ((T = A.onVnodeUpdated) || C) && de(() => {
      T && Ie(T, h, u, c), C && Ye(u, c, h, "updated");
    }, b);
  }, Ge = (c, u, h, b, g, _, x) => {
    for (let v = 0; v < u.length; v++) {
      const y = c[v], w = u[v], C = (
        // oldVNode may be an errored async setup() component inside Suspense
        // which will not have a mounted element
        y.el && // - In the case of a Fragment, we need to provide the actual parent
        // of the Fragment itself so it can move its children.
        (y.type === ee || // - In the case of different nodes, there is going to be a replacement
        // which also requires the correct parent container
        !yt(y, w) || // - In the case of a component, it could contain anything.
        y.shapeFlag & 70) ? p(y.el) : (
          // In other cases, the parent container is not actually used so we
          // just pass the block element here to avoid a DOM parentNode call.
          h
        )
      );
      P(
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
  }, gt = (c, u, h, b, g) => {
    if (u !== h) {
      if (u !== U)
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
    T && (v = v ? v.concat(T) : T), c == null ? (n(w, h, b), n(C, h, b), Ne(
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
    c.dynamicChildren ? (Ge(
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
    (u.key != null || g && u === g.subTree) && Br(
      c,
      u,
      !0
      /* shallow */
    )) : j(
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
    ) : gs(
      u,
      h,
      b,
      g,
      _,
      x,
      y
    ) : an(c, u, y);
  }, gs = (c, u, h, b, g, _, x) => {
    const v = c.component = Go(
      c,
      b,
      g
    );
    if (Ir(c) && (v.ctx.renderer = _t), Jo(v, !1, x), v.asyncDep) {
      if (g && g.registerDep(v, ie, x), !c.el) {
        const y = v.subTree = be(nt);
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
        x
      );
  }, an = (c, u, h) => {
    const b = u.component = c.component;
    if (ko(c, u, h))
      if (b.asyncDep && !b.asyncResolved) {
        K(b, u, h);
        return;
      } else
        b.next = u, b.update();
    else
      u.el = c.el, b.vnode = u;
  }, ie = (c, u, h, b, g, _, x) => {
    const v = () => {
      if (c.isMounted) {
        let { next: S, bu: A, u: T, parent: O, vnode: B } = c;
        {
          const xe = Wr(c);
          if (xe) {
            S && (S.el = B.el, K(c, S, x)), xe.asyncDep.then(() => {
              c.isUnmounted || v();
            });
            return;
          }
        }
        let k = S, ue;
        Xe(c, !1), S ? (S.el = B.el, K(c, S, x)) : S = B, A && bs(A), (ue = S.props && S.props.onVnodeBeforeUpdate) && Ie(ue, O, S, B), Xe(c, !0);
        const ae = In(c), ve = c.subTree;
        c.subTree = ae, P(
          ve,
          ae,
          // parent may have changed if it's in a teleport
          p(ve.el),
          // anchor may have changed if it's in a fragment
          Wt(ve),
          c,
          g,
          _
        ), S.el = ae.el, k === null && Ho(c, ae.el), T && de(T, g), (ue = S.props && S.props.onVnodeUpdated) && de(
          () => Ie(ue, O, S, B),
          g
        );
      } else {
        let S;
        const { el: A, props: T } = u, { bm: O, m: B, parent: k, root: ue, type: ae } = c, ve = $t(u);
        Xe(c, !1), O && bs(O), !ve && (S = T && T.onVnodeBeforeMount) && Ie(S, k, u), Xe(c, !0);
        {
          ue.ce && ue.ce._injectChildStyle(ae);
          const xe = c.subTree = In(c);
          P(
            null,
            xe,
            h,
            b,
            c,
            g,
            _
          ), u.el = xe.el;
        }
        if (B && de(B, g), !ve && (S = T && T.onVnodeMounted)) {
          const xe = u;
          de(
            () => Ie(S, k, xe),
            g
          );
        }
        (u.shapeFlag & 256 || k && $t(k.vnode) && k.vnode.shapeFlag & 256) && c.a && de(c.a, g), c.isMounted = !0, u = h = b = null;
      }
    };
    c.scope.on();
    const y = c.effect = new er(v);
    c.scope.off();
    const w = c.update = y.run.bind(y), C = c.job = y.runIfDirty.bind(y);
    C.i = c, C.id = c.uid, y.scheduler = () => sn(C), Xe(c, !0), w();
  }, K = (c, u, h) => {
    u.component = c;
    const b = c.vnode.props;
    c.vnode = u, c.next = null, xo(c, u.props, b, h), Co(c, u.children, h), Ve(), _n(c), Ke();
  }, j = (c, u, h, b, g, _, x, v, y = !1) => {
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
    T & 8 ? (C & 16 && mt(w, g, _), S !== w && d(h, S)) : C & 16 ? T & 16 ? Bt(
      w,
      S,
      h,
      b,
      g,
      _,
      x,
      v,
      y
    ) : mt(w, g, _, !0) : (C & 8 && d(h, ""), T & 16 && Ne(
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
    c = c || at, u = u || at;
    const w = c.length, C = u.length, S = Math.min(w, C);
    let A;
    for (A = 0; A < S; A++) {
      const T = u[A] = y ? ke(u[A]) : Ce(u[A]);
      P(
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
    w > C ? mt(
      c,
      g,
      _,
      !0,
      !1,
      S
    ) : Ne(
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
      const T = c[w], O = u[w] = y ? ke(u[w]) : Ce(u[w]);
      if (yt(T, O))
        P(
          T,
          O,
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
      const T = c[S], O = u[A] = y ? ke(u[A]) : Ce(u[A]);
      if (yt(T, O))
        P(
          T,
          O,
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
        const T = A + 1, O = T < C ? u[T].el : b;
        for (; w <= A; )
          P(
            null,
            u[w] = y ? ke(u[w]) : Ce(u[w]),
            h,
            O,
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
      const T = w, O = w, B = /* @__PURE__ */ new Map();
      for (w = O; w <= A; w++) {
        const fe = u[w] = y ? ke(u[w]) : Ce(u[w]);
        fe.key != null && B.set(fe.key, w);
      }
      let k, ue = 0;
      const ae = A - O + 1;
      let ve = !1, xe = 0;
      const bt = new Array(ae);
      for (w = 0; w < ae; w++) bt[w] = 0;
      for (w = T; w <= S; w++) {
        const fe = c[w];
        if (ue >= ae) {
          ye(fe, g, _, !0);
          continue;
        }
        let Se;
        if (fe.key != null)
          Se = B.get(fe.key);
        else
          for (k = O; k <= A; k++)
            if (bt[k - O] === 0 && yt(fe, u[k])) {
              Se = k;
              break;
            }
        Se === void 0 ? ye(fe, g, _, !0) : (bt[Se - O] = w + 1, Se >= xe ? xe = Se : ve = !0, P(
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
      const dn = ve ? Mo(bt) : at;
      for (k = dn.length - 1, w = ae - 1; w >= 0; w--) {
        const fe = O + w, Se = u[fe], hn = fe + 1 < C ? u[fe + 1].el : b;
        bt[w] === 0 ? P(
          null,
          Se,
          h,
          hn,
          g,
          _,
          x,
          v,
          y
        ) : ve && (k < 0 || w !== dn[k] ? ze(Se, h, hn, 2) : k--);
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
      x.move(c, u, h, _t);
      return;
    }
    if (x === ee) {
      n(_, u, h);
      for (let S = 0; S < y.length; S++)
        ze(y[S], u, h, b);
      n(c.anchor, u, h);
      return;
    }
    if (x === As) {
      J(c, u, h);
      return;
    }
    if (b !== 2 && w & 1 && v)
      if (b === 0)
        v.beforeEnter(_), n(_, u, h), de(() => v.enter(_), g);
      else {
        const { leave: S, delayLeave: A, afterLeave: T } = v, O = () => n(_, u, h), B = () => {
          S(_, () => {
            O(), T && T();
          });
        };
        A ? A(_, O, B) : B();
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
    if (S === -2 && (g = !1), v != null && ts(v, null, h, c, !0), T != null && (u.renderCache[T] = void 0), C & 256) {
      u.ctx.deactivate(c);
      return;
    }
    const O = C & 1 && A, B = !$t(c);
    let k;
    if (B && (k = x && x.onVnodeBeforeUnmount) && Ie(k, u, c), C & 6)
      ri(c.component, h, b);
    else {
      if (C & 128) {
        c.suspense.unmount(h, b);
        return;
      }
      O && Ye(c, null, u, "beforeUnmount"), C & 64 ? c.type.remove(
        c,
        u,
        h,
        _t,
        b
      ) : w && // #5154
      // when v-once is used inside a block, setBlockTracking(-1) marks the
      // parent block with hasOnce: true
      // so that it doesn't take the fast path during unmount - otherwise
      // components nested in v-once are never unmounted.
      !w.hasOnce && // #1153: fast path should not be taken for non-stable (v-for) fragments
      (_ !== ee || S > 0 && S & 64) ? mt(
        w,
        u,
        h,
        !1,
        !0
      ) : (_ === ee && S & 384 || !g && C & 16) && mt(y, u, h), b && un(c);
    }
    (B && (k = x && x.onVnodeUnmounted) || O) && de(() => {
      k && Ie(k, u, c), O && Ye(c, null, u, "unmounted");
    }, h);
  }, un = (c) => {
    const { type: u, el: h, anchor: b, transition: g } = c;
    if (u === ee) {
      ni(h, b);
      return;
    }
    if (u === As) {
      $(c);
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
    Sn(y), Sn(w), b && bs(b), g.stop(), _ && (_.flags |= 8, ye(x, c, u, h)), v && de(v, u), de(() => {
      c.isUnmounted = !0;
    }, u), u && u.pendingBranch && !u.isUnmounted && c.asyncDep && !c.asyncResolved && c.suspenseId === u.pendingId && (u.deps--, u.deps === 0 && u.resolve());
  }, mt = (c, u, h, b = !1, g = !1, _ = 0) => {
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
  let ms = !1;
  const fn = (c, u, h) => {
    c == null ? u._vnode && ye(u._vnode, null, null, !0) : P(
      u._vnode || null,
      c,
      u,
      null,
      null,
      null,
      h
    ), u._vnode = c, ms || (ms = !0, _n(), yr(), ms = !1);
  }, _t = {
    p: P,
    um: ye,
    m: ze,
    r: un,
    mt: gs,
    mc: Ne,
    pc: j,
    pbc: Ge,
    n: Wt,
    o: e
  };
  return {
    render: fn,
    hydrate: void 0,
    createApp: wo(fn)
  };
}
function Is({ type: e, props: t }, s) {
  return s === "svg" && e === "foreignObject" || s === "mathml" && e === "annotation-xml" && t && t.encoding && t.encoding.includes("html") ? void 0 : s;
}
function Xe({ effect: e, job: t }, s) {
  s ? (e.flags |= 32, t.flags |= 4) : (e.flags &= -33, t.flags &= -5);
}
function Eo(e, t) {
  return (!e || e && !e.pendingBranch) && t && !t.persisted;
}
function Br(e, t, s = !1) {
  const n = e.children, r = t.children;
  if (E(n) && E(r))
    for (let i = 0; i < n.length; i++) {
      const o = n[i];
      let l = r[i];
      l.shapeFlag & 1 && !l.dynamicChildren && ((l.patchFlag <= 0 || l.patchFlag === 32) && (l = r[i] = ke(r[i]), l.el = o.el), !s && l.patchFlag !== -2 && Br(o, l)), l.type === ps && (l.el = o.el);
    }
}
function Mo(e) {
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
function Sn(e) {
  if (e)
    for (let t = 0; t < e.length; t++)
      e[t].flags |= 8;
}
const Po = Symbol.for("v-scx"), Ro = () => Gt(Po);
function Jt(e, t, s) {
  return Ur(e, t, s);
}
function Ur(e, t, s = U) {
  const { immediate: n, deep: r, flush: i, once: o } = s, l = re({}, s), a = t && n || !t && i !== "post";
  let f;
  if (Dt) {
    if (i === "sync") {
      const I = Ro();
      f = I.__watcherHandles || (I.__watcherHandles = []);
    } else if (!a) {
      const I = () => {
      };
      return I.stop = Te, I.resume = Te, I.pause = Te, I;
    }
  }
  const d = ce;
  l.call = (I, R, P) => Ee(I, d, R, P);
  let p = !1;
  i === "post" ? l.scheduler = (I) => {
    de(I, d && d.suspense);
  } : i !== "sync" && (p = !0, l.scheduler = (I, R) => {
    R ? I() : sn(I);
  }), l.augmentJob = (I) => {
    t && (I.flags |= 4), p && (I.flags |= 2, d && (I.id = d.uid, I.i = d));
  };
  const m = Gi(e, t, l);
  return Dt && (f ? f.push(m) : a && m()), m;
}
function Oo(e, t, s) {
  const n = this.proxy, r = X(e) ? e.includes(".") ? Vr(n, e) : () => n[e] : e.bind(n, n);
  let i;
  M(t) ? i = t : (i = t.handler, s = t);
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
const Do = (e, t) => t === "modelValue" || t === "model-value" ? e.modelModifiers : e[`${t}Modifiers`] || e[`${We(t)}Modifiers`] || e[`${rt(t)}Modifiers`];
function Fo(e, t, ...s) {
  if (e.isUnmounted) return;
  const n = e.vnode.props || U;
  let r = s;
  const i = t.startsWith("update:"), o = i && Do(n, t.slice(7));
  o && (o.trim && (r = s.map((d) => X(d) ? d.trim() : d)), o.number && (r = s.map(di)));
  let l, a = n[l = _s(t)] || // also try camelCase event handler (#2249)
  n[l = _s(We(t))];
  !a && i && (a = n[l = _s(rt(t))]), a && Ee(
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
function Kr(e, t, s = !1) {
  const n = t.emitsCache, r = n.get(e);
  if (r !== void 0)
    return r;
  const i = e.emits;
  let o = {}, l = !1;
  if (!M(e)) {
    const a = (f) => {
      const d = Kr(f, t, !0);
      d && (l = !0, re(o, d));
    };
    !s && t.mixins.length && t.mixins.forEach(a), e.extends && a(e.extends), e.mixins && e.mixins.forEach(a);
  }
  return !i && !l ? (q(e) && n.set(e, null), null) : (E(i) ? i.forEach((a) => o[a] = null) : re(o, i), q(e) && n.set(e, o), o);
}
function hs(e, t) {
  return !e || !os(t) ? !1 : (t = t.slice(2).replace(/Once$/, ""), L(e, t[0].toLowerCase() + t.slice(1)) || L(e, rt(t)) || L(e, t));
}
function In(e) {
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
    setupState: I,
    ctx: R,
    inheritAttrs: P
  } = e, Y = es(e);
  let D, G;
  try {
    if (s.shapeFlag & 4) {
      const $ = r || n, Z = $;
      D = Ce(
        f.call(
          Z,
          $,
          d,
          p,
          I,
          m,
          R
        )
      ), G = l;
    } else {
      const $ = t;
      D = Ce(
        $.length > 1 ? $(
          p,
          { attrs: l, slots: o, emit: a }
        ) : $(
          p,
          null
        )
      ), G = t.props ? l : No(l);
    }
  } catch ($) {
    Et.length = 0, fs($, e, 1), D = be(nt);
  }
  let J = D;
  if (G && P !== !1) {
    const $ = Object.keys(G), { shapeFlag: Z } = J;
    $.length && Z & 7 && (i && $.some(Ks) && (G = Lo(
      G,
      i
    )), J = pt(J, G, !1, !0));
  }
  return s.dirs && (J = pt(J, null, !1, !0), J.dirs = J.dirs ? J.dirs.concat(s.dirs) : s.dirs), s.transition && nn(J, s.transition), D = J, es(Y), D;
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
      return n ? An(n, o, f) : !!o;
    if (a & 8) {
      const d = t.dynamicProps;
      for (let p = 0; p < d.length; p++) {
        const m = d[p];
        if (o[m] !== n[m] && !hs(f, m))
          return !0;
      }
    }
  } else
    return (r || l) && (!l || !l.$stable) ? !0 : n === o ? !1 : n ? o ? An(n, o, f) : !0 : !!o;
  return !1;
}
function An(e, t, s) {
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
const qr = (e) => e.__isSuspense;
function jo(e, t) {
  t && t.pendingBranch ? E(e) ? t.effects.push(...e) : t.effects.push(e) : Yi(e);
}
const ee = Symbol.for("v-fgt"), ps = Symbol.for("v-txt"), nt = Symbol.for("v-cmt"), As = Symbol.for("v-stc"), Et = [];
let ge = null;
function F(e = !1) {
  Et.push(ge = e ? null : []);
}
function Bo() {
  Et.pop(), ge = Et[Et.length - 1] || null;
}
let Ot = 1;
function Cn(e, t = !1) {
  Ot += e, e < 0 && ge && t && (ge.hasOnce = !0);
}
function Gr(e) {
  return e.dynamicChildren = Ot > 0 ? ge || at : null, Bo(), Ot > 0 && ge && ge.push(e), e;
}
function V(e, t, s, n, r, i) {
  return Gr(
    H(
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
function Qe(e, t, s, n, r) {
  return Gr(
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
function yt(e, t) {
  return e.type === t.type && e.key === t.key;
}
const zr = ({ key: e }) => e ?? null, zt = ({
  ref: e,
  ref_key: t,
  ref_for: s
}) => (typeof e == "number" && (e = "" + e), e != null ? X(e) || ne(e) || M(e) ? { i: $e, r: e, k: t, f: !!s } : e : null);
function H(e, t = null, s = null, n = 0, r = null, i = e === ee ? 0 : 1, o = !1, l = !1) {
  const a = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e,
    props: t,
    key: t && zr(t),
    ref: t && zt(t),
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
    ctx: $e
  };
  return l ? (on(a, s), i & 128 && e.normalize(a)) : s && (a.shapeFlag |= X(s) ? 8 : 16), Ot > 0 && // avoid a block node from tracking itself
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
  if ((!e || e === uo) && (e = nt), Jr(e)) {
    const l = pt(
      e,
      t,
      !0
      /* mergeRef: true */
    );
    return s && on(l, s), Ot > 0 && !i && ge && (l.shapeFlag & 6 ? ge[ge.indexOf(e)] = l : ge.push(l)), l.patchFlag = -2, l;
  }
  if (Zo(e) && (e = e.__vccOpts), t) {
    t = Uo(t);
    let { class: l, style: a } = t;
    l && !X(l) && (t.class = it(l)), q(a) && (tn(a) && !E(a) && (a = re({}, a)), t.style = pe(a));
  }
  const o = X(e) ? 1 : qr(e) ? 128 : Qi(e) ? 64 : q(e) ? 4 : M(e) ? 2 : 0;
  return H(
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
  return e ? tn(e) || Dr(e) ? re({}, e) : e : null;
}
function pt(e, t, s = !1, n = !1) {
  const { props: r, ref: i, patchFlag: o, children: l, transition: a } = e, f = t ? Vo(r || {}, t) : r, d = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e.type,
    props: f,
    key: f && zr(f),
    ref: t && t.ref ? (
      // #2078 in the case of <component :is="vnode" ref="extra"/>
      // if the vnode itself already has a ref, cloneVNode will need to merge
      // the refs so the single vnode can be set on multiple refs
      s && i ? E(i) ? i.concat(zt(t)) : [i, zt(t)] : zt(t)
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
    ssContent: e.ssContent && pt(e.ssContent),
    ssFallback: e.ssFallback && pt(e.ssFallback),
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
function xt(e = " ", t = 0) {
  return be(ps, null, e, t);
}
function Oe(e = "", t = !1) {
  return t ? (F(), Qe(nt, null, e)) : be(nt, null, e);
}
function Ce(e) {
  return e == null || typeof e == "boolean" ? be(nt) : E(e) ? be(
    ee,
    null,
    // #3666, avoid reference pollution when reusing vnode
    e.slice()
  ) : Jr(e) ? ke(e) : be(ps, null, String(e));
}
function ke(e) {
  return e.el === null && e.patchFlag !== -1 || e.memo ? e : pt(e);
}
function on(e, t) {
  let s = 0;
  const { shapeFlag: n } = e;
  if (t == null)
    t = null;
  else if (E(t))
    s = 16;
  else if (typeof t == "object")
    if (n & 65) {
      const r = t.default;
      r && (r._c && (r._d = !1), on(e, r()), r._c && (r._d = !0));
      return;
    } else {
      s = 32;
      const r = t._;
      !r && !Dr(t) ? t._ctx = $e : r === 3 && $e && ($e.slots._ === 1 ? t._ = 1 : (t._ = 2, e.patchFlag |= 1024));
    }
  else M(t) ? (t = { default: t, _ctx: $e }, s = 32) : (t = String(t), n & 64 ? (s = 16, t = [xt(t)]) : s = 8);
  e.children = t, e.shapeFlag |= s;
}
function Vo(...e) {
  const t = {};
  for (let s = 0; s < e.length; s++) {
    const n = e[s];
    for (const r in n)
      if (r === "class")
        t.class !== n.class && (t.class = it([t.class, n.class]));
      else if (r === "style")
        t.style = pe([t.style, n.style]);
      else if (os(r)) {
        const i = t[r], o = n[r];
        o && i !== o && !(E(i) && i.includes(o)) && (t[r] = i ? [].concat(i, o) : o);
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
    (s) => Dt = s
  );
}
const Lt = (e) => {
  const t = ce;
  return ns(e), e.scope.on(), () => {
    e.scope.off(), ns(t);
  };
}, $n = () => {
  ce && ce.scope.off(), ns(null);
};
function Yr(e) {
  return e.vnode.shapeFlag & 4;
}
let Dt = !1;
function Jo(e, t = !1, s = !1) {
  t && Hs(t);
  const { props: n, children: r } = e.vnode, i = Yr(e);
  vo(e, n, i, t), Ao(e, r, s);
  const o = i ? zo(e, t) : void 0;
  return t && Hs(!1), o;
}
function zo(e, t) {
  const s = e.type;
  e.accessCache = /* @__PURE__ */ Object.create(null), e.proxy = new Proxy(e.ctx, fo);
  const { setup: n } = s;
  if (n) {
    Ve();
    const r = e.setupContext = n.length > 1 ? Xo(e) : null, i = Lt(e), o = Nt(
      n,
      e,
      0,
      [
        e.props,
        r
      ]
    ), l = qn(o);
    if (Ke(), i(), (l || e.sp) && !$t(e) && Sr(e), l) {
      if (o.then($n, $n), t)
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
  M(t) ? e.type.__ssrInlineRender ? e.ssrRender = t : e.render = t : q(t) && (e.setupState = mr(t)), Xr(e);
}
function Xr(e, t, s) {
  const n = e.type;
  e.render || (e.render = n.render || Te);
  {
    const r = Lt(e);
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
function ln(e) {
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
function Zo(e) {
  return M(e) && "__vccOpts" in e;
}
const tt = (e, t) => Ki(e, t, Dt), Qo = "3.5.13";
/**
* @vue/runtime-dom v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
let js;
const En = typeof window < "u" && window.trustedTypes;
if (En)
  try {
    js = /* @__PURE__ */ En.createPolicy("vue", {
      createHTML: (e) => e
    });
  } catch {
  }
const Zr = js ? (e) => js.createHTML(e) : (e) => e, el = "http://www.w3.org/2000/svg", tl = "http://www.w3.org/1998/Math/MathML", Pe = typeof document < "u" ? document : null, Mn = Pe && /* @__PURE__ */ Pe.createElement("template"), sl = {
  insert: (e, t, s) => {
    t.insertBefore(e, s || null);
  },
  remove: (e) => {
    const t = e.parentNode;
    t && t.removeChild(e);
  },
  createElement: (e, t, s, n) => {
    const r = t === "svg" ? Pe.createElementNS(el, e) : t === "mathml" ? Pe.createElementNS(tl, e) : s ? Pe.createElement(e, { is: s }) : Pe.createElement(e);
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
  Pn in e && (e[Pn] = i ? n.display : "", e[il] && (n.display = "none"));
}
const Rn = /\s*!important$/;
function Yt(e, t, s) {
  if (E(s))
    s.forEach((n) => Yt(e, t, n));
  else if (s == null && (s = ""), t.startsWith("--"))
    e.setProperty(t, s);
  else {
    const n = al(e, t);
    Rn.test(s) ? e.setProperty(
      rt(n),
      s.replace(Rn, ""),
      "important"
    ) : e[n] = s;
  }
}
const On = ["Webkit", "Moz", "ms"], Cs = {};
function al(e, t) {
  const s = Cs[t];
  if (s)
    return s;
  let n = We(t);
  if (n !== "filter" && n in e)
    return Cs[t] = n;
  n = zn(n);
  for (let r = 0; r < On.length; r++) {
    const i = On[r] + n;
    if (i in e)
      return Cs[t] = i;
  }
  return t;
}
const Dn = "http://www.w3.org/1999/xlink";
function Fn(e, t, s, n, r, i = bi(t)) {
  n && t.startsWith("xlink:") ? s == null ? e.removeAttributeNS(Dn, t.slice(6, t.length)) : e.setAttributeNS(Dn, t, s) : s == null || i && !Xn(s) ? e.removeAttribute(t) : e.setAttribute(
    t,
    i ? "" : Ue(s) ? String(s) : s
  );
}
function Nn(e, t, s, n, r) {
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
      const f = i[t] = ml(
        n,
        r
      );
      ul(e, l, f, a);
    } else o && (fl(e, l, o, a), i[t] = void 0);
  }
}
const kn = /(?:Once|Passive|Capture)$/;
function hl(e) {
  let t;
  if (kn.test(e)) {
    t = {};
    let n;
    for (; n = e.match(kn); )
      e = e.slice(0, e.length - n[0].length), t[n[0].toLowerCase()] = !0;
  }
  return [e[2] === ":" ? e.slice(3) : rt(e.slice(2)), t];
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
  if (E(t)) {
    const s = e.stopImmediatePropagation;
    return e.stopImmediatePropagation = () => {
      s.call(e), e._stopped = !0;
    }, t.map(
      (n) => (r) => !r._stopped && n && n(r)
    );
  } else
    return t;
}
const Hn = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && // lowercase letter
e.charCodeAt(2) > 96 && e.charCodeAt(2) < 123, bl = (e, t, s, n, r, i) => {
  const o = r === "svg";
  t === "class" ? rl(e, n, o) : t === "style" ? cl(e, s, n) : os(t) ? Ks(t) || dl(e, t, s, n, i) : (t[0] === "." ? (t = t.slice(1), !0) : t[0] === "^" ? (t = t.slice(1), !1) : wl(e, t, n, o)) ? (Nn(e, t, n), !e.tagName.includes("-") && (t === "value" || t === "checked" || t === "selected") && Fn(e, t, n, o, i, t !== "value")) : /* #11081 force set props for possible async custom element */ e._isVueCE && (/[A-Z]/.test(t) || !X(n)) ? Nn(e, We(t), n, i, t) : (t === "true-value" ? e._trueValue = n : t === "false-value" && (e._falseValue = n), Fn(e, t, n, o));
};
function wl(e, t, s, n) {
  if (n)
    return !!(t === "innerHTML" || t === "textContent" || t in e && Hn(t) && M(s));
  if (t === "spellcheck" || t === "draggable" || t === "translate" || t === "form" || t === "list" && e.tagName === "INPUT" || t === "type" && e.tagName === "TEXTAREA")
    return !1;
  if (t === "width" || t === "height") {
    const r = e.tagName;
    if (r === "IMG" || r === "VIDEO" || r === "CANVAS" || r === "SOURCE")
      return !1;
  }
  return Hn(t) && X(s) ? !1 : t in e;
}
const yl = /* @__PURE__ */ re({ patchProp: bl }, sl);
let jn;
function vl() {
  return jn || (jn = $o(yl));
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
const Bs = "@runner", Bn = 5e3;
function $l() {
  return { runs: {}, logs: [], seen: {}, maxCursor: 0 };
}
function Qr(e) {
  return e.outcome !== null || e.abandoned;
}
function Tl(e) {
  return Object.values(e.phases).sort((t, s) => t.order - s.order);
}
function qt(e) {
  e.visible = Tl(e).map((t) => t.instanceId);
}
function El(e, t, s) {
  e.visible = e.visible.map((n) => n === t ? s : n);
  for (const n of e.arrows)
    n.from === t && (n.from = s), n.to === t && (n.to = s);
}
const Ml = /* @__PURE__ */ new Set([
  "phase_start",
  "bound",
  "progress",
  "tool_call",
  "tool_result",
  "message",
  "log"
]);
function Wn(e) {
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
function Pl(e, t) {
  return t.phase_id && e.instanceOfPhase[t.phase_id] ? e.instanceOfPhase[t.phase_id] : t.instance_id || t.phase_id;
}
function Rl(e, t) {
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
  const s = Date.parse(t.recorded_at) || 0, n = Pl(e, t);
  if (!n) return;
  let r;
  if (t.kind === "bound" ? r = Rl(e, t) : ((i = e.phases)[n] ?? (i[n] = ei(t, n)), r = e.phases[n]), t.attempt !== null && t.attempt !== void 0 && (r.attempt = t.attempt), Ol(e, t, r.instanceId), t.kind === "constructed" ? (r.constructed = !0, r.className = t.message) : t.kind === "purpose" ? r.purpose = t.message : t.kind === "cleanup" ? (r.cleanup = t.message, !r.started && r.outcome === null && (r.abandoned = !0)) : t.kind === "error" && (r.error = t.message), r.outcome !== null || r.abandoned) {
    qt(e);
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
    ), qt(e);
    return;
  }
  if (t.kind === "waiting" ? (r.waitDeadlineAt = t.deadline_at ? Date.parse(t.deadline_at) : null, r.waitReason = t.message, r.lastProgressAt = s) : Ml.has(t.kind) && (r.waitDeadlineAt = null, r.waitReason = "", r.lastProgressAt = s), (t.kind === "phase_start" || t.kind === "bound") && !r.started) {
    r.started = !0, r.startedAt = s, t.kind === "phase_start" && (r.phaseId = t.phase_id), rs(e, t, Bs, r.instanceId, r.name, !1), qt(e);
    return;
  }
  qt(e);
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
    (i = r.runs)[o = f.run_id] ?? (i[o] = Wn(f));
    const d = r.runs[f.run_id];
    d.status = f.status, d.endedAt = f.ended_at;
  }
  for (const f of s.sort((d, p) => d.cursor - p.cursor)) {
    r.seen[f.event_id] = !0, r.maxCursor = Math.max(r.maxCursor, f.cursor), (l = r.runs)[a = f.run_id] ?? (l[a] = Wn({
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
  return r.logs.sort((f, d) => f.cursor - d.cursor), r.logs.length > Bn && r.logs.splice(0, r.logs.length - Bn), r;
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
    statusLabel: ti[s],
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
    o.map((m, I) => [m.instanceId, I])
  ), a = Date.parse(e.startedAt) || (((p = e.arrows[0]) == null ? void 0 : p.at) ?? 0), d = e.arrows.filter((m) => l.has(m.from) && l.has(m.to)).sort((m, I) => m.cursor - I.cursor).map((m) => ({
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
    const I = l.get(m.instanceId), R = d.findIndex((D) => D.to === I || D.from === I), P = d.findIndex(
      (D) => D.kind === "phase_end" && D.from === I
    ), Y = e.phases[m.instanceId];
    m.activeFrom = Y != null && Y.started && R >= 0 ? R : null, m.activeTo = P >= 0 ? P : null;
  }
  return { runId: e.runId, columns: o, rows: d };
}
function Vl(e) {
  const t = e.replace(/\.py$/, "").replace(/^adw_/, "").replace(/^(interface|op)_/, "").replace(/_/g, " ").trim();
  return t ? t[0].toUpperCase() + t.slice(1) : "An ADW";
}
function Kl(e) {
  if (!e) return "No ADW has run yet -- the next one started will show here";
  const t = Vl(e.adwName), s = e.visible.map((f) => e.phases[f]).filter(Boolean), n = s.length, i = s.filter((f) => f.started && !Qr(f)).at(-1), o = s.find((f) => f.outcome === "fail"), l = (f) => `step ${s.indexOf(f) + 1} of ${n}, ${f.name.replace(/_/g, " ")}`, a = (f) => `${f} step${f === 1 ? "" : "s"}`;
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
}, lc = ["data-kind", "data-run"], cc = /* @__PURE__ */ qe({
  __name: "LogPane",
  props: {
    lines: {},
    label: {},
    tall: { type: Boolean }
  },
  setup(e) {
    const t = e, s = Xt(null), n = Xt(!0);
    function r() {
      const i = s.value;
      i && (n.value = i.scrollHeight - i.scrollTop - i.clientHeight <= 8);
    }
    return Jt(() => t.lines.length, async () => {
      n.value && (await br(), s.value && (s.value.scrollTop = s.value.scrollHeight));
    }, { immediate: !0 }), (i, o) => (F(), V("div", nc, [
      H("div", rc, [
        H("span", ic, z(i.label), 1),
        H("span", null, z(i.lines.length) + " line" + z(i.lines.length === 1 ? "" : "s") + z(n.value ? "" : " · paused (scroll to bottom to follow)"), 1)
      ]),
      H("div", {
        ref_key: "host",
        ref: s,
        class: it(["adwdbg-log-lines", { "adwdbg-log-tall": i.tall }]),
        role: "log",
        onScroll: r
      }, [
        i.lines.length === 0 ? (F(), V("div", oc, "No ADW events to show.")) : Oe("", !0),
        (F(!0), V(ee, null, ct(i.lines, (l) => (F(), V("div", {
          key: l.eventId,
          class: "adwdbg-log-line",
          "data-kind": l.kind,
          "data-run": l.runId
        }, z(l.text), 9, lc))), 128))
      ], 34)
    ]));
  }
}), St = 78, ac = 170, Ft = 40, cn = 22, Es = 11;
function Us(e, t) {
  return (e + 0.5) / Math.max(1, t) * 100;
}
function uc(e) {
  return 100 / Math.max(1, e);
}
function is(e) {
  return cn + e * Ft + Ft * 0.62;
}
function si(e) {
  return cn * 2 + Math.max(1, e) * Ft;
}
function fc(e, t, s) {
  const n = is(e) - Es, r = t === null ? si(s) - cn / 2 : is(Math.max(e, t)) + Es;
  return { top: n, height: Math.max(Es * 2, r - n) };
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
    const t = e, s = tt(() => fc(t.from, t.to, t.rows));
    return (n, r) => (F(), V("span", {
      class: it(["sd-bar", { "sd-bar-open": n.to === null }]),
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
    return (t, s) => (F(), V("div", {
      class: "sd-lifeline-track",
      "data-lifeline": t.column.instanceId,
      style: pe({ left: `${t.centre}%` })
    }, [
      s[0] || (s[0] = H("span", { class: "sd-lifeline" }, null, -1)),
      t.column.activeFrom !== null && t.column.activeFrom !== void 0 ? (F(), Qe(pc, {
        key: 0,
        from: t.column.activeFrom,
        to: t.column.activeTo ?? null,
        rows: t.rows,
        status: t.column.status
      }, null, 8, ["from", "to", "rows", "status"])) : Oe("", !0)
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
    const t = e, s = tt(() => dc(t.row.from, t.row.to)), n = tt(() => {
      const r = `${is(t.index) - Ft * 0.62}px`, i = `${Ft}px`, o = Us(t.row.from, t.count);
      if (s.value === "self") {
        const a = t.row.from === t.count - 1 ? 0.46 : 0.92;
        return { top: r, height: i, left: `${o}%`, width: `${uc(t.count) * a}%` };
      }
      const l = Us(t.row.to, t.count);
      return { top: r, height: i, left: `${Math.min(o, l)}%`, width: `${Math.abs(l - o)}%` };
    });
    return (r, i) => (F(), V("div", {
      class: it(["sd-message", [`sd-${s.value}`, { "sd-dashed": r.row.dashed }]]),
      "data-kind": r.row.kind,
      "data-row": r.index,
      style: pe(n.value)
    }, [
      H("div", {
        class: "sd-label",
        title: r.row.text
      }, [
        H("span", wc, z(r.row.text), 1)
      ], 8, bc),
      i[0] || (i[0] = H("div", { class: "sd-line" }, [
        H("span", { class: "sd-head" })
      ], -1))
    ], 14, _c));
  }
}), vc = ["data-status", "data-instance", "data-edge", "data-participant", "title", "aria-pressed"], xc = { class: "sd-name" }, Sc = { class: "sd-status" }, Un = /* @__PURE__ */ qe({
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
      class: it(["sd-box", { "sd-selected": i.column.selected, "sd-runner": i.column.kind === "runner" }]),
      "data-status": i.column.status,
      "data-instance": i.column.instanceId,
      "data-edge": i.edge,
      "data-participant": i.column.kind ?? "phase",
      title: r(),
      "aria-pressed": i.column.selected,
      onClick: o[0] || (o[0] = (l) => n("select", i.column))
    }, [
      H("span", xc, [
        xt(z(i.column.name), 1),
        i.column.attempt && i.column.attempt > 1 ? (F(), V(ee, { key: 0 }, [
          xt(" · attempt " + z(i.column.attempt), 1)
        ], 64)) : Oe("", !0)
      ]),
      H("span", Sc, [
        xt(z(i.column.statusLabel), 1),
        i.column.detail ? (F(), V(ee, { key: 0 }, [
          xt(" · " + z(i.column.detail), 1)
        ], 64)) : Oe("", !0)
      ])
    ], 10, vc));
  }
}), Ic = /* @__PURE__ */ qe({
  __name: "TimeAxis",
  props: {
    rows: {}
  },
  setup(e) {
    return (t, s) => (F(), V("div", {
      class: "sd-axis",
      style: pe({ width: `${He(St)}px` }),
      "aria-hidden": "true"
    }, [
      (F(!0), V(ee, null, ct(t.rows, (n, r) => (F(), V("span", {
        key: n.id,
        class: "sd-tick",
        style: pe({ top: `${He(is)(r)}px` })
      }, z(n.elapsed), 5))), 128))
    ], 4));
  }
}), Ac = { class: "sd" }, Cc = { class: "sd-tools" }, $c = { class: "sd-zoom-value" }, Tc = { class: "sd-hint" }, Ec = { class: "sd-scroll" }, Mc = /* @__PURE__ */ qe({
  __name: "SequenceDiagram",
  props: {
    model: {},
    hint: { default: "Click a phase box to filter the events below; click the ADW box for all events." }
  },
  emits: ["phase-click", "runner-click"],
  setup(e, { emit: t }) {
    const s = e, n = t, r = Xt(1), i = tt(() => Math.max(1, s.model.columns.length)), o = tt(() => s.model.rows.length), l = tt(() => `${St + i.value * ac}px`);
    function a(f) {
      f.kind === "runner" ? n("runner-click") : n("phase-click", f.instanceId);
    }
    return (f, d) => (F(), V("div", Ac, [
      H("div", Cc, [
        H("button", {
          type: "button",
          class: "sd-zoom",
          "aria-label": "Zoom out",
          onClick: d[0] || (d[0] = (p) => r.value = Math.max(0.4, r.value - 0.1))
        }, "-"),
        H("span", $c, z(Math.round(r.value * 100)) + "%", 1),
        H("button", {
          type: "button",
          class: "sd-zoom",
          "aria-label": "Zoom in",
          onClick: d[1] || (d[1] = (p) => r.value = Math.min(2, r.value + 0.1))
        }, "+"),
        H("button", {
          type: "button",
          class: "sd-zoom",
          onClick: d[2] || (d[2] = (p) => r.value = 1)
        }, "Reset"),
        H("span", Tc, z(f.hint), 1)
      ]),
      H("div", Ec, [
        H("div", {
          class: "sd-canvas",
          style: pe({ zoom: r.value, minWidth: l.value })
        }, [
          H("div", {
            class: "sd-titles sd-titles-top",
            style: pe({ marginLeft: `${He(St)}px` })
          }, [
            (F(!0), V(ee, null, ct(f.model.columns, (p) => (F(), Qe(Un, {
              key: p.instanceId,
              column: p,
              edge: "top",
              onSelect: a
            }, null, 8, ["column"]))), 128))
          ], 4),
          H("div", {
            class: "sd-body",
            style: pe({ height: `${He(si)(o.value)}px` })
          }, [
            be(Ic, {
              rows: f.model.rows
            }, null, 8, ["rows"]),
            H("div", {
              class: "sd-plot",
              style: pe({ left: `${He(St)}px` })
            }, [
              (F(!0), V(ee, null, ct(f.model.columns, (p, m) => (F(), Qe(mc, {
                key: p.instanceId,
                column: p,
                centre: He(Us)(m, i.value),
                rows: o.value
              }, null, 8, ["column", "centre", "rows"]))), 128)),
              (F(!0), V(ee, null, ct(f.model.rows, (p, m) => (F(), Qe(yc, {
                key: p.id,
                row: p,
                index: m,
                count: i.value
              }, null, 8, ["row", "index", "count"]))), 128))
            ], 4)
          ], 4),
          H("div", {
            class: "sd-titles sd-titles-bottom",
            style: pe({ marginLeft: `${He(St)}px` })
          }, [
            (F(!0), V(ee, null, ct(f.model.columns, (p) => (F(), Qe(Un, {
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
}), Pc = {
  key: 0,
  class: "adwseq",
  "aria-label": "ADW run sequence diagram"
}, Rc = { class: "adwseq-head" }, Oc = { "data-field": "headline" }, Dc = ["data-run-status"], Fc = {
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
}, jc = ["aria-label"], Vn = "@all", Bc = /* @__PURE__ */ qe({
  __name: "RunSequencePanel",
  props: {
    controller: {}
  },
  setup(e) {
    const t = e, s = Bi(null), n = Xt(null), r = t.controller.subscribe((l) => {
      s.value = l;
    });
    Cr(r), Tr((l) => (t.controller.reportRenderError(l instanceof Error ? l.message : String(l)), !1));
    function i(l) {
      if (n.value === l) {
        n.value = null, t.controller.allEvents();
        return;
      }
      n.value = l, l === Vn ? t.controller.allEvents() : t.controller.selectPhase(l);
    }
    function o() {
      n.value && i(n.value);
    }
    return (l, a) => s.value ? (F(), V("section", Pc, [
      H("header", Rc, [
        H("strong", Oc, z(s.value.headline), 1),
        s.value.runStatus ? (F(), V("span", {
          key: 0,
          class: "adwdbg-chip",
          "data-run-status": s.value.runStatus,
          "data-field": "status"
        }, z(s.value.runStatus), 9, Dc)) : Oe("", !0)
      ]),
      s.value.connection.status === "disconnected" ? (F(), V("p", Fc, " Event feed disconnected (attempt " + z(s.value.connection.attempts) + "): " + z(s.value.connection.reason) + ". Showing the last events received. ", 1)) : s.value.connection.status === "degraded" ? (F(), V("p", Nc, " The ADW trace cannot be read: " + z(s.value.connection.reason), 1)) : Oe("", !0),
      s.value.renderError ? (F(), V("p", Lc, " Diagram could not be redrawn (" + z(s.value.renderError) + "). Showing the last good diagram. ", 1)) : Oe("", !0),
      H("div", kc, [
        s.value.diagram.columns.length ? (F(), Qe(Mc, {
          key: 0,
          model: s.value.diagram,
          hint: "Click a phase to open its console; click it again to close.",
          onPhaseClick: a[0] || (a[0] = (f) => i(f)),
          onRunnerClick: a[1] || (a[1] = (f) => i(Vn))
        }, null, 8, ["model"])) : (F(), V("p", Hc, z(s.value.connection.status === "connecting" ? "Loading the run…" : "This run has not started a step yet."), 1)),
        n.value ? (F(), V("div", {
          key: 2,
          class: "adwseq-popup",
          "data-field": "popup",
          role: "dialog",
          "aria-label": s.value.filterLabel
        }, [
          H("button", {
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
