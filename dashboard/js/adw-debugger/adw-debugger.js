var zi = Object.defineProperty;
var Yi = (e, t, s) =>
  t in e
    ? zi(e, t, { enumerable: !0, configurable: !0, writable: !0, value: s })
    : (e[t] = s);
var Y = (e, t, s) => Yi(e, typeof t != "symbol" ? t + "" : t, s);
/**
 * @vue/shared v3.5.13
 * (c) 2018-present Yuxi (Evan) You and Vue contributors
 * @license MIT
 **/
/*! #__NO_SIDE_EFFECTS__ */
// @__NO_SIDE_EFFECTS__
function $s(e) {
  const t = /* @__PURE__ */ Object.create(null);
  for (const s of e.split(",")) t[s] = 1;
  return (s) => s in t;
}
const K = {},
  rt = [],
  Ee = () => {},
  Zi = () => !1,
  Zt = (e) =>
    e.charCodeAt(0) === 111 &&
    e.charCodeAt(1) === 110 && // uppercase letter
    (e.charCodeAt(2) > 122 || e.charCodeAt(2) < 97),
  Fs = (e) => e.startsWith("onUpdate:"),
  ie = Object.assign,
  Ls = (e, t) => {
    const s = e.indexOf(t);
    s > -1 && e.splice(s, 1);
  },
  Xi = Object.prototype.hasOwnProperty,
  L = (e, t) => Xi.call(e, t),
  R = Array.isArray,
  ot = (e) => Xt(e) === "[object Map]",
  Fn = (e) => Xt(e) === "[object Set]",
  M = (e) => typeof e == "function",
  Z = (e) => typeof e == "string",
  We = (e) => typeof e == "symbol",
  q = (e) => e !== null && typeof e == "object",
  Ln = (e) => (q(e) || M(e)) && M(e.then) && M(e.catch),
  Nn = Object.prototype.toString,
  Xt = (e) => Nn.call(e),
  Qi = (e) => Xt(e).slice(8, -1),
  kn = (e) => Xt(e) === "[object Object]",
  Ns = (e) => Z(e) && e !== "NaN" && e[0] !== "-" && "" + parseInt(e, 10) === e,
  bt = /* @__PURE__ */ $s(
    // the leading comma is intentional so empty string "" is also included
    ",key,ref,ref_for,ref_key,onVnodeBeforeMount,onVnodeMounted,onVnodeBeforeUpdate,onVnodeUpdated,onVnodeBeforeUnmount,onVnodeUnmounted",
  ),
  Qt = (e) => {
    const t = /* @__PURE__ */ Object.create(null);
    return (s) => t[s] || (t[s] = e(s));
  },
  er = /-(\w)/g,
  Be = Qt((e) => e.replace(er, (t, s) => (s ? s.toUpperCase() : ""))),
  tr = /\B([A-Z])/g,
  st = Qt((e) => e.replace(tr, "-$1").toLowerCase()),
  Hn = Qt((e) => e.charAt(0).toUpperCase() + e.slice(1)),
  cs = Qt((e) => (e ? `on${Hn(e)}` : "")),
  je = (e, t) => !Object.is(e, t),
  as = (e, ...t) => {
    for (let s = 0; s < e.length; s++) e[s](...t);
  },
  jn = (e, t, s, n = !1) => {
    Object.defineProperty(e, t, {
      configurable: !0,
      enumerable: !1,
      writable: n,
      value: s,
    });
  },
  sr = (e) => {
    const t = parseFloat(e);
    return isNaN(t) ? e : t;
  };
let nn;
const es = () =>
  nn ||
  (nn =
    typeof globalThis < "u"
      ? globalThis
      : typeof self < "u"
        ? self
        : typeof window < "u"
          ? window
          : typeof global < "u"
            ? global
            : {});
function ke(e) {
  if (R(e)) {
    const t = {};
    for (let s = 0; s < e.length; s++) {
      const n = e[s],
        i = Z(n) ? or(n) : ke(n);
      if (i) for (const r in i) t[r] = i[r];
    }
    return t;
  } else if (Z(e) || q(e)) return e;
}
const nr = /;(?![^(]*\))/g,
  ir = /:([^]+)/,
  rr = /\/\*[^]*?\*\//g;
function or(e) {
  const t = {};
  return (
    e
      .replace(rr, "")
      .split(nr)
      .forEach((s) => {
        if (s) {
          const n = s.split(ir);
          n.length > 1 && (t[n[0].trim()] = n[1].trim());
        }
      }),
    t
  );
}
function Xe(e) {
  let t = "";
  if (Z(e)) t = e;
  else if (R(e))
    for (let s = 0; s < e.length; s++) {
      const n = Xe(e[s]);
      n && (t += n + " ");
    }
  else if (q(e)) for (const s in e) e[s] && (t += s + " ");
  return t.trim();
}
const lr =
    "itemscope,allowfullscreen,formnovalidate,ismap,nomodule,novalidate,readonly",
  cr = /* @__PURE__ */ $s(lr);
function Bn(e) {
  return !!e || e === "";
}
const Wn = (e) => !!(e && e.__v_isRef === !0),
  U = (e) =>
    Z(e)
      ? e
      : e == null
        ? ""
        : R(e) || (q(e) && (e.toString === Nn || !M(e.toString)))
          ? Wn(e)
            ? U(e.value)
            : JSON.stringify(e, Un, 2)
          : String(e),
  Un = (e, t) =>
    Wn(t)
      ? Un(e, t.value)
      : ot(t)
        ? {
            [`Map(${t.size})`]: [...t.entries()].reduce(
              (s, [n, i], r) => ((s[us(n, r) + " =>"] = i), s),
              {},
            ),
          }
        : Fn(t)
          ? {
              [`Set(${t.size})`]: [...t.values()].map((s) => us(s)),
            }
          : We(t)
            ? us(t)
            : q(t) && !R(t) && !kn(t)
              ? String(t)
              : t,
  us = (e, t = "") => {
    var s;
    return (
      // Symbol.description in es2019+ so we need to cast here to pass
      // the lib: es2016 check
      We(e) ? `Symbol(${((s = e.description)) != null ? s : t})` : e
    );
  };
/**
 * @vue/reactivity v3.5.13
 * (c) 2018-present Yuxi (Evan) You and Vue contributors
 * @license MIT
 **/
let he;
class ar {
  constructor(t = !1) {
    (this.detached = t),
      (this._active = !0),
      (this.effects = []),
      (this.cleanups = []),
      (this._isPaused = !1),
      (this.parent = he),
      !t && he && (this.index = (he.scopes || (he.scopes = [])).push(this) - 1);
  }
  get active() {
    return this._active;
  }
  pause() {
    if (this._active) {
      this._isPaused = !0;
      let t, s;
      if (this.scopes)
        for (t = 0, s = this.scopes.length; t < s; t++) this.scopes[t].pause();
      for (t = 0, s = this.effects.length; t < s; t++) this.effects[t].pause();
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
        for (t = 0, s = this.scopes.length; t < s; t++) this.scopes[t].resume();
      for (t = 0, s = this.effects.length; t < s; t++) this.effects[t].resume();
    }
  }
  run(t) {
    if (this._active) {
      const s = he;
      try {
        return (he = this), t();
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
      for (s = 0, n = this.effects.length; s < n; s++) this.effects[s].stop();
      for (this.effects.length = 0, s = 0, n = this.cleanups.length; s < n; s++)
        this.cleanups[s]();
      if (((this.cleanups.length = 0), this.scopes)) {
        for (s = 0, n = this.scopes.length; s < n; s++) this.scopes[s].stop(!0);
        this.scopes.length = 0;
      }
      if (!this.detached && this.parent && !t) {
        const i = this.parent.scopes.pop();
        i &&
          i !== this &&
          ((this.parent.scopes[this.index] = i), (i.index = this.index));
      }
      this.parent = void 0;
    }
  }
}
function ur() {
  return he;
}
let W;
const fs = /* @__PURE__ */ new WeakSet();
class Vn {
  constructor(t) {
    (this.fn = t),
      (this.deps = void 0),
      (this.depsTail = void 0),
      (this.flags = 5),
      (this.next = void 0),
      (this.cleanup = void 0),
      (this.scheduler = void 0),
      he && he.active && he.effects.push(this);
  }
  pause() {
    this.flags |= 64;
  }
  resume() {
    this.flags & 64 &&
      ((this.flags &= -65), fs.has(this) && (fs.delete(this), this.trigger()));
  }
  /**
   * @internal
   */
  notify() {
    (this.flags & 2 && !(this.flags & 32)) || this.flags & 8 || Gn(this);
  }
  run() {
    if (!(this.flags & 1)) return this.fn();
    (this.flags |= 2), rn(this), qn(this);
    const t = W,
      s = me;
    (W = this), (me = !0);
    try {
      return this.fn();
    } finally {
      Jn(this), (W = t), (me = s), (this.flags &= -3);
    }
  }
  stop() {
    if (this.flags & 1) {
      for (let t = this.deps; t; t = t.nextDep) js(t);
      (this.deps = this.depsTail = void 0),
        rn(this),
        this.onStop && this.onStop(),
        (this.flags &= -2);
    }
  }
  trigger() {
    this.flags & 64
      ? fs.add(this)
      : this.scheduler
        ? this.scheduler()
        : this.runIfDirty();
  }
  /**
   * @internal
   */
  runIfDirty() {
    ws(this) && this.run();
  }
  get dirty() {
    return ws(this);
  }
}
let Kn = 0,
  yt,
  vt;
function Gn(e, t = !1) {
  if (((e.flags |= 8), t)) {
    (e.next = vt), (vt = e);
    return;
  }
  (e.next = yt), (yt = e);
}
function ks() {
  Kn++;
}
function Hs() {
  if (--Kn > 0) return;
  if (vt) {
    let t = vt;
    for (vt = void 0; t; ) {
      const s = t.next;
      (t.next = void 0), (t.flags &= -9), (t = s);
    }
  }
  let e;
  for (; yt; ) {
    let t = yt;
    for (yt = void 0; t; ) {
      const s = t.next;
      if (((t.next = void 0), (t.flags &= -9), t.flags & 1))
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
function qn(e) {
  for (let t = e.deps; t; t = t.nextDep)
    (t.version = -1),
      (t.prevActiveLink = t.dep.activeLink),
      (t.dep.activeLink = t);
}
function Jn(e) {
  let t,
    s = e.depsTail,
    n = s;
  for (; n; ) {
    const i = n.prevDep;
    n.version === -1 ? (n === s && (s = i), js(n), fr(n)) : (t = n),
      (n.dep.activeLink = n.prevActiveLink),
      (n.prevActiveLink = void 0),
      (n = i);
  }
  (e.deps = t), (e.depsTail = s);
}
function ws(e) {
  for (let t = e.deps; t; t = t.nextDep)
    if (
      t.dep.version !== t.version ||
      (t.dep.computed && (zn(t.dep.computed) || t.dep.version !== t.version))
    )
      return !0;
  return !!e._dirty;
}
function zn(e) {
  if (
    (e.flags & 4 && !(e.flags & 16)) ||
    ((e.flags &= -17), e.globalVersion === It)
  )
    return;
  e.globalVersion = It;
  const t = e.dep;
  if (((e.flags |= 2), t.version > 0 && !e.isSSR && e.deps && !ws(e))) {
    e.flags &= -3;
    return;
  }
  const s = W,
    n = me;
  (W = e), (me = !0);
  try {
    qn(e);
    const i = e.fn(e._value);
    (t.version === 0 || je(i, e._value)) && ((e._value = i), t.version++);
  } catch (i) {
    throw (t.version++, i);
  } finally {
    (W = s), (me = n), Jn(e), (e.flags &= -3);
  }
}
function js(e, t = !1) {
  const { dep: s, prevSub: n, nextSub: i } = e;
  if (
    (n && ((n.nextSub = i), (e.prevSub = void 0)),
    i && ((i.prevSub = n), (e.nextSub = void 0)),
    s.subs === e && ((s.subs = n), !n && s.computed))
  ) {
    s.computed.flags &= -5;
    for (let r = s.computed.deps; r; r = r.nextDep) js(r, !0);
  }
  !t && !--s.sc && s.map && s.map.delete(s.key);
}
function fr(e) {
  const { prevDep: t, nextDep: s } = e;
  t && ((t.nextDep = s), (e.prevDep = void 0)),
    s && ((s.prevDep = t), (e.nextDep = void 0));
}
let me = !0;
const Yn = [];
function Ue() {
  Yn.push(me), (me = !1);
}
function Ve() {
  const e = Yn.pop();
  me = e === void 0 ? !0 : e;
}
function rn(e) {
  const { cleanup: t } = e;
  if (((e.cleanup = void 0), t)) {
    const s = W;
    W = void 0;
    try {
      t();
    } finally {
      W = s;
    }
  }
}
let It = 0;
class dr {
  constructor(t, s) {
    (this.sub = t),
      (this.dep = s),
      (this.version = s.version),
      (this.nextDep =
        this.prevDep =
        this.nextSub =
        this.prevSub =
        this.prevActiveLink =
          void 0);
  }
}
class Bs {
  constructor(t) {
    (this.computed = t),
      (this.version = 0),
      (this.activeLink = void 0),
      (this.subs = void 0),
      (this.map = void 0),
      (this.key = void 0),
      (this.sc = 0);
  }
  track(t) {
    if (!W || !me || W === this.computed) return;
    let s = this.activeLink;
    if (s === void 0 || s.sub !== W)
      (s = this.activeLink = new dr(W, this)),
        W.deps
          ? ((s.prevDep = W.depsTail),
            (W.depsTail.nextDep = s),
            (W.depsTail = s))
          : (W.deps = W.depsTail = s),
        Zn(s);
    else if (s.version === -1 && ((s.version = this.version), s.nextDep)) {
      const n = s.nextDep;
      (n.prevDep = s.prevDep),
        s.prevDep && (s.prevDep.nextDep = n),
        (s.prevDep = W.depsTail),
        (s.nextDep = void 0),
        (W.depsTail.nextDep = s),
        (W.depsTail = s),
        W.deps === s && (W.deps = n);
    }
    return s;
  }
  trigger(t) {
    this.version++, It++, this.notify(t);
  }
  notify(t) {
    ks();
    try {
      for (let s = this.subs; s; s = s.prevSub)
        s.sub.notify() && s.sub.dep.notify();
    } finally {
      Hs();
    }
  }
}
function Zn(e) {
  if ((e.dep.sc++, e.sub.flags & 4)) {
    const t = e.dep.computed;
    if (t && !e.dep.subs) {
      t.flags |= 20;
      for (let n = t.deps; n; n = n.nextDep) Zn(n);
    }
    const s = e.dep.subs;
    s !== e && ((e.prevSub = s), s && (s.nextSub = e)), (e.dep.subs = e);
  }
}
const xs = /* @__PURE__ */ new WeakMap(),
  Qe = Symbol(""),
  Ss = Symbol(""),
  At = Symbol("");
function te(e, t, s) {
  if (me && W) {
    let n = xs.get(e);
    n || xs.set(e, (n = /* @__PURE__ */ new Map()));
    let i = n.get(s);
    i || (n.set(s, (i = new Bs())), (i.map = n), (i.key = s)), i.track();
  }
}
function Oe(e, t, s, n, i, r) {
  const o = xs.get(e);
  if (!o) {
    It++;
    return;
  }
  const l = (a) => {
    a && a.trigger();
  };
  if ((ks(), t === "clear")) o.forEach(l);
  else {
    const a = R(e),
      d = a && Ns(s);
    if (a && s === "length") {
      const f = Number(n);
      o.forEach((h, x) => {
        (x === "length" || x === At || (!We(x) && x >= f)) && l(h);
      });
    } else
      switch (
        ((s !== void 0 || o.has(void 0)) && l(o.get(s)), d && l(o.get(At)), t)
      ) {
        case "add":
          a ? d && l(o.get("length")) : (l(o.get(Qe)), ot(e) && l(o.get(Ss)));
          break;
        case "delete":
          a || (l(o.get(Qe)), ot(e) && l(o.get(Ss)));
          break;
        case "set":
          ot(e) && l(o.get(Qe));
          break;
      }
  }
  Hs();
}
function nt(e) {
  const t = F(e);
  return t === e ? t : (te(t, "iterate", At), ge(e) ? t : t.map(se));
}
function ts(e) {
  return te((e = F(e)), "iterate", At), e;
}
const hr = {
  __proto__: null,
  [Symbol.iterator]() {
    return ds(this, Symbol.iterator, se);
  },
  concat(...e) {
    return nt(this).concat(...e.map((t) => (R(t) ? nt(t) : t)));
  },
  entries() {
    return ds(this, "entries", (e) => ((e[1] = se(e[1])), e));
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
    return hs(this, "includes", e);
  },
  indexOf(...e) {
    return hs(this, "indexOf", e);
  },
  join(e) {
    return nt(this).join(e);
  },
  // keys() iterator only reads `length`, no optimisation required
  lastIndexOf(...e) {
    return hs(this, "lastIndexOf", e);
  },
  map(e, t) {
    return Re(this, "map", e, t, void 0, arguments);
  },
  pop() {
    return gt(this, "pop");
  },
  push(...e) {
    return gt(this, "push", e);
  },
  reduce(e, ...t) {
    return on(this, "reduce", e, t);
  },
  reduceRight(e, ...t) {
    return on(this, "reduceRight", e, t);
  },
  shift() {
    return gt(this, "shift");
  },
  // slice could use ARRAY_ITERATE but also seems to beg for range tracking
  some(e, t) {
    return Re(this, "some", e, t, void 0, arguments);
  },
  splice(...e) {
    return gt(this, "splice", e);
  },
  toReversed() {
    return nt(this).toReversed();
  },
  toSorted(e) {
    return nt(this).toSorted(e);
  },
  toSpliced(...e) {
    return nt(this).toSpliced(...e);
  },
  unshift(...e) {
    return gt(this, "unshift", e);
  },
  values() {
    return ds(this, "values", se);
  },
};
function ds(e, t, s) {
  const n = ts(e),
    i = n[t]();
  return (
    n !== e &&
      !ge(e) &&
      ((i._next = i.next),
      (i.next = () => {
        const r = i._next();
        return r.value && (r.value = s(r.value)), r;
      })),
    i
  );
}
const pr = Array.prototype;
function Re(e, t, s, n, i, r) {
  const o = ts(e),
    l = o !== e && !ge(e),
    a = o[t];
  if (a !== pr[t]) {
    const h = a.apply(e, r);
    return l ? se(h) : h;
  }
  let d = s;
  o !== e &&
    (l
      ? (d = function (h, x) {
          return s.call(this, se(h), x, e);
        })
      : s.length > 2 &&
        (d = function (h, x) {
          return s.call(this, h, x, e);
        }));
  const f = a.call(o, d, n);
  return l && i ? i(f) : f;
}
function on(e, t, s, n) {
  const i = ts(e);
  let r = s;
  return (
    i !== e &&
      (ge(e)
        ? s.length > 3 &&
          (r = function (o, l, a) {
            return s.call(this, o, l, a, e);
          })
        : (r = function (o, l, a) {
            return s.call(this, o, se(l), a, e);
          })),
    i[t](r, ...n)
  );
}
function hs(e, t, s) {
  const n = F(e);
  te(n, "iterate", At);
  const i = n[t](...s);
  return (i === -1 || i === !1) && Ks(s[0])
    ? ((s[0] = F(s[0])), n[t](...s))
    : i;
}
function gt(e, t, s = []) {
  Ue(), ks();
  const n = F(e)[t].apply(e, s);
  return Hs(), Ve(), n;
}
const gr = /* @__PURE__ */ $s("__proto__,__v_isRef,__isVue"),
  Xn = new Set(
    /* @__PURE__ */ Object.getOwnPropertyNames(Symbol)
      .filter((e) => e !== "arguments" && e !== "caller")
      .map((e) => Symbol[e])
      .filter(We),
  );
function mr(e) {
  We(e) || (e = String(e));
  const t = F(this);
  return te(t, "has", e), Object.hasOwn(t, e);
}
class Qn {
  constructor(t = !1, s = !1) {
    (this._isReadonly = t), (this._isShallow = s);
  }
  get(t, s, n) {
    if (s === "__v_skip") return t.__v_skip;
    const i = this._isReadonly,
      r = this._isShallow;
    if (s === "__v_isReactive") return !i;
    if (s === "__v_isReadonly") return i;
    if (s === "__v_isShallow") return r;
    if (s === "__v_raw")
      return n === (i ? (r ? Cr : ni) : r ? si : ti).get(t) || // receiver is not the reactive proxy, but has the same prototype
        // this means the receiver is a user proxy of the reactive proxy
        Object.getPrototypeOf(t) === Object.getPrototypeOf(n)
        ? t
        : void 0;
    const o = R(t);
    if (!i) {
      let a;
      if (o && (a = hr[s])) return a;
      if (s === "hasOwnProperty") return mr;
    }
    const l = Reflect.get(
      t,
      s,
      // if this is a proxy wrapping a ref, return methods using the raw ref
      // as receiver so that we don't have to call `toRaw` on the ref in all
      // its class methods
      ne(t) ? t : n,
    );
    return (We(s) ? Xn.has(s) : gr(s)) || (i || te(t, "get", s), r)
      ? l
      : ne(l)
        ? o && Ns(s)
          ? l
          : l.value
        : q(l)
          ? i
            ? ii(l)
            : Us(l)
          : l;
  }
}
class ei extends Qn {
  constructor(t = !1) {
    super(!1, t);
  }
  set(t, s, n, i) {
    let r = t[s];
    if (!this._isShallow) {
      const a = et(r);
      if (
        (!ge(n) && !et(n) && ((r = F(r)), (n = F(n))), !R(t) && ne(r) && !ne(n))
      )
        return a ? !1 : ((r.value = n), !0);
    }
    const o = R(t) && Ns(s) ? Number(s) < t.length : L(t, s),
      l = Reflect.set(t, s, n, ne(t) ? t : i);
    return (
      t === F(i) && (o ? je(n, r) && Oe(t, "set", s, n) : Oe(t, "add", s, n)), l
    );
  }
  deleteProperty(t, s) {
    const n = L(t, s);
    t[s];
    const i = Reflect.deleteProperty(t, s);
    return i && n && Oe(t, "delete", s, void 0), i;
  }
  has(t, s) {
    const n = Reflect.has(t, s);
    return (!We(s) || !Xn.has(s)) && te(t, "has", s), n;
  }
  ownKeys(t) {
    return te(t, "iterate", R(t) ? "length" : Qe), Reflect.ownKeys(t);
  }
}
class _r extends Qn {
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
const br = /* @__PURE__ */ new ei(),
  yr = /* @__PURE__ */ new _r(),
  vr = /* @__PURE__ */ new ei(!0);
const Is = (e) => e,
  Nt = (e) => Reflect.getPrototypeOf(e);
function wr(e, t, s) {
  return function (...n) {
    const i = this.__v_raw,
      r = F(i),
      o = ot(r),
      l = e === "entries" || (e === Symbol.iterator && o),
      a = e === "keys" && o,
      d = i[e](...n),
      f = s ? Is : t ? As : se;
    return (
      !t && te(r, "iterate", a ? Ss : Qe),
      {
        // iterator protocol
        next() {
          const { value: h, done: x } = d.next();
          return x
            ? { value: h, done: x }
            : {
                value: l ? [f(h[0]), f(h[1])] : f(h),
                done: x,
              };
        },
        // iterable protocol
        [Symbol.iterator]() {
          return this;
        },
      }
    );
  };
}
function kt(e) {
  return function (...t) {
    return e === "delete" ? !1 : e === "clear" ? void 0 : this;
  };
}
function xr(e, t) {
  const s = {
    get(i) {
      const r = this.__v_raw,
        o = F(r),
        l = F(i);
      e || (je(i, l) && te(o, "get", i), te(o, "get", l));
      const { has: a } = Nt(o),
        d = t ? Is : e ? As : se;
      if (a.call(o, i)) return d(r.get(i));
      if (a.call(o, l)) return d(r.get(l));
      r !== o && r.get(i);
    },
    get size() {
      const i = this.__v_raw;
      return !e && te(F(i), "iterate", Qe), Reflect.get(i, "size", i);
    },
    has(i) {
      const r = this.__v_raw,
        o = F(r),
        l = F(i);
      return (
        e || (je(i, l) && te(o, "has", i), te(o, "has", l)),
        i === l ? r.has(i) : r.has(i) || r.has(l)
      );
    },
    forEach(i, r) {
      const l = this.__v_raw,
        a = F(l),
        d = t ? Is : e ? As : se;
      return (
        !e && te(a, "iterate", Qe),
        l.forEach((f, h) => i.call(r, d(f), d(h), this))
      );
    },
  };
  return (
    ie(
      s,
      e
        ? {
            add: kt("add"),
            set: kt("set"),
            delete: kt("delete"),
            clear: kt("clear"),
          }
        : {
            add(i) {
              !t && !ge(i) && !et(i) && (i = F(i));
              const r = F(this);
              return (
                Nt(r).has.call(r, i) || (r.add(i), Oe(r, "add", i, i)), this
              );
            },
            set(i, r) {
              !t && !ge(r) && !et(r) && (r = F(r));
              const o = F(this),
                { has: l, get: a } = Nt(o);
              let d = l.call(o, i);
              d || ((i = F(i)), (d = l.call(o, i)));
              const f = a.call(o, i);
              return (
                o.set(i, r),
                d ? je(r, f) && Oe(o, "set", i, r) : Oe(o, "add", i, r),
                this
              );
            },
            delete(i) {
              const r = F(this),
                { has: o, get: l } = Nt(r);
              let a = o.call(r, i);
              a || ((i = F(i)), (a = o.call(r, i))), l && l.call(r, i);
              const d = r.delete(i);
              return a && Oe(r, "delete", i, void 0), d;
            },
            clear() {
              const i = F(this),
                r = i.size !== 0,
                o = i.clear();
              return r && Oe(i, "clear", void 0, void 0), o;
            },
          },
    ),
    ["keys", "values", "entries", Symbol.iterator].forEach((i) => {
      s[i] = wr(i, e, t);
    }),
    s
  );
}
function Ws(e, t) {
  const s = xr(e, t);
  return (n, i, r) =>
    i === "__v_isReactive"
      ? !e
      : i === "__v_isReadonly"
        ? e
        : i === "__v_raw"
          ? n
          : Reflect.get(L(s, i) && i in n ? s : n, i, r);
}
const Sr = {
    get: /* @__PURE__ */ Ws(!1, !1),
  },
  Ir = {
    get: /* @__PURE__ */ Ws(!1, !0),
  },
  Ar = {
    get: /* @__PURE__ */ Ws(!0, !1),
  };
const ti = /* @__PURE__ */ new WeakMap(),
  si = /* @__PURE__ */ new WeakMap(),
  ni = /* @__PURE__ */ new WeakMap(),
  Cr = /* @__PURE__ */ new WeakMap();
function Er(e) {
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
function Tr(e) {
  return e.__v_skip || !Object.isExtensible(e) ? 0 : Er(Qi(e));
}
function Us(e) {
  return et(e) ? e : Vs(e, !1, br, Sr, ti);
}
function Pr(e) {
  return Vs(e, !1, vr, Ir, si);
}
function ii(e) {
  return Vs(e, !0, yr, Ar, ni);
}
function Vs(e, t, s, n, i) {
  if (!q(e) || (e.__v_raw && !(t && e.__v_isReactive))) return e;
  const r = i.get(e);
  if (r) return r;
  const o = Tr(e);
  if (o === 0) return e;
  const l = new Proxy(e, o === 2 ? n : s);
  return i.set(e, l), l;
}
function lt(e) {
  return et(e) ? lt(e.__v_raw) : !!(e && e.__v_isReactive);
}
function et(e) {
  return !!(e && e.__v_isReadonly);
}
function ge(e) {
  return !!(e && e.__v_isShallow);
}
function Ks(e) {
  return e ? !!e.__v_raw : !1;
}
function F(e) {
  const t = e && e.__v_raw;
  return t ? F(t) : e;
}
function Rr(e) {
  return (
    !L(e, "__v_skip") && Object.isExtensible(e) && jn(e, "__v_skip", !0), e
  );
}
const se = (e) => (q(e) ? Us(e) : e),
  As = (e) => (q(e) ? ii(e) : e);
function ne(e) {
  return e ? e.__v_isRef === !0 : !1;
}
function Cs(e) {
  return ri(e, !1);
}
function Mr(e) {
  return ri(e, !0);
}
function ri(e, t) {
  return ne(e) ? e : new Or(e, t);
}
class Or {
  constructor(t, s) {
    (this.dep = new Bs()),
      (this.__v_isRef = !0),
      (this.__v_isShallow = !1),
      (this._rawValue = s ? t : F(t)),
      (this._value = s ? t : se(t)),
      (this.__v_isShallow = s);
  }
  get value() {
    return this.dep.track(), this._value;
  }
  set value(t) {
    const s = this._rawValue,
      n = this.__v_isShallow || ge(t) || et(t);
    (t = n ? t : F(t)),
      je(t, s) &&
        ((this._rawValue = t),
        (this._value = n ? t : se(t)),
        this.dep.trigger());
  }
}
function Dr(e) {
  return ne(e) ? e.value : e;
}
const $r = {
  get: (e, t, s) => (t === "__v_raw" ? e : Dr(Reflect.get(e, t, s))),
  set: (e, t, s, n) => {
    const i = e[t];
    return ne(i) && !ne(s) ? ((i.value = s), !0) : Reflect.set(e, t, s, n);
  },
};
function oi(e) {
  return lt(e) ? e : new Proxy(e, $r);
}
class Fr {
  constructor(t, s, n) {
    (this.fn = t),
      (this.setter = s),
      (this._value = void 0),
      (this.dep = new Bs(this)),
      (this.__v_isRef = !0),
      (this.deps = void 0),
      (this.depsTail = void 0),
      (this.flags = 16),
      (this.globalVersion = It - 1),
      (this.next = void 0),
      (this.effect = this),
      (this.__v_isReadonly = !s),
      (this.isSSR = n);
  }
  /**
   * @internal
   */
  notify() {
    if (
      ((this.flags |= 16),
      !(this.flags & 8) && // avoid infinite self recursion
        W !== this)
    )
      return Gn(this, !0), !0;
  }
  get value() {
    const t = this.dep.track();
    return zn(this), t && (t.version = this.dep.version), this._value;
  }
  set value(t) {
    this.setter && this.setter(t);
  }
}
function Lr(e, t, s = !1) {
  let n, i;
  return M(e) ? (n = e) : ((n = e.get), (i = e.set)), new Fr(n, i, s);
}
const Ht = {},
  Vt = /* @__PURE__ */ new WeakMap();
let Ye;
function Nr(e, t = !1, s = Ye) {
  if (s) {
    let n = Vt.get(s);
    n || Vt.set(s, (n = [])), n.push(e);
  }
}
function kr(e, t, s = K) {
  const {
      immediate: n,
      deep: i,
      once: r,
      scheduler: o,
      augmentJob: l,
      call: a,
    } = s,
    d = (T) => (i ? T : ge(T) || i === !1 || i === 0 ? He(T, 1) : He(T));
  let f,
    h,
    x,
    w,
    C = !1,
    O = !1;
  if (
    (ne(e)
      ? ((h = () => e.value), (C = ge(e)))
      : lt(e)
        ? ((h = () => d(e)), (C = !0))
        : R(e)
          ? ((O = !0),
            (C = e.some((T) => lt(T) || ge(T))),
            (h = () =>
              e.map((T) => {
                if (ne(T)) return T.value;
                if (lt(T)) return d(T);
                if (M(T)) return a ? a(T, 2) : T();
              })))
          : M(e)
            ? t
              ? (h = a ? () => a(e, 2) : e)
              : (h = () => {
                  if (x) {
                    Ue();
                    try {
                      x();
                    } finally {
                      Ve();
                    }
                  }
                  const T = Ye;
                  Ye = f;
                  try {
                    return a ? a(e, 3, [w]) : e(w);
                  } finally {
                    Ye = T;
                  }
                })
            : (h = Ee),
    t && i)
  ) {
    const T = h,
      X = i === !0 ? 1 / 0 : i;
    h = () => He(T(), X);
  }
  const ee = ur(),
    H = () => {
      f.stop(), ee && ee.active && Ls(ee.effects, f);
    };
  if (r && t) {
    const T = t;
    t = (...X) => {
      T(...X), H();
    };
  }
  let J = O ? new Array(e.length).fill(Ht) : Ht;
  const z = (T) => {
    if (!(!(f.flags & 1) || (!f.dirty && !T)))
      if (t) {
        const X = f.run();
        if (i || C || (O ? X.some(($e, _e) => je($e, J[_e])) : je(X, J))) {
          x && x();
          const $e = Ye;
          Ye = f;
          try {
            const _e = [
              X,
              // pass undefined as the old value when it's changed for the first time
              J === Ht ? void 0 : O && J[0] === Ht ? [] : J,
              w,
            ];
            a
              ? a(t, 3, _e)
              : // @ts-expect-error
                t(..._e),
              (J = X);
          } finally {
            Ye = $e;
          }
        }
      } else f.run();
  };
  return (
    l && l(z),
    (f = new Vn(h)),
    (f.scheduler = o ? () => o(z, !1) : z),
    (w = (T) => Nr(T, !1, f)),
    (x = f.onStop =
      () => {
        const T = Vt.get(f);
        if (T) {
          if (a) a(T, 4);
          else for (const X of T) X();
          Vt.delete(f);
        }
      }),
    t ? (n ? z(!0) : (J = f.run())) : o ? o(z.bind(null, !0), !0) : f.run(),
    (H.pause = f.pause.bind(f)),
    (H.resume = f.resume.bind(f)),
    (H.stop = H),
    H
  );
}
function He(e, t = 1 / 0, s) {
  if (
    t <= 0 ||
    !q(e) ||
    e.__v_skip ||
    ((s = s || /* @__PURE__ */ new Set()), s.has(e))
  )
    return e;
  if ((s.add(e), t--, ne(e))) He(e.value, t, s);
  else if (R(e)) for (let n = 0; n < e.length; n++) He(e[n], t, s);
  else if (Fn(e) || ot(e))
    e.forEach((n) => {
      He(n, t, s);
    });
  else if (kn(e)) {
    for (const n in e) He(e[n], t, s);
    for (const n of Object.getOwnPropertySymbols(e))
      Object.prototype.propertyIsEnumerable.call(e, n) && He(e[n], t, s);
  }
  return e;
}
/**
 * @vue/runtime-core v3.5.13
 * (c) 2018-present Yuxi (Evan) You and Vue contributors
 * @license MIT
 **/
function Rt(e, t, s, n) {
  try {
    return n ? e(...n) : e();
  } catch (i) {
    ss(i, t, s);
  }
}
function Pe(e, t, s, n) {
  if (M(e)) {
    const i = Rt(e, t, s, n);
    return (
      i &&
        Ln(i) &&
        i.catch((r) => {
          ss(r, t, s);
        }),
      i
    );
  }
  if (R(e)) {
    const i = [];
    for (let r = 0; r < e.length; r++) i.push(Pe(e[r], t, s, n));
    return i;
  }
}
function ss(e, t, s, n = !0) {
  const i = t ? t.vnode : null,
    { errorHandler: r, throwUnhandledErrorInProduction: o } =
      (t && t.appContext.config) || K;
  if (t) {
    let l = t.parent;
    const a = t.proxy,
      d = `https://vuejs.org/error-reference/#runtime-${s}`;
    for (; l; ) {
      const f = l.ec;
      if (f) {
        for (let h = 0; h < f.length; h++) if (f[h](e, a, d) === !1) return;
      }
      l = l.parent;
    }
    if (r) {
      Ue(), Rt(r, null, 10, [e, a, d]), Ve();
      return;
    }
  }
  Hr(e, s, i, n, o);
}
function Hr(e, t, s, n = !0, i = !1) {
  if (i) throw e;
  console.error(e);
}
const le = [];
let Se = -1;
const ct = [];
let Le = null,
  it = 0;
const li = /* @__PURE__ */ Promise.resolve();
let Kt = null;
function ci(e) {
  const t = Kt || li;
  return e ? t.then(this ? e.bind(this) : e) : t;
}
function jr(e) {
  let t = Se + 1,
    s = le.length;
  for (; t < s; ) {
    const n = (t + s) >>> 1,
      i = le[n],
      r = Ct(i);
    r < e || (r === e && i.flags & 2) ? (t = n + 1) : (s = n);
  }
  return t;
}
function Gs(e) {
  if (!(e.flags & 1)) {
    const t = Ct(e),
      s = le[le.length - 1];
    !s || // fast path when the job id is larger than the tail
    (!(e.flags & 2) && t >= Ct(s))
      ? le.push(e)
      : le.splice(jr(t), 0, e),
      (e.flags |= 1),
      ai();
  }
}
function ai() {
  Kt || (Kt = li.then(fi));
}
function Br(e) {
  R(e)
    ? ct.push(...e)
    : Le && e.id === -1
      ? Le.splice(it + 1, 0, e)
      : e.flags & 1 || (ct.push(e), (e.flags |= 1)),
    ai();
}
function ln(e, t, s = Se + 1) {
  for (; s < le.length; s++) {
    const n = le[s];
    if (n && n.flags & 2) {
      if (e && n.id !== e.uid) continue;
      le.splice(s, 1),
        s--,
        n.flags & 4 && (n.flags &= -2),
        n(),
        n.flags & 4 || (n.flags &= -2);
    }
  }
}
function ui(e) {
  if (ct.length) {
    const t = [...new Set(ct)].sort((s, n) => Ct(s) - Ct(n));
    if (((ct.length = 0), Le)) {
      Le.push(...t);
      return;
    }
    for (Le = t, it = 0; it < Le.length; it++) {
      const s = Le[it];
      s.flags & 4 && (s.flags &= -2), s.flags & 8 || s(), (s.flags &= -2);
    }
    (Le = null), (it = 0);
  }
}
const Ct = (e) => (e.id == null ? (e.flags & 2 ? -1 : 1 / 0) : e.id);
function fi(e) {
  try {
    for (Se = 0; Se < le.length; Se++) {
      const t = le[Se];
      t &&
        !(t.flags & 8) &&
        (t.flags & 4 && (t.flags &= -2),
        Rt(t, t.i, t.i ? 15 : 14),
        t.flags & 4 || (t.flags &= -2));
    }
  } finally {
    for (; Se < le.length; Se++) {
      const t = le[Se];
      t && (t.flags &= -2);
    }
    (Se = -1),
      (le.length = 0),
      ui(),
      (Kt = null),
      (le.length || ct.length) && fi();
  }
}
let Ce = null,
  di = null;
function Gt(e) {
  const t = Ce;
  return (Ce = e), (di = (e && e.type.__scopeId) || null), t;
}
function Wr(e, t = Ce, s) {
  if (!t || e._n) return e;
  const n = (...i) => {
    n._d && mn(-1);
    const r = Gt(t);
    let o;
    try {
      o = e(...i);
    } finally {
      Gt(r), n._d && mn(1);
    }
    return o;
  };
  return (n._n = !0), (n._c = !0), (n._d = !0), n;
}
function Je(e, t, s, n) {
  const i = e.dirs,
    r = t && t.dirs;
  for (let o = 0; o < i.length; o++) {
    const l = i[o];
    r && (l.oldValue = r[o].value);
    const a = l.dir[n];
    a && (Ue(), Pe(a, s, 8, [e.el, l, e, t]), Ve());
  }
}
const Ur = Symbol("_vte"),
  Vr = (e) => e.__isTeleport;
function qs(e, t) {
  e.shapeFlag & 6 && e.component
    ? ((e.transition = t), qs(e.component.subTree, t))
    : e.shapeFlag & 128
      ? ((e.ssContent.transition = t.clone(e.ssContent)),
        (e.ssFallback.transition = t.clone(e.ssFallback)))
      : (e.transition = t);
}
/*! #__NO_SIDE_EFFECTS__ */
// @__NO_SIDE_EFFECTS__
function Js(e, t) {
  return M(e)
    ? // #8236: extend call and options.name access are considered side-effects
      // by Rollup, so we have to wrap it in a pure-annotated IIFE.
      ie({ name: e.name }, t, { setup: e })
    : e;
}
function hi(e) {
  e.ids = [e.ids[0] + e.ids[2]++ + "-", 0, 0];
}
function qt(e, t, s, n, i = !1) {
  if (R(e)) {
    e.forEach((C, O) => qt(C, t && (R(t) ? t[O] : t), s, n, i));
    return;
  }
  if (wt(n) && !i) {
    n.shapeFlag & 512 &&
      n.type.__asyncResolved &&
      n.component.subTree.component &&
      qt(e, t, s, n.component.subTree);
    return;
  }
  const r = n.shapeFlag & 4 ? Zs(n.component) : n.el,
    o = i ? null : r,
    { i: l, r: a } = e,
    d = t && t.r,
    f = l.refs === K ? (l.refs = {}) : l.refs,
    h = l.setupState,
    x = F(h),
    w = h === K ? () => !1 : (C) => L(x, C);
  if (
    (d != null &&
      d !== a &&
      (Z(d)
        ? ((f[d] = null), w(d) && (h[d] = null))
        : ne(d) && (d.value = null)),
    M(a))
  )
    Rt(a, l, 12, [o, f]);
  else {
    const C = Z(a),
      O = ne(a);
    if (C || O) {
      const ee = () => {
        if (e.f) {
          const H = C ? (w(a) ? h[a] : f[a]) : a.value;
          i
            ? R(H) && Ls(H, r)
            : R(H)
              ? H.includes(r) || H.push(r)
              : C
                ? ((f[a] = [r]), w(a) && (h[a] = f[a]))
                : ((a.value = [r]), e.k && (f[e.k] = a.value));
        } else
          C
            ? ((f[a] = o), w(a) && (h[a] = o))
            : O && ((a.value = o), e.k && (f[e.k] = o));
      };
      o ? ((ee.id = -1), de(ee, s)) : ee();
    }
  }
}
es().requestIdleCallback;
es().cancelIdleCallback;
const wt = (e) => !!e.type.__asyncLoader,
  pi = (e) => e.type.__isKeepAlive;
function Kr(e, t) {
  gi(e, "a", t);
}
function Gr(e, t) {
  gi(e, "da", t);
}
function gi(e, t, s = ce) {
  const n =
    e.__wdc ||
    (e.__wdc = () => {
      let i = s;
      for (; i; ) {
        if (i.isDeactivated) return;
        i = i.parent;
      }
      return e();
    });
  if ((ns(t, n, s), s)) {
    let i = s.parent;
    for (; i && i.parent; )
      pi(i.parent.vnode) && qr(n, t, s, i), (i = i.parent);
  }
}
function qr(e, t, s, n) {
  const i = ns(
    t,
    e,
    n,
    !0,
    /* prepend */
  );
  _i(() => {
    Ls(n[t], i);
  }, s);
}
function ns(e, t, s = ce, n = !1) {
  if (s) {
    const i = s[e] || (s[e] = []),
      r =
        t.__weh ||
        (t.__weh = (...o) => {
          Ue();
          const l = Mt(s),
            a = Pe(t, s, e, o);
          return l(), Ve(), a;
        });
    return n ? i.unshift(r) : i.push(r), r;
  }
}
const De =
    (e) =>
    (t, s = ce) => {
      (!Pt || e === "sp") && ns(e, (...n) => t(...n), s);
    },
  Jr = De("bm"),
  zr = De("m"),
  Yr = De("bu"),
  Zr = De("u"),
  mi = De("bum"),
  _i = De("um"),
  Xr = De("sp"),
  Qr = De("rtg"),
  eo = De("rtc");
function bi(e, t = ce) {
  ns("ec", e, t);
}
const to = Symbol.for("v-ndc");
function Ze(e, t, s, n) {
  let i;
  const r = s,
    o = R(e);
  if (o || Z(e)) {
    const l = o && lt(e);
    let a = !1;
    l && ((a = !ge(e)), (e = ts(e))), (i = new Array(e.length));
    for (let d = 0, f = e.length; d < f; d++)
      i[d] = t(a ? se(e[d]) : e[d], d, void 0, r);
  } else if (typeof e == "number") {
    i = new Array(e);
    for (let l = 0; l < e; l++) i[l] = t(l + 1, l, void 0, r);
  } else if (q(e))
    if (e[Symbol.iterator]) i = Array.from(e, (l, a) => t(l, a, void 0, r));
    else {
      const l = Object.keys(e);
      i = new Array(l.length);
      for (let a = 0, d = l.length; a < d; a++) {
        const f = l[a];
        i[a] = t(e[f], f, a, r);
      }
    }
  else i = [];
  return i;
}
const Es = (e) => (e ? (Bi(e) ? Zs(e) : Es(e.parent)) : null),
  xt =
    // Move PURE marker to new line to workaround compiler discarding it
    // due to type annotation
    /* @__PURE__ */ ie(/* @__PURE__ */ Object.create(null), {
      $: (e) => e,
      $el: (e) => e.vnode.el,
      $data: (e) => e.data,
      $props: (e) => e.props,
      $attrs: (e) => e.attrs,
      $slots: (e) => e.slots,
      $refs: (e) => e.refs,
      $parent: (e) => Es(e.parent),
      $root: (e) => Es(e.root),
      $host: (e) => e.ce,
      $emit: (e) => e.emit,
      $options: (e) => vi(e),
      $forceUpdate: (e) =>
        e.f ||
        (e.f = () => {
          Gs(e.update);
        }),
      $nextTick: (e) => e.n || (e.n = ci.bind(e.proxy)),
      $watch: (e) => Io.bind(e),
    }),
  ps = (e, t) => e !== K && !e.__isScriptSetup && L(e, t),
  so = {
    get({ _: e }, t) {
      if (t === "__v_skip") return !0;
      const {
        ctx: s,
        setupState: n,
        data: i,
        props: r,
        accessCache: o,
        type: l,
        appContext: a,
      } = e;
      let d;
      if (t[0] !== "$") {
        const w = o[t];
        if (w !== void 0)
          switch (w) {
            case 1:
              return n[t];
            case 2:
              return i[t];
            case 4:
              return s[t];
            case 3:
              return r[t];
          }
        else {
          if (ps(n, t)) return (o[t] = 1), n[t];
          if (i !== K && L(i, t)) return (o[t] = 2), i[t];
          if (
            // only cache other properties when instance has declared (thus stable)
            // props
            (d = e.propsOptions[0]) &&
            L(d, t)
          )
            return (o[t] = 3), r[t];
          if (s !== K && L(s, t)) return (o[t] = 4), s[t];
          Ts && (o[t] = 0);
        }
      }
      const f = xt[t];
      let h, x;
      if (f) return t === "$attrs" && te(e.attrs, "get", ""), f(e);
      if (
        // css module (injected by vue-loader)
        (h = l.__cssModules) &&
        (h = h[t])
      )
        return h;
      if (s !== K && L(s, t)) return (o[t] = 4), s[t];
      if (
        // global properties
        ((x = a.config.globalProperties), L(x, t))
      )
        return x[t];
    },
    set({ _: e }, t, s) {
      const { data: n, setupState: i, ctx: r } = e;
      return ps(i, t)
        ? ((i[t] = s), !0)
        : n !== K && L(n, t)
          ? ((n[t] = s), !0)
          : L(e.props, t) || (t[0] === "$" && t.slice(1) in e)
            ? !1
            : ((r[t] = s), !0);
    },
    has(
      {
        _: {
          data: e,
          setupState: t,
          accessCache: s,
          ctx: n,
          appContext: i,
          propsOptions: r,
        },
      },
      o,
    ) {
      let l;
      return (
        !!s[o] ||
        (e !== K && L(e, o)) ||
        ps(t, o) ||
        ((l = r[0]) && L(l, o)) ||
        L(n, o) ||
        L(xt, o) ||
        L(i.config.globalProperties, o)
      );
    },
    defineProperty(e, t, s) {
      return (
        s.get != null
          ? (e._.accessCache[t] = 0)
          : L(s, "value") && this.set(e, t, s.value, null),
        Reflect.defineProperty(e, t, s)
      );
    },
  };
function cn(e) {
  return R(e) ? e.reduce((t, s) => ((t[s] = null), t), {}) : e;
}
let Ts = !0;
function no(e) {
  const t = vi(e),
    s = e.proxy,
    n = e.ctx;
  (Ts = !1), t.beforeCreate && an(t.beforeCreate, e, "bc");
  const {
    // state
    data: i,
    computed: r,
    methods: o,
    watch: l,
    provide: a,
    inject: d,
    // lifecycle
    created: f,
    beforeMount: h,
    mounted: x,
    beforeUpdate: w,
    updated: C,
    activated: O,
    deactivated: ee,
    beforeDestroy: H,
    beforeUnmount: J,
    destroyed: z,
    unmounted: T,
    render: X,
    renderTracked: $e,
    renderTriggered: _e,
    errorCaptured: Fe,
    serverPrefetch: Ot,
    // public API
    expose: Ke,
    inheritAttrs: ft,
    // assets
    components: Dt,
    directives: $t,
    filters: os,
  } = t;
  if ((d && io(d, n, null), o))
    for (const G in o) {
      const j = o[G];
      M(j) && (n[G] = j.bind(s));
    }
  if (i) {
    const G = i.call(s, s);
    q(G) && (e.data = Us(G));
  }
  if (((Ts = !0), r))
    for (const G in r) {
      const j = r[G],
        Ge = M(j) ? j.bind(s, s) : M(j.get) ? j.get.bind(s, s) : Ee,
        Ft = !M(j) && M(j.set) ? j.set.bind(s) : Ee,
        qe = Os({
          get: Ge,
          set: Ft,
        });
      Object.defineProperty(n, G, {
        enumerable: !0,
        configurable: !0,
        get: () => qe.value,
        set: (be) => (qe.value = be),
      });
    }
  if (l) for (const G in l) yi(l[G], n, s, G);
  if (a) {
    const G = M(a) ? a.call(s) : a;
    Reflect.ownKeys(G).forEach((j) => {
      uo(j, G[j]);
    });
  }
  f && an(f, e, "c");
  function re(G, j) {
    R(j) ? j.forEach((Ge) => G(Ge.bind(s))) : j && G(j.bind(s));
  }
  if (
    (re(Jr, h),
    re(zr, x),
    re(Yr, w),
    re(Zr, C),
    re(Kr, O),
    re(Gr, ee),
    re(bi, Fe),
    re(eo, $e),
    re(Qr, _e),
    re(mi, J),
    re(_i, T),
    re(Xr, Ot),
    R(Ke))
  )
    if (Ke.length) {
      const G = e.exposed || (e.exposed = {});
      Ke.forEach((j) => {
        Object.defineProperty(G, j, {
          get: () => s[j],
          set: (Ge) => (s[j] = Ge),
        });
      });
    } else e.exposed || (e.exposed = {});
  X && e.render === Ee && (e.render = X),
    ft != null && (e.inheritAttrs = ft),
    Dt && (e.components = Dt),
    $t && (e.directives = $t),
    Ot && hi(e);
}
function io(e, t, s = Ee) {
  R(e) && (e = Ps(e));
  for (const n in e) {
    const i = e[n];
    let r;
    q(i)
      ? "default" in i
        ? (r = jt(i.from || n, i.default, !0))
        : (r = jt(i.from || n))
      : (r = jt(i)),
      ne(r)
        ? Object.defineProperty(t, n, {
            enumerable: !0,
            configurable: !0,
            get: () => r.value,
            set: (o) => (r.value = o),
          })
        : (t[n] = r);
  }
}
function an(e, t, s) {
  Pe(R(e) ? e.map((n) => n.bind(t.proxy)) : e.bind(t.proxy), t, s);
}
function yi(e, t, s, n) {
  const i = n.includes(".") ? $i(s, n) : () => s[n];
  if (Z(e)) {
    const r = t[e];
    M(r) && Bt(i, r);
  } else if (M(e)) Bt(i, e.bind(s));
  else if (q(e))
    if (R(e)) e.forEach((r) => yi(r, t, s, n));
    else {
      const r = M(e.handler) ? e.handler.bind(s) : t[e.handler];
      M(r) && Bt(i, r, e);
    }
}
function vi(e) {
  const t = e.type,
    { mixins: s, extends: n } = t,
    {
      mixins: i,
      optionsCache: r,
      config: { optionMergeStrategies: o },
    } = e.appContext,
    l = r.get(t);
  let a;
  return (
    l
      ? (a = l)
      : !i.length && !s && !n
        ? (a = t)
        : ((a = {}),
          i.length && i.forEach((d) => Jt(a, d, o, !0)),
          Jt(a, t, o)),
    q(t) && r.set(t, a),
    a
  );
}
function Jt(e, t, s, n = !1) {
  const { mixins: i, extends: r } = t;
  r && Jt(e, r, s, !0), i && i.forEach((o) => Jt(e, o, s, !0));
  for (const o in t)
    if (!(n && o === "expose")) {
      const l = ro[o] || (s && s[o]);
      e[o] = l ? l(e[o], t[o]) : t[o];
    }
  return e;
}
const ro = {
  data: un,
  props: fn,
  emits: fn,
  // objects
  methods: _t,
  computed: _t,
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
  components: _t,
  directives: _t,
  // watch
  watch: lo,
  // provide / inject
  provide: un,
  inject: oo,
};
function un(e, t) {
  return t
    ? e
      ? function () {
          return ie(
            M(e) ? e.call(this, this) : e,
            M(t) ? t.call(this, this) : t,
          );
        }
      : t
    : e;
}
function oo(e, t) {
  return _t(Ps(e), Ps(t));
}
function Ps(e) {
  if (R(e)) {
    const t = {};
    for (let s = 0; s < e.length; s++) t[e[s]] = e[s];
    return t;
  }
  return e;
}
function oe(e, t) {
  return e ? [...new Set([].concat(e, t))] : t;
}
function _t(e, t) {
  return e ? ie(/* @__PURE__ */ Object.create(null), e, t) : t;
}
function fn(e, t) {
  return e
    ? R(e) && R(t)
      ? [.../* @__PURE__ */ new Set([...e, ...t])]
      : ie(/* @__PURE__ */ Object.create(null), cn(e), cn(t ?? {}))
    : t;
}
function lo(e, t) {
  if (!e) return t;
  if (!t) return e;
  const s = ie(/* @__PURE__ */ Object.create(null), e);
  for (const n in t) s[n] = oe(e[n], t[n]);
  return s;
}
function wi() {
  return {
    app: null,
    config: {
      isNativeTag: Zi,
      performance: !1,
      globalProperties: {},
      optionMergeStrategies: {},
      errorHandler: void 0,
      warnHandler: void 0,
      compilerOptions: {},
    },
    mixins: [],
    components: {},
    directives: {},
    provides: /* @__PURE__ */ Object.create(null),
    optionsCache: /* @__PURE__ */ new WeakMap(),
    propsCache: /* @__PURE__ */ new WeakMap(),
    emitsCache: /* @__PURE__ */ new WeakMap(),
  };
}
let co = 0;
function ao(e, t) {
  return (n, i = null) => {
    M(n) || (n = ie({}, n)), i != null && !q(i) && (i = null);
    const r = wi(),
      o = /* @__PURE__ */ new WeakSet(),
      l = [];
    let a = !1;
    const d = (r.app = {
      _uid: co++,
      _component: n,
      _props: i,
      _container: null,
      _context: r,
      _instance: null,
      version: Vo,
      get config() {
        return r.config;
      },
      set config(f) {},
      use(f, ...h) {
        return (
          o.has(f) ||
            (f && M(f.install)
              ? (o.add(f), f.install(d, ...h))
              : M(f) && (o.add(f), f(d, ...h))),
          d
        );
      },
      mixin(f) {
        return r.mixins.includes(f) || r.mixins.push(f), d;
      },
      component(f, h) {
        return h ? ((r.components[f] = h), d) : r.components[f];
      },
      directive(f, h) {
        return h ? ((r.directives[f] = h), d) : r.directives[f];
      },
      mount(f, h, x) {
        if (!a) {
          const w = d._ceVNode || Te(n, i);
          return (
            (w.appContext = r),
            x === !0 ? (x = "svg") : x === !1 && (x = void 0),
            e(w, f, x),
            (a = !0),
            (d._container = f),
            (f.__vue_app__ = d),
            Zs(w.component)
          );
        }
      },
      onUnmount(f) {
        l.push(f);
      },
      unmount() {
        a &&
          (Pe(l, d._instance, 16),
          e(null, d._container),
          delete d._container.__vue_app__);
      },
      provide(f, h) {
        return (r.provides[f] = h), d;
      },
      runWithContext(f) {
        const h = at;
        at = d;
        try {
          return f();
        } finally {
          at = h;
        }
      },
    });
    return d;
  };
}
let at = null;
function uo(e, t) {
  if (ce) {
    let s = ce.provides;
    const n = ce.parent && ce.parent.provides;
    n === s && (s = ce.provides = Object.create(n)), (s[e] = t);
  }
}
function jt(e, t, s = !1) {
  const n = ce || Ce;
  if (n || at) {
    const i = at
      ? at._context.provides
      : n
        ? n.parent == null
          ? n.vnode.appContext && n.vnode.appContext.provides
          : n.parent.provides
        : void 0;
    if (i && e in i) return i[e];
    if (arguments.length > 1) return s && M(t) ? t.call(n && n.proxy) : t;
  }
}
const xi = {},
  Si = () => Object.create(xi),
  Ii = (e) => Object.getPrototypeOf(e) === xi;
function fo(e, t, s, n = !1) {
  const i = {},
    r = Si();
  (e.propsDefaults = /* @__PURE__ */ Object.create(null)), Ai(e, t, i, r);
  for (const o in e.propsOptions[0]) o in i || (i[o] = void 0);
  s ? (e.props = n ? i : Pr(i)) : e.type.props ? (e.props = i) : (e.props = r),
    (e.attrs = r);
}
function ho(e, t, s, n) {
  const {
      props: i,
      attrs: r,
      vnode: { patchFlag: o },
    } = e,
    l = F(i),
    [a] = e.propsOptions;
  let d = !1;
  if (
    // always force full diff in dev
    // - #1942 if hmr is enabled with sfc component
    // - vite#872 non-sfc component used by sfc component
    (n || o > 0) &&
    !(o & 16)
  ) {
    if (o & 8) {
      const f = e.vnode.dynamicProps;
      for (let h = 0; h < f.length; h++) {
        const x = f[h];
        if (is(e.emitsOptions, x)) continue;
        const w = t[x];
        if (a)
          if (L(r, x)) w !== r[x] && ((r[x] = w), (d = !0));
          else {
            const C = Be(x);
            i[C] = Rs(a, l, C, w, e, !1);
          }
        else w !== r[x] && ((r[x] = w), (d = !0));
      }
    }
  } else {
    Ai(e, t, i, r) && (d = !0);
    let f;
    for (const h in l)
      (!t || // for camelCase
        (!L(t, h) && // it's possible the original props was passed in as kebab-case
          // and converted to camelCase (#955)
          ((f = st(h)) === h || !L(t, f)))) &&
        (a
          ? s && // for camelCase
            (s[h] !== void 0 || // for kebab-case
              s[f] !== void 0) &&
            (i[h] = Rs(a, l, h, void 0, e, !0))
          : delete i[h]);
    if (r !== l) for (const h in r) (!t || !L(t, h)) && (delete r[h], (d = !0));
  }
  d && Oe(e.attrs, "set", "");
}
function Ai(e, t, s, n) {
  const [i, r] = e.propsOptions;
  let o = !1,
    l;
  if (t)
    for (const a in t) {
      if (bt(a)) continue;
      const d = t[a];
      let f;
      i && L(i, (f = Be(a)))
        ? !r || !r.includes(f)
          ? (s[f] = d)
          : ((l || (l = {}))[f] = d)
        : is(e.emitsOptions, a) ||
          ((!(a in n) || d !== n[a]) && ((n[a] = d), (o = !0)));
    }
  if (r) {
    const a = F(s),
      d = l || K;
    for (let f = 0; f < r.length; f++) {
      const h = r[f];
      s[h] = Rs(i, a, h, d[h], e, !L(d, h));
    }
  }
  return o;
}
function Rs(e, t, s, n, i, r) {
  const o = e[s];
  if (o != null) {
    const l = L(o, "default");
    if (l && n === void 0) {
      const a = o.default;
      if (o.type !== Function && !o.skipFactory && M(a)) {
        const { propsDefaults: d } = i;
        if (s in d) n = d[s];
        else {
          const f = Mt(i);
          (n = d[s] = a.call(null, t)), f();
        }
      } else n = a;
      i.ce && i.ce._setProp(s, n);
    }
    o[0] &&
    /* shouldCast */
      (r && !l
        ? (n = !1)
        : o[1] &&
          /* shouldCastTrue */
          (n === "" || n === st(s)) &&
          (n = !0));
  }
  return n;
}
const po = /* @__PURE__ */ new WeakMap();
function Ci(e, t, s = !1) {
  const n = s ? po : t.propsCache,
    i = n.get(e);
  if (i) return i;
  const r = e.props,
    o = {},
    l = [];
  let a = !1;
  if (!M(e)) {
    const f = (h) => {
      a = !0;
      const [x, w] = Ci(h, t, !0);
      ie(o, x), w && l.push(...w);
    };
    !s && t.mixins.length && t.mixins.forEach(f),
      e.extends && f(e.extends),
      e.mixins && e.mixins.forEach(f);
  }
  if (!r && !a) return q(e) && n.set(e, rt), rt;
  if (R(r))
    for (let f = 0; f < r.length; f++) {
      const h = Be(r[f]);
      dn(h) && (o[h] = K);
    }
  else if (r)
    for (const f in r) {
      const h = Be(f);
      if (dn(h)) {
        const x = r[f],
          w = (o[h] = R(x) || M(x) ? { type: x } : ie({}, x)),
          C = w.type;
        let O = !1,
          ee = !0;
        if (R(C))
          for (let H = 0; H < C.length; ++H) {
            const J = C[H],
              z = M(J) && J.name;
            if (z === "Boolean") {
              O = !0;
              break;
            } else z === "String" && (ee = !1);
          }
        else O = M(C) && C.name === "Boolean";
        (w[0] =
        /* shouldCast */
          O),
          (w[1] =
          /* shouldCastTrue */
            ee),
          (O || L(w, "default")) && l.push(h);
      }
    }
  const d = [o, l];
  return q(e) && n.set(e, d), d;
}
function dn(e) {
  return e[0] !== "$" && !bt(e);
}
const Ei = (e) => e[0] === "_" || e === "$stable",
  zs = (e) => (R(e) ? e.map(Ae) : [Ae(e)]),
  go = (e, t, s) => {
    if (t._n) return t;
    const n = Wr((...i) => zs(t(...i)), s);
    return (n._c = !1), n;
  },
  Ti = (e, t, s) => {
    const n = e._ctx;
    for (const i in e) {
      if (Ei(i)) continue;
      const r = e[i];
      if (M(r)) t[i] = go(i, r, n);
      else if (r != null) {
        const o = zs(r);
        t[i] = () => o;
      }
    }
  },
  Pi = (e, t) => {
    const s = zs(t);
    e.slots.default = () => s;
  },
  Ri = (e, t, s) => {
    for (const n in t) (s || n !== "_") && (e[n] = t[n]);
  },
  mo = (e, t, s) => {
    const n = (e.slots = Si());
    if (e.vnode.shapeFlag & 32) {
      const i = t._;
      i ? (Ri(n, t, s), s && jn(n, "_", i, !0)) : Ti(t, n);
    } else t && Pi(e, t);
  },
  _o = (e, t, s) => {
    const { vnode: n, slots: i } = e;
    let r = !0,
      o = K;
    if (n.shapeFlag & 32) {
      const l = t._;
      l
        ? s && l === 1
          ? (r = !1)
          : Ri(i, t, s)
        : ((r = !t.$stable), Ti(t, i)),
        (o = t);
    } else t && (Pi(e, t), (o = { default: 1 }));
    if (r) for (const l in i) !Ei(l) && o[l] == null && delete i[l];
  },
  de = Mo;
function bo(e) {
  return yo(e);
}
function yo(e, t) {
  const s = es();
  s.__VUE__ = !0;
  const {
      insert: n,
      remove: i,
      patchProp: r,
      createElement: o,
      createText: l,
      createComment: a,
      setText: d,
      setElementText: f,
      parentNode: h,
      nextSibling: x,
      setScopeId: w = Ee,
      insertStaticContent: C,
    } = e,
    O = (
      c,
      u,
      p,
      _ = null,
      g = null,
      m = null,
      S = void 0,
      v = null,
      y = !!u.dynamicChildren,
    ) => {
      if (c === u) return;
      c && !mt(c, u) && ((_ = Lt(c)), be(c, g, m, !0), (c = null)),
        u.patchFlag === -2 && ((y = !1), (u.dynamicChildren = null));
      const { type: b, ref: E, shapeFlag: I } = u;
      switch (b) {
        case rs:
          ee(c, u, p, _);
          break;
        case tt:
          H(c, u, p, _);
          break;
        case ms:
          c == null && J(u, p, _, S);
          break;
        case Q:
          Dt(c, u, p, _, g, m, S, v, y);
          break;
        default:
          I & 1
            ? X(c, u, p, _, g, m, S, v, y)
            : I & 6
              ? $t(c, u, p, _, g, m, S, v, y)
              : (I & 64 || I & 128) && b.process(c, u, p, _, g, m, S, v, y, ht);
      }
      E != null && g && qt(E, c && c.ref, m, u || c, !u);
    },
    ee = (c, u, p, _) => {
      if (c == null) n((u.el = l(u.children)), p, _);
      else {
        const g = (u.el = c.el);
        u.children !== c.children && d(g, u.children);
      }
    },
    H = (c, u, p, _) => {
      c == null ? n((u.el = a(u.children || "")), p, _) : (u.el = c.el);
    },
    J = (c, u, p, _) => {
      [c.el, c.anchor] = C(c.children, u, p, _, c.el, c.anchor);
    },
    z = ({ el: c, anchor: u }, p, _) => {
      let g;
      for (; c && c !== u; ) (g = x(c)), n(c, p, _), (c = g);
      n(u, p, _);
    },
    T = ({ el: c, anchor: u }) => {
      let p;
      for (; c && c !== u; ) (p = x(c)), i(c), (c = p);
      i(u);
    },
    X = (c, u, p, _, g, m, S, v, y) => {
      u.type === "svg" ? (S = "svg") : u.type === "math" && (S = "mathml"),
        c == null ? $e(u, p, _, g, m, S, v, y) : Ot(c, u, g, m, S, v, y);
    },
    $e = (c, u, p, _, g, m, S, v) => {
      let y, b;
      const { props: E, shapeFlag: I, transition: A, dirs: P } = c;
      if (
        ((y = c.el = o(c.type, m, E && E.is, E)),
        I & 8
          ? f(y, c.children)
          : I & 16 && Fe(c.children, y, null, _, g, gs(c, m), S, v),
        P && Je(c, null, _, "created"),
        _e(y, c, c.scopeId, S, _),
        E)
      ) {
        for (const B in E) B !== "value" && !bt(B) && r(y, B, null, E[B], m, _);
        "value" in E && r(y, "value", null, E.value, m),
          (b = E.onVnodeBeforeMount) && xe(b, _, c);
      }
      P && Je(c, null, _, "beforeMount");
      const $ = vo(g, A);
      $ && A.beforeEnter(y),
        n(y, u, p),
        ((b = E && E.onVnodeMounted) || $ || P) &&
          de(() => {
            b && xe(b, _, c), $ && A.enter(y), P && Je(c, null, _, "mounted");
          }, g);
    },
    _e = (c, u, p, _, g) => {
      if ((p && w(c, p), _)) for (let m = 0; m < _.length; m++) w(c, _[m]);
      if (g) {
        const m = g.subTree;
        if (
          u === m ||
          (Li(m.type) && (m.ssContent === u || m.ssFallback === u))
        ) {
          const S = g.vnode;
          _e(c, S, S.scopeId, S.slotScopeIds, g.parent);
        }
      }
    },
    Fe = (c, u, p, _, g, m, S, v, y = 0) => {
      for (let b = y; b < c.length; b++) {
        const E = (c[b] = v ? Ne(c[b]) : Ae(c[b]));
        O(null, E, u, p, _, g, m, S, v);
      }
    },
    Ot = (c, u, p, _, g, m, S) => {
      const v = (u.el = c.el);
      let { patchFlag: y, dynamicChildren: b, dirs: E } = u;
      y |= c.patchFlag & 16;
      const I = c.props || K,
        A = u.props || K;
      let P;
      if (
        (p && ze(p, !1),
        (P = A.onVnodeBeforeUpdate) && xe(P, p, u, c),
        E && Je(u, c, p, "beforeUpdate"),
        p && ze(p, !0),
        ((I.innerHTML && A.innerHTML == null) ||
          (I.textContent && A.textContent == null)) &&
          f(v, ""),
        b
          ? Ke(c.dynamicChildren, b, v, p, _, gs(u, g), m)
          : S || j(c, u, v, null, p, _, gs(u, g), m, !1),
        y > 0)
      ) {
        if (y & 16) ft(v, I, A, p, g);
        else if (
          (y & 2 && I.class !== A.class && r(v, "class", null, A.class, g),
          y & 4 && r(v, "style", I.style, A.style, g),
          y & 8)
        ) {
          const $ = u.dynamicProps;
          for (let B = 0; B < $.length; B++) {
            const N = $[B],
              ue = I[N],
              ae = A[N];
            (ae !== ue || N === "value") && r(v, N, ue, ae, g, p);
          }
        }
        y & 1 && c.children !== u.children && f(v, u.children);
      } else !S && b == null && ft(v, I, A, p, g);
      ((P = A.onVnodeUpdated) || E) &&
        de(() => {
          P && xe(P, p, u, c), E && Je(u, c, p, "updated");
        }, _);
    },
    Ke = (c, u, p, _, g, m, S) => {
      for (let v = 0; v < u.length; v++) {
        const y = c[v],
          b = u[v],
          E =
            // oldVNode may be an errored async setup() component inside Suspense
            // which will not have a mounted element
            y.el && // - In the case of a Fragment, we need to provide the actual parent
            // of the Fragment itself so it can move its children.
            (y.type === Q || // - In the case of different nodes, there is going to be a replacement
              // which also requires the correct parent container
              !mt(y, b) || // - In the case of a component, it could contain anything.
              y.shapeFlag & 70)
              ? h(y.el)
              : // In other cases, the parent container is not actually used so we
                // just pass the block element here to avoid a DOM parentNode call.
                p;
        O(y, b, E, null, _, g, m, S, !0);
      }
    },
    ft = (c, u, p, _, g) => {
      if (u !== p) {
        if (u !== K)
          for (const m in u) !bt(m) && !(m in p) && r(c, m, u[m], null, g, _);
        for (const m in p) {
          if (bt(m)) continue;
          const S = p[m],
            v = u[m];
          S !== v && m !== "value" && r(c, m, v, S, g, _);
        }
        "value" in p && r(c, "value", u.value, p.value, g);
      }
    },
    Dt = (c, u, p, _, g, m, S, v, y) => {
      const b = (u.el = c ? c.el : l("")),
        E = (u.anchor = c ? c.anchor : l(""));
      const { patchFlag: I, dynamicChildren: A, slotScopeIds: P } = u;
      P && (v = v ? v.concat(P) : P),
        c == null
          ? (n(b, p, _),
            n(E, p, _),
            Fe(
              // #10007
              // such fragment like `<></>` will be compiled into
              // a fragment which doesn't have a children.
              // In this case fallback to an empty array
              u.children || [],
              p,
              E,
              g,
              m,
              S,
              v,
              y,
            ))
          : I > 0 &&
              I & 64 &&
              A && // #2715 the previous fragment could've been a BAILed one as a result
              // of renderSlot() with no valid children
              c.dynamicChildren
            ? (Ke(
                c.dynamicChildren,
                A,
                p,
                g,
                m,
                S,
                v,
              ), // #2080 if the stable fragment has a key, it's a <template v-for> that may
              //  get moved around. Make sure all root level vnodes inherit el.
              // #2134 or if it's a component root, it may also get moved around
              // as the component is being moved.
              (u.key != null || (g && u === g.subTree)) &&
                Mi(
                  c,
                  u,
                  !0,
                  /* shallow */
                ))
            : j(c, u, p, E, g, m, S, v, y);
    },
    $t = (c, u, p, _, g, m, S, v, y) => {
      (u.slotScopeIds = v),
        c == null
          ? u.shapeFlag & 512
            ? g.ctx.activate(u, p, _, S, y)
            : os(u, p, _, g, m, S, y)
          : Xs(c, u, y);
    },
    os = (c, u, p, _, g, m, S) => {
      const v = (c.component = ko(c, _, g));
      if ((pi(c) && (v.ctx.renderer = ht), Ho(v, !1, S), v.asyncDep)) {
        if ((g && g.registerDep(v, re, S), !c.el)) {
          const y = (v.subTree = Te(tt));
          H(null, y, u, p);
        }
      } else re(v, c, u, p, g, m, S);
    },
    Xs = (c, u, p) => {
      const _ = (u.component = c.component);
      if (Po(c, u, p))
        if (_.asyncDep && !_.asyncResolved) {
          G(_, u, p);
          return;
        } else (_.next = u), _.update();
      else (u.el = c.el), (_.vnode = u);
    },
    re = (c, u, p, _, g, m, S) => {
      const v = () => {
        if (c.isMounted) {
          let { next: I, bu: A, u: P, parent: $, vnode: B } = c;
          {
            const ve = Oi(c);
            if (ve) {
              I && ((I.el = B.el), G(c, I, S)),
                ve.asyncDep.then(() => {
                  c.isUnmounted || v();
                });
              return;
            }
          }
          let N = I,
            ue;
          ze(c, !1),
            I ? ((I.el = B.el), G(c, I, S)) : (I = B),
            A && as(A),
            (ue = I.props && I.props.onVnodeBeforeUpdate) && xe(ue, $, I, B),
            ze(c, !0);
          const ae = pn(c),
            ye = c.subTree;
          (c.subTree = ae),
            O(
              ye,
              ae,
              // parent may have changed if it's in a teleport
              h(ye.el),
              // anchor may have changed if it's in a fragment
              Lt(ye),
              c,
              g,
              m,
            ),
            (I.el = ae.el),
            N === null && Ro(c, ae.el),
            P && de(P, g),
            (ue = I.props && I.props.onVnodeUpdated) &&
              de(() => xe(ue, $, I, B), g);
        } else {
          let I;
          const { el: A, props: P } = u,
            { bm: $, m: B, parent: N, root: ue, type: ae } = c,
            ye = wt(u);
          ze(c, !1),
            $ && as($),
            !ye && (I = P && P.onVnodeBeforeMount) && xe(I, N, u),
            ze(c, !0);
          {
            ue.ce && ue.ce._injectChildStyle(ae);
            const ve = (c.subTree = pn(c));
            O(null, ve, p, _, c, g, m), (u.el = ve.el);
          }
          if ((B && de(B, g), !ye && (I = P && P.onVnodeMounted))) {
            const ve = u;
            de(() => xe(I, N, ve), g);
          }
          (u.shapeFlag & 256 ||
            (N && wt(N.vnode) && N.vnode.shapeFlag & 256)) &&
            c.a &&
            de(c.a, g),
            (c.isMounted = !0),
            (u = p = _ = null);
        }
      };
      c.scope.on();
      const y = (c.effect = new Vn(v));
      c.scope.off();
      const b = (c.update = y.run.bind(y)),
        E = (c.job = y.runIfDirty.bind(y));
      (E.i = c), (E.id = c.uid), (y.scheduler = () => Gs(E)), ze(c, !0), b();
    },
    G = (c, u, p) => {
      u.component = c;
      const _ = c.vnode.props;
      (c.vnode = u),
        (c.next = null),
        ho(c, u.props, _, p),
        _o(c, u.children, p),
        Ue(),
        ln(c),
        Ve();
    },
    j = (c, u, p, _, g, m, S, v, y = !1) => {
      const b = c && c.children,
        E = c ? c.shapeFlag : 0,
        I = u.children,
        { patchFlag: A, shapeFlag: P } = u;
      if (A > 0) {
        if (A & 128) {
          Ft(b, I, p, _, g, m, S, v, y);
          return;
        } else if (A & 256) {
          Ge(b, I, p, _, g, m, S, v, y);
          return;
        }
      }
      P & 8
        ? (E & 16 && dt(b, g, m), I !== b && f(p, I))
        : E & 16
          ? P & 16
            ? Ft(b, I, p, _, g, m, S, v, y)
            : dt(b, g, m, !0)
          : (E & 8 && f(p, ""), P & 16 && Fe(I, p, _, g, m, S, v, y));
    },
    Ge = (c, u, p, _, g, m, S, v, y) => {
      (c = c || rt), (u = u || rt);
      const b = c.length,
        E = u.length,
        I = Math.min(b, E);
      let A;
      for (A = 0; A < I; A++) {
        const P = (u[A] = y ? Ne(u[A]) : Ae(u[A]));
        O(c[A], P, p, null, g, m, S, v, y);
      }
      b > E ? dt(c, g, m, !0, !1, I) : Fe(u, p, _, g, m, S, v, y, I);
    },
    Ft = (c, u, p, _, g, m, S, v, y) => {
      let b = 0;
      const E = u.length;
      let I = c.length - 1,
        A = E - 1;
      for (; b <= I && b <= A; ) {
        const P = c[b],
          $ = (u[b] = y ? Ne(u[b]) : Ae(u[b]));
        if (mt(P, $)) O(P, $, p, null, g, m, S, v, y);
        else break;
        b++;
      }
      for (; b <= I && b <= A; ) {
        const P = c[I],
          $ = (u[A] = y ? Ne(u[A]) : Ae(u[A]));
        if (mt(P, $)) O(P, $, p, null, g, m, S, v, y);
        else break;
        I--, A--;
      }
      if (b > I) {
        if (b <= A) {
          const P = A + 1,
            $ = P < E ? u[P].el : _;
          for (; b <= A; )
            O(null, (u[b] = y ? Ne(u[b]) : Ae(u[b])), p, $, g, m, S, v, y), b++;
        }
      } else if (b > A) for (; b <= I; ) be(c[b], g, m, !0), b++;
      else {
        const P = b,
          $ = b,
          B = /* @__PURE__ */ new Map();
        for (b = $; b <= A; b++) {
          const fe = (u[b] = y ? Ne(u[b]) : Ae(u[b]));
          fe.key != null && B.set(fe.key, b);
        }
        let N,
          ue = 0;
        const ae = A - $ + 1;
        let ye = !1,
          ve = 0;
        const pt = new Array(ae);
        for (b = 0; b < ae; b++) pt[b] = 0;
        for (b = P; b <= I; b++) {
          const fe = c[b];
          if (ue >= ae) {
            be(fe, g, m, !0);
            continue;
          }
          let we;
          if (fe.key != null) we = B.get(fe.key);
          else
            for (N = $; N <= A; N++)
              if (pt[N - $] === 0 && mt(fe, u[N])) {
                we = N;
                break;
              }
          we === void 0
            ? be(fe, g, m, !0)
            : ((pt[we - $] = b + 1),
              we >= ve ? (ve = we) : (ye = !0),
              O(fe, u[we], p, null, g, m, S, v, y),
              ue++);
        }
        const tn = ye ? wo(pt) : rt;
        for (N = tn.length - 1, b = ae - 1; b >= 0; b--) {
          const fe = $ + b,
            we = u[fe],
            sn = fe + 1 < E ? u[fe + 1].el : _;
          pt[b] === 0
            ? O(null, we, p, sn, g, m, S, v, y)
            : ye && (N < 0 || b !== tn[N] ? qe(we, p, sn, 2) : N--);
        }
      }
    },
    qe = (c, u, p, _, g = null) => {
      const { el: m, type: S, transition: v, children: y, shapeFlag: b } = c;
      if (b & 6) {
        qe(c.component.subTree, u, p, _);
        return;
      }
      if (b & 128) {
        c.suspense.move(u, p, _);
        return;
      }
      if (b & 64) {
        S.move(c, u, p, ht);
        return;
      }
      if (S === Q) {
        n(m, u, p);
        for (let I = 0; I < y.length; I++) qe(y[I], u, p, _);
        n(c.anchor, u, p);
        return;
      }
      if (S === ms) {
        z(c, u, p);
        return;
      }
      if (_ !== 2 && b & 1 && v)
        if (_ === 0) v.beforeEnter(m), n(m, u, p), de(() => v.enter(m), g);
        else {
          const { leave: I, delayLeave: A, afterLeave: P } = v,
            $ = () => n(m, u, p),
            B = () => {
              I(m, () => {
                $(), P && P();
              });
            };
          A ? A(m, $, B) : B();
        }
      else n(m, u, p);
    },
    be = (c, u, p, _ = !1, g = !1) => {
      const {
        type: m,
        props: S,
        ref: v,
        children: y,
        dynamicChildren: b,
        shapeFlag: E,
        patchFlag: I,
        dirs: A,
        cacheIndex: P,
      } = c;
      if (
        (I === -2 && (g = !1),
        v != null && qt(v, null, p, c, !0),
        P != null && (u.renderCache[P] = void 0),
        E & 256)
      ) {
        u.ctx.deactivate(c);
        return;
      }
      const $ = E & 1 && A,
        B = !wt(c);
      let N;
      if ((B && (N = S && S.onVnodeBeforeUnmount) && xe(N, u, c), E & 6))
        Ji(c.component, p, _);
      else {
        if (E & 128) {
          c.suspense.unmount(p, _);
          return;
        }
        $ && Je(c, null, u, "beforeUnmount"),
          E & 64
            ? c.type.remove(c, u, p, ht, _)
            : b && // #5154
                // when v-once is used inside a block, setBlockTracking(-1) marks the
                // parent block with hasOnce: true
                // so that it doesn't take the fast path during unmount - otherwise
                // components nested in v-once are never unmounted.
                !b.hasOnce && // #1153: fast path should not be taken for non-stable (v-for) fragments
                (m !== Q || (I > 0 && I & 64))
              ? dt(b, u, p, !1, !0)
              : ((m === Q && I & 384) || (!g && E & 16)) && dt(y, u, p),
          _ && Qs(c);
      }
      ((B && (N = S && S.onVnodeUnmounted)) || $) &&
        de(() => {
          N && xe(N, u, c), $ && Je(c, null, u, "unmounted");
        }, p);
    },
    Qs = (c) => {
      const { type: u, el: p, anchor: _, transition: g } = c;
      if (u === Q) {
        qi(p, _);
        return;
      }
      if (u === ms) {
        T(c);
        return;
      }
      const m = () => {
        i(p), g && !g.persisted && g.afterLeave && g.afterLeave();
      };
      if (c.shapeFlag & 1 && g && !g.persisted) {
        const { leave: S, delayLeave: v } = g,
          y = () => S(p, m);
        v ? v(c.el, m, y) : y();
      } else m();
    },
    qi = (c, u) => {
      let p;
      for (; c !== u; ) (p = x(c)), i(c), (c = p);
      i(u);
    },
    Ji = (c, u, p) => {
      const { bum: _, scope: g, job: m, subTree: S, um: v, m: y, a: b } = c;
      hn(y),
        hn(b),
        _ && as(_),
        g.stop(),
        m && ((m.flags |= 8), be(S, c, u, p)),
        v && de(v, u),
        de(() => {
          c.isUnmounted = !0;
        }, u),
        u &&
          u.pendingBranch &&
          !u.isUnmounted &&
          c.asyncDep &&
          !c.asyncResolved &&
          c.suspenseId === u.pendingId &&
          (u.deps--, u.deps === 0 && u.resolve());
    },
    dt = (c, u, p, _ = !1, g = !1, m = 0) => {
      for (let S = m; S < c.length; S++) be(c[S], u, p, _, g);
    },
    Lt = (c) => {
      if (c.shapeFlag & 6) return Lt(c.component.subTree);
      if (c.shapeFlag & 128) return c.suspense.next();
      const u = x(c.anchor || c.el),
        p = u && u[Ur];
      return p ? x(p) : u;
    };
  let ls = !1;
  const en = (c, u, p) => {
      c == null
        ? u._vnode && be(u._vnode, null, null, !0)
        : O(u._vnode || null, c, u, null, null, null, p),
        (u._vnode = c),
        ls || ((ls = !0), ln(), ui(), (ls = !1));
    },
    ht = {
      p: O,
      um: be,
      m: qe,
      r: Qs,
      mt: os,
      mc: Fe,
      pc: j,
      pbc: Ke,
      n: Lt,
      o: e,
    };
  return {
    render: en,
    hydrate: void 0,
    createApp: ao(en),
  };
}
function gs({ type: e, props: t }, s) {
  return (s === "svg" && e === "foreignObject") ||
    (s === "mathml" &&
      e === "annotation-xml" &&
      t &&
      t.encoding &&
      t.encoding.includes("html"))
    ? void 0
    : s;
}
function ze({ effect: e, job: t }, s) {
  s ? ((e.flags |= 32), (t.flags |= 4)) : ((e.flags &= -33), (t.flags &= -5));
}
function vo(e, t) {
  return (!e || (e && !e.pendingBranch)) && t && !t.persisted;
}
function Mi(e, t, s = !1) {
  const n = e.children,
    i = t.children;
  if (R(n) && R(i))
    for (let r = 0; r < n.length; r++) {
      const o = n[r];
      let l = i[r];
      l.shapeFlag & 1 &&
        !l.dynamicChildren &&
        ((l.patchFlag <= 0 || l.patchFlag === 32) &&
          ((l = i[r] = Ne(i[r])), (l.el = o.el)),
        !s && l.patchFlag !== -2 && Mi(o, l)),
        l.type === rs && (l.el = o.el);
    }
}
function wo(e) {
  const t = e.slice(),
    s = [0];
  let n, i, r, o, l;
  const a = e.length;
  for (n = 0; n < a; n++) {
    const d = e[n];
    if (d !== 0) {
      if (((i = s[s.length - 1]), e[i] < d)) {
        (t[n] = i), s.push(n);
        continue;
      }
      for (r = 0, o = s.length - 1; r < o; )
        (l = (r + o) >> 1), e[s[l]] < d ? (r = l + 1) : (o = l);
      d < e[s[r]] && (r > 0 && (t[n] = s[r - 1]), (s[r] = n));
    }
  }
  for (r = s.length, o = s[r - 1]; r-- > 0; ) (s[r] = o), (o = t[o]);
  return s;
}
function Oi(e) {
  const t = e.subTree.component;
  if (t) return t.asyncDep && !t.asyncResolved ? t : Oi(t);
}
function hn(e) {
  if (e) for (let t = 0; t < e.length; t++) e[t].flags |= 8;
}
const xo = Symbol.for("v-scx"),
  So = () => jt(xo);
function Bt(e, t, s) {
  return Di(e, t, s);
}
function Di(e, t, s = K) {
  const { immediate: n, deep: i, flush: r, once: o } = s,
    l = ie({}, s),
    a = (t && n) || (!t && r !== "post");
  let d;
  if (Pt) {
    if (r === "sync") {
      const w = So();
      d = w.__watcherHandles || (w.__watcherHandles = []);
    } else if (!a) {
      const w = () => {};
      return (w.stop = Ee), (w.resume = Ee), (w.pause = Ee), w;
    }
  }
  const f = ce;
  l.call = (w, C, O) => Pe(w, f, C, O);
  let h = !1;
  r === "post"
    ? (l.scheduler = (w) => {
        de(w, f && f.suspense);
      })
    : r !== "sync" &&
      ((h = !0),
      (l.scheduler = (w, C) => {
        C ? w() : Gs(w);
      })),
    (l.augmentJob = (w) => {
      t && (w.flags |= 4),
        h && ((w.flags |= 2), f && ((w.id = f.uid), (w.i = f)));
    });
  const x = kr(e, t, l);
  return Pt && (d ? d.push(x) : a && x()), x;
}
function Io(e, t, s) {
  const n = this.proxy,
    i = Z(e) ? (e.includes(".") ? $i(n, e) : () => n[e]) : e.bind(n, n);
  let r;
  M(t) ? (r = t) : ((r = t.handler), (s = t));
  const o = Mt(this),
    l = Di(i, r.bind(n), s);
  return o(), l;
}
function $i(e, t) {
  const s = t.split(".");
  return () => {
    let n = e;
    for (let i = 0; i < s.length && n; i++) n = n[s[i]];
    return n;
  };
}
const Ao = (e, t) =>
  t === "modelValue" || t === "model-value"
    ? e.modelModifiers
    : e[`${t}Modifiers`] || e[`${Be(t)}Modifiers`] || e[`${st(t)}Modifiers`];
function Co(e, t, ...s) {
  if (e.isUnmounted) return;
  const n = e.vnode.props || K;
  let i = s;
  const r = t.startsWith("update:"),
    o = r && Ao(n, t.slice(7));
  o &&
    (o.trim && (i = s.map((f) => (Z(f) ? f.trim() : f))),
    o.number && (i = s.map(sr)));
  let l,
    a =
      n[(l = cs(t))] || // also try camelCase event handler (#2249)
      n[(l = cs(Be(t)))];
  !a && r && (a = n[(l = cs(st(t)))]), a && Pe(a, e, 6, i);
  const d = n[l + "Once"];
  if (d) {
    if (!e.emitted) e.emitted = {};
    else if (e.emitted[l]) return;
    (e.emitted[l] = !0), Pe(d, e, 6, i);
  }
}
function Fi(e, t, s = !1) {
  const n = t.emitsCache,
    i = n.get(e);
  if (i !== void 0) return i;
  const r = e.emits;
  let o = {},
    l = !1;
  if (!M(e)) {
    const a = (d) => {
      const f = Fi(d, t, !0);
      f && ((l = !0), ie(o, f));
    };
    !s && t.mixins.length && t.mixins.forEach(a),
      e.extends && a(e.extends),
      e.mixins && e.mixins.forEach(a);
  }
  return !r && !l
    ? (q(e) && n.set(e, null), null)
    : (R(r) ? r.forEach((a) => (o[a] = null)) : ie(o, r),
      q(e) && n.set(e, o),
      o);
}
function is(e, t) {
  return !e || !Zt(t)
    ? !1
    : ((t = t.slice(2).replace(/Once$/, "")),
      L(e, t[0].toLowerCase() + t.slice(1)) || L(e, st(t)) || L(e, t));
}
function pn(e) {
  const {
      type: t,
      vnode: s,
      proxy: n,
      withProxy: i,
      propsOptions: [r],
      slots: o,
      attrs: l,
      emit: a,
      render: d,
      renderCache: f,
      props: h,
      data: x,
      setupState: w,
      ctx: C,
      inheritAttrs: O,
    } = e,
    ee = Gt(e);
  let H, J;
  try {
    if (s.shapeFlag & 4) {
      const T = i || n,
        X = T;
      (H = Ae(d.call(X, T, f, h, w, x, C))), (J = l);
    } else {
      const T = t;
      (H = Ae(
        T.length > 1 ? T(h, { attrs: l, slots: o, emit: a }) : T(h, null),
      )),
        (J = t.props ? l : Eo(l));
    }
  } catch (T) {
    (St.length = 0), ss(T, e, 1), (H = Te(tt));
  }
  let z = H;
  if (J && O !== !1) {
    const T = Object.keys(J),
      { shapeFlag: X } = z;
    T.length &&
      X & 7 &&
      (r && T.some(Fs) && (J = To(J, r)), (z = ut(z, J, !1, !0)));
  }
  return (
    s.dirs &&
      ((z = ut(z, null, !1, !0)),
      (z.dirs = z.dirs ? z.dirs.concat(s.dirs) : s.dirs)),
    s.transition && qs(z, s.transition),
    (H = z),
    Gt(ee),
    H
  );
}
const Eo = (e) => {
    let t;
    for (const s in e)
      (s === "class" || s === "style" || Zt(s)) && ((t || (t = {}))[s] = e[s]);
    return t;
  },
  To = (e, t) => {
    const s = {};
    for (const n in e) (!Fs(n) || !(n.slice(9) in t)) && (s[n] = e[n]);
    return s;
  };
function Po(e, t, s) {
  const { props: n, children: i, component: r } = e,
    { props: o, children: l, patchFlag: a } = t,
    d = r.emitsOptions;
  if (t.dirs || t.transition) return !0;
  if (s && a >= 0) {
    if (a & 1024) return !0;
    if (a & 16) return n ? gn(n, o, d) : !!o;
    if (a & 8) {
      const f = t.dynamicProps;
      for (let h = 0; h < f.length; h++) {
        const x = f[h];
        if (o[x] !== n[x] && !is(d, x)) return !0;
      }
    }
  } else
    return (i || l) && (!l || !l.$stable)
      ? !0
      : n === o
        ? !1
        : n
          ? o
            ? gn(n, o, d)
            : !0
          : !!o;
  return !1;
}
function gn(e, t, s) {
  const n = Object.keys(t);
  if (n.length !== Object.keys(e).length) return !0;
  for (let i = 0; i < n.length; i++) {
    const r = n[i];
    if (t[r] !== e[r] && !is(s, r)) return !0;
  }
  return !1;
}
function Ro({ vnode: e, parent: t }, s) {
  for (; t; ) {
    const n = t.subTree;
    if ((n.suspense && n.suspense.activeBranch === e && (n.el = e.el), n === e))
      ((e = t.vnode).el = s), (t = t.parent);
    else break;
  }
}
const Li = (e) => e.__isSuspense;
function Mo(e, t) {
  t && t.pendingBranch
    ? R(e)
      ? t.effects.push(...e)
      : t.effects.push(e)
    : Br(e);
}
const Q = Symbol.for("v-fgt"),
  rs = Symbol.for("v-txt"),
  tt = Symbol.for("v-cmt"),
  ms = Symbol.for("v-stc"),
  St = [];
let pe = null;
function k(e = !1) {
  St.push((pe = e ? null : []));
}
function Oo() {
  St.pop(), (pe = St[St.length - 1] || null);
}
let Et = 1;
function mn(e, t = !1) {
  (Et += e), e < 0 && pe && t && (pe.hasOnce = !0);
}
function Ni(e) {
  return (
    (e.dynamicChildren = Et > 0 ? pe || rt : null),
    Oo(),
    Et > 0 && pe && pe.push(e),
    e
  );
}
function V(e, t, s, n, i, r) {
  return Ni(D(e, t, s, n, i, r, !0));
}
function ki(e, t, s, n, i) {
  return Ni(Te(e, t, s, n, i, !0));
}
function Hi(e) {
  return e ? e.__v_isVNode === !0 : !1;
}
function mt(e, t) {
  return e.type === t.type && e.key === t.key;
}
const ji = ({ key: e }) => e ?? null,
  Wt = ({ ref: e, ref_key: t, ref_for: s }) => (
    typeof e == "number" && (e = "" + e),
    e != null
      ? Z(e) || ne(e) || M(e)
        ? { i: Ce, r: e, k: t, f: !!s }
        : e
      : null
  );
function D(
  e,
  t = null,
  s = null,
  n = 0,
  i = null,
  r = e === Q ? 0 : 1,
  o = !1,
  l = !1,
) {
  const a = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e,
    props: t,
    key: t && ji(t),
    ref: t && Wt(t),
    scopeId: di,
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
    shapeFlag: r,
    patchFlag: n,
    dynamicProps: i,
    dynamicChildren: null,
    appContext: null,
    ctx: Ce,
  };
  return (
    l
      ? (Ys(a, s), r & 128 && e.normalize(a))
      : s && (a.shapeFlag |= Z(s) ? 8 : 16),
    Et > 0 && // avoid a block node from tracking itself
      !o && // has current parent block
      pe && // presence of a patch flag indicates this node needs patching on updates.
      // component nodes also should always be patched, because even if the
      // component doesn't need to update, it needs to persist the instance on to
      // the next vnode so that it can be properly unmounted later.
      (a.patchFlag > 0 || r & 6) && // the EVENTS flag is only for hydration and if it is the only flag, the
      // vnode should not be considered dynamic due to handler caching.
      a.patchFlag !== 32 &&
      pe.push(a),
    a
  );
}
const Te = Do;
function Do(e, t = null, s = null, n = 0, i = null, r = !1) {
  if (((!e || e === to) && (e = tt), Hi(e))) {
    const l = ut(
      e,
      t,
      !0,
      /* mergeRef: true */
    );
    return (
      s && Ys(l, s),
      Et > 0 &&
        !r &&
        pe &&
        (l.shapeFlag & 6 ? (pe[pe.indexOf(e)] = l) : pe.push(l)),
      (l.patchFlag = -2),
      l
    );
  }
  if ((Uo(e) && (e = e.__vccOpts), t)) {
    t = $o(t);
    let { class: l, style: a } = t;
    l && !Z(l) && (t.class = Xe(l)),
      q(a) && (Ks(a) && !R(a) && (a = ie({}, a)), (t.style = ke(a)));
  }
  const o = Z(e) ? 1 : Li(e) ? 128 : Vr(e) ? 64 : q(e) ? 4 : M(e) ? 2 : 0;
  return D(e, t, s, n, i, o, r, !0);
}
function $o(e) {
  return e ? (Ks(e) || Ii(e) ? ie({}, e) : e) : null;
}
function ut(e, t, s = !1, n = !1) {
  const { props: i, ref: r, patchFlag: o, children: l, transition: a } = e,
    d = t ? Fo(i || {}, t) : i,
    f = {
      __v_isVNode: !0,
      __v_skip: !0,
      type: e.type,
      props: d,
      key: d && ji(d),
      ref:
        t && t.ref
          ? // #2078 in the case of <component :is="vnode" ref="extra"/>
            // if the vnode itself already has a ref, cloneVNode will need to merge
            // the refs so the single vnode can be set on multiple refs
            s && r
            ? R(r)
              ? r.concat(Wt(t))
              : [r, Wt(t)]
            : Wt(t)
          : r,
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
      patchFlag: t && e.type !== Q ? (o === -1 ? 16 : o | 16) : o,
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
      ssContent: e.ssContent && ut(e.ssContent),
      ssFallback: e.ssFallback && ut(e.ssFallback),
      el: e.el,
      anchor: e.anchor,
      ctx: e.ctx,
      ce: e.ce,
    };
  return a && n && qs(f, a.clone(f)), f;
}
function Tt(e = " ", t = 0) {
  return Te(rs, null, e, t);
}
function Ie(e = "", t = !1) {
  return t ? (k(), ki(tt, null, e)) : Te(tt, null, e);
}
function Ae(e) {
  return e == null || typeof e == "boolean"
    ? Te(tt)
    : R(e)
      ? Te(
          Q,
          null,
          // #3666, avoid reference pollution when reusing vnode
          e.slice(),
        )
      : Hi(e)
        ? Ne(e)
        : Te(rs, null, String(e));
}
function Ne(e) {
  return (e.el === null && e.patchFlag !== -1) || e.memo ? e : ut(e);
}
function Ys(e, t) {
  let s = 0;
  const { shapeFlag: n } = e;
  if (t == null) t = null;
  else if (R(t)) s = 16;
  else if (typeof t == "object")
    if (n & 65) {
      const i = t.default;
      i && (i._c && (i._d = !1), Ys(e, i()), i._c && (i._d = !0));
      return;
    } else {
      s = 32;
      const i = t._;
      !i && !Ii(t)
        ? (t._ctx = Ce)
        : i === 3 &&
          Ce &&
          (Ce.slots._ === 1 ? (t._ = 1) : ((t._ = 2), (e.patchFlag |= 1024)));
    }
  else
    M(t)
      ? ((t = { default: t, _ctx: Ce }), (s = 32))
      : ((t = String(t)), n & 64 ? ((s = 16), (t = [Tt(t)])) : (s = 8));
  (e.children = t), (e.shapeFlag |= s);
}
function Fo(...e) {
  const t = {};
  for (let s = 0; s < e.length; s++) {
    const n = e[s];
    for (const i in n)
      if (i === "class")
        t.class !== n.class && (t.class = Xe([t.class, n.class]));
      else if (i === "style") t.style = ke([t.style, n.style]);
      else if (Zt(i)) {
        const r = t[i],
          o = n[i];
        o &&
          r !== o &&
          !(R(r) && r.includes(o)) &&
          (t[i] = r ? [].concat(r, o) : o);
      } else i !== "" && (t[i] = n[i]);
  }
  return t;
}
function xe(e, t, s, n = null) {
  Pe(e, t, 7, [s, n]);
}
const Lo = wi();
let No = 0;
function ko(e, t, s) {
  const n = e.type,
    i = (t ? t.appContext : e.appContext) || Lo,
    r = {
      uid: No++,
      vnode: e,
      type: n,
      parent: t,
      appContext: i,
      root: null,
      // to be immediately set
      next: null,
      subTree: null,
      // will be set synchronously right after creation
      effect: null,
      update: null,
      // will be set synchronously right after creation
      job: null,
      scope: new ar(
        !0,
        /* detached */
      ),
      render: null,
      proxy: null,
      exposed: null,
      exposeProxy: null,
      withProxy: null,
      provides: t ? t.provides : Object.create(i.provides),
      ids: t ? t.ids : ["", 0, 0],
      accessCache: null,
      renderCache: [],
      // local resolved assets
      components: null,
      directives: null,
      // resolved props and emits options
      propsOptions: Ci(n, i),
      emitsOptions: Fi(n, i),
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
      sp: null,
    };
  return (
    (r.ctx = { _: r }),
    (r.root = t ? t.root : r),
    (r.emit = Co.bind(null, r)),
    e.ce && e.ce(r),
    r
  );
}
let ce = null,
  zt,
  Ms;
{
  const e = es(),
    t = (s, n) => {
      let i;
      return (
        (i = e[s]) || (i = e[s] = []),
        i.push(n),
        (r) => {
          i.length > 1 ? i.forEach((o) => o(r)) : i[0](r);
        }
      );
    };
  (zt = t("__VUE_INSTANCE_SETTERS__", (s) => (ce = s))),
    (Ms = t("__VUE_SSR_SETTERS__", (s) => (Pt = s)));
}
const Mt = (e) => {
    const t = ce;
    return (
      zt(e),
      e.scope.on(),
      () => {
        e.scope.off(), zt(t);
      }
    );
  },
  _n = () => {
    ce && ce.scope.off(), zt(null);
  };
function Bi(e) {
  return e.vnode.shapeFlag & 4;
}
let Pt = !1;
function Ho(e, t = !1, s = !1) {
  t && Ms(t);
  const { props: n, children: i } = e.vnode,
    r = Bi(e);
  fo(e, n, r, t), mo(e, i, s);
  const o = r ? jo(e, t) : void 0;
  return t && Ms(!1), o;
}
function jo(e, t) {
  const s = e.type;
  (e.accessCache = /* @__PURE__ */ Object.create(null)),
    (e.proxy = new Proxy(e.ctx, so));
  const { setup: n } = s;
  if (n) {
    Ue();
    const i = (e.setupContext = n.length > 1 ? Wo(e) : null),
      r = Mt(e),
      o = Rt(n, e, 0, [e.props, i]),
      l = Ln(o);
    if ((Ve(), r(), (l || e.sp) && !wt(e) && hi(e), l)) {
      if ((o.then(_n, _n), t))
        return o
          .then((a) => {
            bn(e, a);
          })
          .catch((a) => {
            ss(a, e, 0);
          });
      e.asyncDep = o;
    } else bn(e, o);
  } else Wi(e);
}
function bn(e, t, s) {
  M(t)
    ? e.type.__ssrInlineRender
      ? (e.ssrRender = t)
      : (e.render = t)
    : q(t) && (e.setupState = oi(t)),
    Wi(e);
}
function Wi(e, t, s) {
  const n = e.type;
  e.render || (e.render = n.render || Ee);
  {
    const i = Mt(e);
    Ue();
    try {
      no(e);
    } finally {
      Ve(), i();
    }
  }
}
const Bo = {
  get(e, t) {
    return te(e, "get", ""), e[t];
  },
};
function Wo(e) {
  const t = (s) => {
    e.exposed = s || {};
  };
  return {
    attrs: new Proxy(e.attrs, Bo),
    slots: e.slots,
    emit: e.emit,
    expose: t,
  };
}
function Zs(e) {
  return e.exposed
    ? e.exposeProxy ||
        (e.exposeProxy = new Proxy(oi(Rr(e.exposed)), {
          get(t, s) {
            if (s in t) return t[s];
            if (s in xt) return xt[s](e);
          },
          has(t, s) {
            return s in t || s in xt;
          },
        }))
    : e.proxy;
}
function Uo(e) {
  return M(e) && "__vccOpts" in e;
}
const Os = (e, t) => Lr(e, t, Pt),
  Vo = "3.5.13";
/**
 * @vue/runtime-dom v3.5.13
 * (c) 2018-present Yuxi (Evan) You and Vue contributors
 * @license MIT
 **/
let Ds;
const yn = typeof window < "u" && window.trustedTypes;
if (yn)
  try {
    Ds = /* @__PURE__ */ yn.createPolicy("vue", {
      createHTML: (e) => e,
    });
  } catch {}
const Ui = Ds ? (e) => Ds.createHTML(e) : (e) => e,
  Ko = "http://www.w3.org/2000/svg",
  Go = "http://www.w3.org/1998/Math/MathML",
  Me = typeof document < "u" ? document : null,
  vn = Me && /* @__PURE__ */ Me.createElement("template"),
  qo = {
    insert: (e, t, s) => {
      t.insertBefore(e, s || null);
    },
    remove: (e) => {
      const t = e.parentNode;
      t && t.removeChild(e);
    },
    createElement: (e, t, s, n) => {
      const i =
        t === "svg"
          ? Me.createElementNS(Ko, e)
          : t === "mathml"
            ? Me.createElementNS(Go, e)
            : s
              ? Me.createElement(e, { is: s })
              : Me.createElement(e);
      return (
        e === "select" &&
          n &&
          n.multiple != null &&
          i.setAttribute("multiple", n.multiple),
        i
      );
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
    insertStaticContent(e, t, s, n, i, r) {
      const o = s ? s.previousSibling : t.lastChild;
      if (i && (i === r || i.nextSibling))
        for (
          ;
          t.insertBefore(i.cloneNode(!0), s),
            !(i === r || !(i = i.nextSibling));
        );
      else {
        vn.innerHTML = Ui(
          n === "svg"
            ? `<svg>${e}</svg>`
            : n === "mathml"
              ? `<math>${e}</math>`
              : e,
        );
        const l = vn.content;
        if (n === "svg" || n === "mathml") {
          const a = l.firstChild;
          for (; a.firstChild; ) l.appendChild(a.firstChild);
          l.removeChild(a);
        }
        t.insertBefore(l, s);
      }
      return [
        // first
        o ? o.nextSibling : t.firstChild,
        // last
        s ? s.previousSibling : t.lastChild,
      ];
    },
  },
  Jo = Symbol("_vtc");
function zo(e, t, s) {
  const n = e[Jo];
  n && (t = (t ? [t, ...n] : [...n]).join(" ")),
    t == null
      ? e.removeAttribute("class")
      : s
        ? e.setAttribute("class", t)
        : (e.className = t);
}
const wn = Symbol("_vod"),
  Yo = Symbol("_vsh"),
  Zo = Symbol(""),
  Xo = /(^|;)\s*display\s*:/;
function Qo(e, t, s) {
  const n = e.style,
    i = Z(s);
  let r = !1;
  if (s && !i) {
    if (t)
      if (Z(t))
        for (const o of t.split(";")) {
          const l = o.slice(0, o.indexOf(":")).trim();
          s[l] == null && Ut(n, l, "");
        }
      else for (const o in t) s[o] == null && Ut(n, o, "");
    for (const o in s) o === "display" && (r = !0), Ut(n, o, s[o]);
  } else if (i) {
    if (t !== s) {
      const o = n[Zo];
      o && (s += ";" + o), (n.cssText = s), (r = Xo.test(s));
    }
  } else t && e.removeAttribute("style");
  wn in e && ((e[wn] = r ? n.display : ""), e[Yo] && (n.display = "none"));
}
const xn = /\s*!important$/;
function Ut(e, t, s) {
  if (R(s)) s.forEach((n) => Ut(e, t, n));
  else if ((s == null && (s = ""), t.startsWith("--"))) e.setProperty(t, s);
  else {
    const n = el(e, t);
    xn.test(s)
      ? e.setProperty(st(n), s.replace(xn, ""), "important")
      : (e[n] = s);
  }
}
const Sn = ["Webkit", "Moz", "ms"],
  _s = {};
function el(e, t) {
  const s = _s[t];
  if (s) return s;
  let n = Be(t);
  if (n !== "filter" && n in e) return (_s[t] = n);
  n = Hn(n);
  for (let i = 0; i < Sn.length; i++) {
    const r = Sn[i] + n;
    if (r in e) return (_s[t] = r);
  }
  return t;
}
const In = "http://www.w3.org/1999/xlink";
function An(e, t, s, n, i, r = cr(t)) {
  n && t.startsWith("xlink:")
    ? s == null
      ? e.removeAttributeNS(In, t.slice(6, t.length))
      : e.setAttributeNS(In, t, s)
    : s == null || (r && !Bn(s))
      ? e.removeAttribute(t)
      : e.setAttribute(t, r ? "" : We(s) ? String(s) : s);
}
function Cn(e, t, s, n, i) {
  if (t === "innerHTML" || t === "textContent") {
    s != null && (e[t] = t === "innerHTML" ? Ui(s) : s);
    return;
  }
  const r = e.tagName;
  if (
    t === "value" &&
    r !== "PROGRESS" && // custom elements may use _value internally
    !r.includes("-")
  ) {
    const l = r === "OPTION" ? e.getAttribute("value") || "" : e.value,
      a =
        s == null
          ? // #11647: value should be set as empty string for null and undefined,
            // but <input type="checkbox"> should be set as 'on'.
            e.type === "checkbox"
            ? "on"
            : ""
          : String(s);
    (l !== a || !("_value" in e)) && (e.value = a),
      s == null && e.removeAttribute(t),
      (e._value = s);
    return;
  }
  let o = !1;
  if (s === "" || s == null) {
    const l = typeof e[t];
    l === "boolean"
      ? (s = Bn(s))
      : s == null && l === "string"
        ? ((s = ""), (o = !0))
        : l === "number" && ((s = 0), (o = !0));
  }
  try {
    e[t] = s;
  } catch {}
  o && e.removeAttribute(i || t);
}
function tl(e, t, s, n) {
  e.addEventListener(t, s, n);
}
function sl(e, t, s, n) {
  e.removeEventListener(t, s, n);
}
const En = Symbol("_vei");
function nl(e, t, s, n, i = null) {
  const r = e[En] || (e[En] = {}),
    o = r[t];
  if (n && o) o.value = n;
  else {
    const [l, a] = il(t);
    if (n) {
      const d = (r[t] = ll(n, i));
      tl(e, l, d, a);
    } else o && (sl(e, l, o, a), (r[t] = void 0));
  }
}
const Tn = /(?:Once|Passive|Capture)$/;
function il(e) {
  let t;
  if (Tn.test(e)) {
    t = {};
    let n;
    for (; (n = e.match(Tn)); )
      (e = e.slice(0, e.length - n[0].length)), (t[n[0].toLowerCase()] = !0);
  }
  return [e[2] === ":" ? e.slice(3) : st(e.slice(2)), t];
}
let bs = 0;
const rl = /* @__PURE__ */ Promise.resolve(),
  ol = () => bs || (rl.then(() => (bs = 0)), (bs = Date.now()));
function ll(e, t) {
  const s = (n) => {
    if (!n._vts) n._vts = Date.now();
    else if (n._vts <= s.attached) return;
    Pe(cl(n, s.value), t, 5, [n]);
  };
  return (s.value = e), (s.attached = ol()), s;
}
function cl(e, t) {
  if (R(t)) {
    const s = e.stopImmediatePropagation;
    return (
      (e.stopImmediatePropagation = () => {
        s.call(e), (e._stopped = !0);
      }),
      t.map((n) => (i) => !i._stopped && n && n(i))
    );
  } else return t;
}
const Pn = (e) =>
    e.charCodeAt(0) === 111 &&
    e.charCodeAt(1) === 110 && // lowercase letter
    e.charCodeAt(2) > 96 &&
    e.charCodeAt(2) < 123,
  al = (e, t, s, n, i, r) => {
    const o = i === "svg";
    t === "class"
      ? zo(e, n, o)
      : t === "style"
        ? Qo(e, s, n)
        : Zt(t)
          ? Fs(t) || nl(e, t, s, n, r)
          : (
                t[0] === "."
                  ? ((t = t.slice(1)), !0)
                  : t[0] === "^"
                    ? ((t = t.slice(1)), !1)
                    : ul(e, t, n, o)
              )
            ? (Cn(e, t, n),
              !e.tagName.includes("-") &&
                (t === "value" || t === "checked" || t === "selected") &&
                An(e, t, n, o, r, t !== "value"))
            : /* #11081 force set props for possible async custom element */ e._isVueCE &&
                (/[A-Z]/.test(t) || !Z(n))
              ? Cn(e, Be(t), n, r, t)
              : (t === "true-value"
                  ? (e._trueValue = n)
                  : t === "false-value" && (e._falseValue = n),
                An(e, t, n, o));
  };
function ul(e, t, s, n) {
  if (n)
    return !!(
      t === "innerHTML" ||
      t === "textContent" ||
      (t in e && Pn(t) && M(s))
    );
  if (
    t === "spellcheck" ||
    t === "draggable" ||
    t === "translate" ||
    t === "form" ||
    (t === "list" && e.tagName === "INPUT") ||
    (t === "type" && e.tagName === "TEXTAREA")
  )
    return !1;
  if (t === "width" || t === "height") {
    const i = e.tagName;
    if (i === "IMG" || i === "VIDEO" || i === "CANVAS" || i === "SOURCE")
      return !1;
  }
  return Pn(t) && Z(s) ? !1 : t in e;
}
const fl = /* @__PURE__ */ ie({ patchProp: al }, qo);
let Rn;
function dl() {
  return Rn || (Rn = bo(fl));
}
const hl = (...e) => {
  const t = dl().createApp(...e),
    { mount: s } = t;
  return (
    (t.mount = (n) => {
      const i = gl(n);
      if (!i) return;
      const r = t._component;
      !M(r) && !r.render && !r.template && (r.template = i.innerHTML),
        i.nodeType === 1 && (i.textContent = "");
      const o = s(i, !1, pl(i));
      return (
        i instanceof Element &&
          (i.removeAttribute("v-cloak"), i.setAttribute("data-v-app", "")),
        o
      );
    }),
    t
  );
};
function pl(e) {
  if (e instanceof SVGElement) return "svg";
  if (typeof MathMLElement == "function" && e instanceof MathMLElement)
    return "mathml";
}
function gl(e) {
  return Z(e) ? document.querySelector(e) : e;
}
function ml(e, t, s) {
  return e.logs.filter((n) => {
    if (n.cursor <= s.get(n.runId)) return !1;
    if (t.mode === "all") return !0;
    if (n.runId !== t.runId) return !1;
    const i = e.runs[n.runId];
    return (
      ((n.phaseId && (i == null ? void 0 : i.instanceOfPhase[n.phaseId])) ||
        n.instanceId ||
        n.phaseId) === t.instanceId
    );
  });
}
function _l(e, t, s) {
  s.set(t, Math.max(s.get(t), e.maxCursor));
}
const Mn = 5e3;
function bl() {
  return { runs: {}, logs: [], seen: {}, maxCursor: 0 };
}
function Vi(e) {
  return e.outcome !== null || e.abandoned;
}
function Ki(e) {
  return Object.values(e.phases).sort((t, s) => t.order - s.order);
}
function yl(e) {
  return Ki(e)
    .filter((t) => !Vi(t))
    .map((t) => t.instanceId);
}
function vl(e) {
  (e.recent = []), Yt(e);
}
function wl(e, t) {
  e.recent.includes(t) || e.recent.push(t), Yt(e);
}
function Yt(e) {
  const t = yl(e);
  if (t.length === 0) return;
  const s = /* @__PURE__ */ new Set([...t, ...e.recent]);
  e.visible = Ki(e)
    .map((n) => n.instanceId)
    .filter((n) => s.has(n));
}
function xl(e, t, s) {
  const n = (i) => i.map((r) => (r === t ? s : r));
  (e.recent = n(e.recent)), (e.visible = n(e.visible));
}
const Sl = /* @__PURE__ */ new Set([
  "phase_start",
  "bound",
  "progress",
  "tool_call",
  "tool_result",
  "message",
  "log",
]);
function On(e) {
  return {
    runId: e.run_id,
    adwName: e.adw_name,
    status: e.status,
    startedAt: e.started_at,
    endedAt: e.ended_at,
    phases: {},
    instanceOfPhase: {},
    arrows: [],
    recent: [],
    visible: [],
  };
}
function Gi(e, t) {
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
    error: "",
  };
}
function Il(e, t) {
  return t.phase_id && e.instanceOfPhase[t.phase_id]
    ? e.instanceOfPhase[t.phase_id]
    : t.instance_id || t.phase_id;
}
function Al(e, t) {
  const s = t.instance_id,
    n = e.phases[t.phase_id],
    i = e.phases[s] ?? Gi(t, s);
  return (
    n &&
      n !== i &&
      ((i.started = i.started || n.started),
      (i.startedAt = i.startedAt || n.startedAt),
      (i.lastProgressAt = Math.max(i.lastProgressAt, n.lastProgressAt)),
      (i.outcome = i.outcome ?? n.outcome),
      delete e.phases[t.phase_id],
      xl(e, t.phase_id, s)),
    (e.phases[s] = i),
    (e.instanceOfPhase[t.phase_id] = s),
    (i.phaseId = t.phase_id),
    i
  );
}
function Cl(e, t, s) {
  if (
    t.kind !== "tool_call" &&
    t.kind !== "tool_result" &&
    t.kind !== "message"
  )
    return;
  const n = t.kind === "message" && t.source_instance && t.target_instance;
  e.arrows.push({
    id: t.event_id,
    cursor: t.cursor,
    kind: t.kind,
    from: n ? t.source_instance : s,
    to: n ? t.target_instance : s,
    text: t.message,
    dashed: t.kind === "tool_result",
  });
}
function El(e, t) {
  var r;
  const s = Date.parse(t.recorded_at) || 0,
    n = Il(e, t);
  if (!n) return;
  const i =
    t.kind === "bound" ? Al(e, t) : ((r = e.phases)[n] ?? (r[n] = Gi(t, n)));
  if (
    (t.attempt !== null && t.attempt !== void 0 && (i.attempt = t.attempt),
    Cl(e, t, i.instanceId),
    t.kind === "constructed"
      ? ((i.constructed = !0), (i.className = t.message))
      : t.kind === "purpose"
        ? (i.purpose = t.message)
        : t.kind === "cleanup"
          ? ((i.cleanup = t.message),
            !i.started && i.outcome === null && (i.abandoned = !0))
          : t.kind === "error" && (i.error = t.message),
    i.outcome !== null || i.abandoned)
  ) {
    Yt(e);
    return;
  }
  if (t.kind === "phase_end" && t.status && t.status !== "running") {
    (i.outcome = t.status),
      (i.endedAt = s),
      (i.started = !0),
      wl(e, i.instanceId);
    return;
  }
  if (
    (t.kind === "waiting"
      ? ((i.waitDeadlineAt = t.deadline_at ? Date.parse(t.deadline_at) : null),
        (i.waitReason = t.message),
        (i.lastProgressAt = s))
      : Sl.has(t.kind) &&
        ((i.waitDeadlineAt = null),
        (i.waitReason = ""),
        (i.lastProgressAt = s)),
    (t.kind === "phase_start" || t.kind === "bound") && !i.started)
  ) {
    (i.started = !0),
      (i.startedAt = s),
      t.kind === "phase_start" && (i.phaseId = t.phase_id),
      vl(e);
    return;
  }
  Yt(e);
}
function Tl(e) {
  const t = [e.run_id, e.phase_name, e.kind].filter(Boolean).join(" ");
  return `${e.recorded_at} [${t}] ${e.message}`;
}
function Pl(e, t) {
  var r, o, l, a;
  const s = t.events.filter((d) => !e.seen[d.event_id]),
    n = t.runs.some((d) => {
      const f = e.runs[d.run_id];
      return !f || f.status !== d.status || f.endedAt !== d.ended_at;
    });
  if (s.length === 0 && !n) return e;
  const i = structuredClone(e);
  for (const d of t.runs) {
    const f = (r = i.runs)[(o = d.run_id)] ?? (r[o] = On(d));
    (f.status = d.status), (f.endedAt = d.ended_at);
  }
  for (const d of s.sort((f, h) => f.cursor - h.cursor)) {
    (i.seen[d.event_id] = !0), (i.maxCursor = Math.max(i.maxCursor, d.cursor));
    const f =
      (l = i.runs)[(a = d.run_id)] ??
      (l[a] = On({
        run_id: d.run_id,
        adw_name: d.adw_name,
        status: "running",
        started_at: d.recorded_at,
        ended_at: null,
      }));
    El(f, d),
      i.logs.push({
        cursor: d.cursor,
        eventId: d.event_id,
        runId: d.run_id,
        phaseId: d.phase_id,
        instanceId: d.instance_id,
        recordedAt: d.recorded_at,
        kind: d.kind,
        text: Tl(d),
      });
  }
  return (
    i.logs.sort((d, f) => d.cursor - f.cursor),
    i.logs.length > Mn && i.logs.splice(0, i.logs.length - Mn),
    i
  );
}
const Rl = {
    idle: "Idle -- no pilot run recorded yet",
    live: "Live",
    completed: "Completed",
    pinned: "Pinned after failure",
  },
  Ml = {
    waiting: "Waiting",
    running: "Running",
    stalled: "Stalled",
    fail: "Fail",
    pass: "Pass",
  };
function Dn(e, t) {
  if (!e) return "";
  const s = Math.max(0, Math.round((t - e) / 1e3));
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
}
function Ol(e, t, s, n, i, r) {
  let o = "waiting",
    l = "";
  if (e.outcome === "pass" || e.outcome === "fail")
    (o = e.outcome),
      (l = [Dn(e.startedAt, e.endedAt), e.error].filter(Boolean).join(" -- "));
  else if (e.abandoned) l = "never executed";
  else if (!e.started) l = "constructed, not started";
  else if (t.status !== "running")
    (o = "stalled"),
      (l =
        t.status === "interrupted"
          ? "process ended without recording an outcome; no cleanup recorded"
          : `run ended (${t.status}) without an outcome for this phase`);
  else {
    const a = i.evaluate(
      {
        started: e.started,
        terminal: Vi(e),
        lastProgressAt: e.lastProgressAt,
        waitDeadlineAt: e.waitDeadlineAt,
        waitReason: e.waitReason,
      },
      s,
      n,
    );
    (o = a ? "stalled" : e.waitDeadlineAt !== null ? "waiting" : "running"),
      (l = [Dn(e.startedAt, s), (a == null ? void 0 : a.reason) ?? e.waitReason]
        .filter(Boolean)
        .join(" -- "));
  }
  return {
    instanceId: e.instanceId,
    name: e.name,
    attempt: e.attempt,
    status: o,
    statusLabel: Ml[o],
    detail: l,
    purpose: e.purpose,
    selected: r,
  };
}
function Dl(e, t, s, n, i) {
  if (!e) return { runId: "", columns: [], rows: [] };
  const r = e.visible
      .map((a) => e.phases[a])
      .filter(Boolean)
      .map((a) => Ol(a, e, t, s, n, a.instanceId === i)),
    o = new Map(r.map((a, d) => [a.instanceId, d])),
    l = e.arrows
      .filter((a) => o.has(a.from) && o.has(a.to))
      .map((a) => ({
        id: a.id,
        from: o.get(a.from),
        to: o.get(a.to),
        text: a.text,
        dashed: a.dashed,
        kind: a.kind,
      }));
  return { runId: e.runId, columns: r, rows: l };
}
function $l(e, t, s, n) {
  var r;
  const i =
    s.mode === "phase"
      ? (r = n.runs[s.runId]) == null
        ? void 0
        : r.phases[s.instanceId]
      : void 0;
  return {
    modeLabel: Rl[t],
    filterLabel:
      s.mode === "all"
        ? "All events"
        : `Run ${s.runId} -- phase ${(i == null ? void 0 : i.name) ?? s.instanceId} (${s.instanceId}${i != null && i.attempt ? `, attempt ${i.attempt}` : ""})`,
    clearLabel: e
      ? `Clear displayed logs for ${e.runId}`
      : "Clear displayed logs",
    clearDisabledReason: e
      ? ""
      : "No ADW run is selected, so there is nothing run-scoped to clear.",
  };
}
class Fl {
  constructor(t) {
    Y(this, "state", bl());
    Y(this, "selected", { runId: null, pinReleased: !1 });
    Y(this, "filter", { mode: "all" });
    Y(this, "connection", { status: "connecting" });
    Y(this, "timeoutSeconds", 120);
    Y(this, "lastDelayMs", null);
    Y(this, "renderError", "");
    Y(this, "tick", null);
    Y(this, "unsubscribe", null);
    Y(this, "listeners", /* @__PURE__ */ new Set());
    this.deps = t;
  }
  start() {
    (this.unsubscribe = this.deps.source.subscribe({
      onPage: (s) => this.onPage(s),
      onConnection: (s) => {
        (this.connection = s), this.publish();
      },
    })),
      this.deps.source.start();
    const t = () => {
      this.publish(),
        (this.tick = this.deps.timer.set(t, this.deps.tickMs ?? 1e3));
    };
    this.tick = this.deps.timer.set(t, this.deps.tickMs ?? 1e3);
  }
  /** The view came into sight: catch up now rather than on the slow cadence. */
  wake() {
    this.deps.source.wake();
  }
  dispose() {
    var t;
    this.deps.source.stop(),
      (t = this.unsubscribe) == null || t.call(this),
      this.deps.timer.clear(this.tick),
      this.deps.legacy.setVisible(!0),
      this.listeners.clear();
  }
  subscribe(t) {
    return (
      this.listeners.add(t),
      t(this.view()),
      () => {
        this.listeners.delete(t);
      }
    );
  }
  selectPhase(t) {
    this.selected.runId &&
      ((this.filter = {
        mode: "phase",
        runId: this.selected.runId,
        instanceId: t,
      }),
      this.publish());
  }
  allEvents() {
    (this.filter = { mode: "all" }), this.publish();
  }
  followLive() {
    this.follow(this.deps.selection.followLive(this.selected, this.runs())),
      this.publish();
  }
  clearSelectedRun() {
    this.selected.runId &&
      (_l(this.state, this.selected.runId, this.deps.cleared), this.publish());
  }
  reportRenderError(t) {
    (this.renderError = t), this.publish();
  }
  runs() {
    return Object.values(this.state.runs).map((t) => ({
      runId: t.runId,
      status: t.status,
      startedAt: t.startedAt,
    }));
  }
  follow(t) {
    t.runId !== this.selected.runId && (this.filter = { mode: "all" }),
      (this.selected = t);
  }
  onPage(t) {
    var n, i;
    (i = (n = this.deps.clock).align) == null || i.call(n, t.server_now),
      (this.timeoutSeconds = t.stall_timeout_seconds);
    const s = this.state;
    if (
      ((this.state = Pl(this.state, t)),
      !t.bootstrap && this.state !== s && t.events.length > 0)
    ) {
      const r = Date.parse(t.events[t.events.length - 1].recorded_at);
      Number.isNaN(r) ||
        (this.lastDelayMs = Math.max(0, this.deps.clock.now() - r));
    }
    this.follow(this.deps.selection.select(this.selected, this.runs())),
      this.publish();
  }
  view() {
    const t = this.selected.runId
        ? this.state.runs[this.selected.runId]
        : void 0,
      s = this.deps.selection.mode(this.selected, this.runs()),
      n =
        this.filter.mode === "phase" &&
        this.filter.runId === (t == null ? void 0 : t.runId)
          ? this.filter.instanceId
          : null,
      i = this.deps.renderer.render(
        Dl(
          t,
          this.deps.clock.now(),
          this.timeoutSeconds * 1e3,
          this.deps.stall,
          n,
        ),
      );
    return {
      runId: (t == null ? void 0 : t.runId) ?? null,
      adwName: (t == null ? void 0 : t.adwName) ?? "",
      runStatus: (t == null ? void 0 : t.status) ?? null,
      mode: s,
      diagram: i.model,
      lines: ml(this.state, this.filter, this.deps.cleared),
      phaseSelected: this.filter.mode === "phase",
      connection: this.connection,
      renderError: i.error || this.renderError,
      stallTimeoutSeconds: this.timeoutSeconds,
      lastDelayMs: this.lastDelayMs,
      ...$l(t, s, this.filter, this.state),
    };
  }
  publish() {
    this.deps.legacy.setVisible(this.filter.mode === "all");
    const t = this.view();
    for (const s of this.listeners) s(t);
  }
}
function ys(e, t) {
  return (
    e.startedAt.localeCompare(t.startedAt) || e.runId.localeCompare(t.runId)
  );
}
function $n(e) {
  return (
    (e == null ? void 0 : e.status) === "fail" ||
    (e == null ? void 0 : e.status) === "interrupted"
  );
}
class Ll {
  select(t, s) {
    const n = s.find((o) => o.runId === t.runId);
    if (
      (n == null ? void 0 : n.status) === "running" ||
      ($n(n) && !t.pinReleased)
    )
      return t;
    const i = s.filter((o) => o.status === "running").sort(ys)[0];
    if (i) return { runId: i.runId, pinReleased: !1 };
    const r = [...s].sort(ys).at(-1);
    return n && (!r || ys(r, n) <= 0)
      ? t
      : { runId: (r == null ? void 0 : r.runId) ?? null, pinReleased: !1 };
  }
  followLive(t, s) {
    return this.select({ runId: t.runId, pinReleased: !0 }, s);
  }
  mode(t, s) {
    const n = s.find((i) => i.runId === t.runId);
    return n
      ? n.status === "running"
        ? "live"
        : $n(n) && !t.pinReleased
          ? "pinned"
          : "completed"
      : "idle";
  }
}
function vs(e) {
  return `${Math.max(0, Math.round(e / 1e3))}s`;
}
class Nl {
  evaluate(t, s, n) {
    if (!t.started || t.terminal) return null;
    if (t.waitDeadlineAt !== null) {
      const r = s - t.waitDeadlineAt;
      return r > 0
        ? { reason: `wait deadline passed ${vs(r)} ago: ${t.waitReason}` }
        : null;
    }
    const i = s - t.lastProgressAt;
    return i > n
      ? { reason: `no progress for ${vs(i)} (timeout ${vs(n)})` }
      : null;
  }
}
class kl {
  async getJSON(t) {
    const s = await fetch(t, { cache: "no-store" });
    if (!s.ok) throw new Error(`HTTP ${s.status} from ${t}`);
    return s.json();
  }
}
class Hl {
  set(t, s) {
    return window.setTimeout(t, s);
  }
  clear(t) {
    window.clearTimeout(t);
  }
}
class jl {
  constructor() {
    Y(this, "offset", 0);
  }
  align(t) {
    const s = Date.parse(t);
    Number.isNaN(s) || (this.offset = s - Date.now());
  }
  now() {
    return Date.now() + this.offset;
  }
}
class Bl {
  constructor(t = "adwDebugger.clearedThrough.v1") {
    Y(this, "marks", {});
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
    } catch {}
  }
}
class Wl {
  constructor(t) {
    this.node = t;
  }
  setVisible(t) {
    this.node && (this.node.style.display = t ? "" : "none");
  }
}
class Ul {
  constructor(t, s, n) {
    Y(this, "listeners", /* @__PURE__ */ new Set());
    Y(this, "cursor", null);
    Y(this, "handle", null);
    Y(this, "running", !1);
    Y(this, "inflight", !1);
    Y(this, "failures", 0);
    (this.http = t), (this.timer = s), (this.options = n);
  }
  subscribe(t) {
    return (
      this.listeners.add(t),
      () => {
        this.listeners.delete(t);
      }
    );
  }
  start() {
    this.running ||
      ((this.running = !0), this.emit({ status: "connecting" }), this.poll());
  }
  stop() {
    (this.running = !1), this.timer.clear(this.handle), (this.handle = null);
  }
  wake() {
    !this.running ||
      this.inflight ||
      (this.timer.clear(this.handle), this.poll());
  }
  emit(t) {
    for (const s of this.listeners) s.onConnection(t);
  }
  schedule() {
    if (!this.running) return;
    const t =
      this.failures > 0
        ? Math.min(
            this.options.retryStepMs * this.failures,
            this.options.retryMaxMs,
          )
        : this.options.isActive()
          ? this.options.activeMs
          : this.options.idleMs;
    this.handle = this.timer.set(() => void this.poll(), t);
  }
  async poll() {
    if (!(this.inflight || !this.running)) {
      this.inflight = !0;
      try {
        const t =
            this.cursor === null
              ? this.options.url
              : `${this.options.url}?after=${this.cursor}`,
          s = await this.http.getJSON(t);
        if (!this.running) return;
        if (((this.failures = 0), s.ok)) {
          (this.cursor = Math.max(this.cursor ?? 0, s.cursor)),
            this.emit({ status: "connected" });
          for (const n of this.listeners) n.onPage(s);
        } else
          this.emit({
            status: "degraded",
            reason: s.error || "the feed could not read the trace database",
          });
      } catch (t) {
        (this.failures += 1),
          this.emit({
            status: "disconnected",
            attempts: this.failures,
            reason: t instanceof Error ? t.message : String(t),
          });
      } finally {
        (this.inflight = !1), this.schedule();
      }
    }
  }
}
class Vl {
  constructor() {
    Y(this, "lastGood", { runId: "", columns: [], rows: [] });
  }
  render(t) {
    try {
      const s = /* @__PURE__ */ new Set();
      for (const n of t.columns) {
        if (!n.instanceId || s.has(n.instanceId))
          throw new Error(
            `duplicate or empty phase instance id "${n.instanceId}"`,
          );
        s.add(n.instanceId);
      }
      for (const n of t.rows)
        if (!t.columns[n.from] || !t.columns[n.to])
          throw new Error(
            `arrow ${n.id} points at a column that is not on screen`,
          );
      return (this.lastGood = t), { model: t, error: "" };
    } catch (s) {
      return {
        model: this.lastGood,
        error: s instanceof Error ? s.message : String(s),
      };
    }
  }
}
const Kl = { class: "adwdbg-log" },
  Gl = { class: "adwdbg-log-head" },
  ql = { class: "adwdbg-log-label" },
  Jl = {
    key: 0,
    class: "adwdbg-log-empty",
  },
  zl = ["data-kind", "data-run"],
  Yl = /* @__PURE__ */ Js({
    __name: "LogPane",
    props: {
      lines: {},
      label: {},
      tall: { type: Boolean },
    },
    setup(e) {
      const t = e,
        s = Cs(null),
        n = Cs(!0);
      function i() {
        const r = s.value;
        r && (n.value = r.scrollHeight - r.scrollTop - r.clientHeight <= 8);
      }
      return (
        Bt(
          () => t.lines.length,
          async () => {
            n.value &&
              (await ci(),
              s.value && (s.value.scrollTop = s.value.scrollHeight));
          },
          { immediate: !0 },
        ),
        (r, o) => (
          k(),
          V("div", Kl, [
            D("div", Gl, [
              D("span", ql, U(r.label), 1),
              D(
                "span",
                null,
                U(r.lines.length) +
                  " line" +
                  U(r.lines.length === 1 ? "" : "s") +
                  U(n.value ? "" : " · paused (scroll to bottom to follow)"),
                1,
              ),
            ]),
            D(
              "div",
              {
                ref_key: "host",
                ref: s,
                class: Xe(["adwdbg-log-lines", { "adwdbg-log-tall": r.tall }]),
                role: "log",
                onScroll: i,
              },
              [
                r.lines.length === 0
                  ? (k(), V("div", Jl, "No ADW events to show."))
                  : Ie("", !0),
                (k(!0),
                V(
                  Q,
                  null,
                  Ze(
                    r.lines,
                    (l) => (
                      k(),
                      V(
                        "div",
                        {
                          key: l.eventId,
                          class: "adwdbg-log-line",
                          "data-kind": l.kind,
                          "data-run": l.runId,
                        },
                        U(l.text),
                        9,
                        zl,
                      )
                    ),
                  ),
                  128,
                )),
              ],
              34,
            ),
          ])
        )
      );
    },
  }),
  Zl = { class: "sd" },
  Xl = { class: "sd-tools" },
  Ql = { class: "sd-zoom-value" },
  ec = { class: "sd-scroll" },
  tc = [
    "data-status",
    "data-instance",
    "data-edge",
    "title",
    "aria-pressed",
    "onClick",
  ],
  sc = { class: "sd-name" },
  nc = { class: "sd-status" },
  ic = {
    key: 0,
    class: "sd-detail",
  },
  rc = {
    class: "sd-body",
    style: { order: "1" },
  },
  oc = {
    key: 0,
    class: "sd-row sd-row-empty",
  },
  lc = ["data-kind"],
  cc = { class: "sd-label" },
  ac = /* @__PURE__ */ Js({
    __name: "SequenceDiagram",
    props: {
      model: {},
    },
    emits: ["phase-click"],
    setup(e, { emit: t }) {
      const s = e,
        n = t,
        i = Cs(1),
        r = Os(() => Math.max(1, s.model.columns.length)),
        o = Os(() => 100 / r.value);
      function l(h) {
        return { left: `${(h + 0.5) * o.value}%` };
      }
      function a(h) {
        if (h.from === h.to) {
          const w = h.from === r.value - 1 ? 0.48 : 0.94;
          return {
            marginLeft: `${(h.from + 0.5) * o.value}%`,
            width: `${o.value * w}%`,
          };
        }
        return {
          marginLeft: `${(Math.min(h.from, h.to) + 0.5) * o.value}%`,
          width: `${Math.abs(h.to - h.from) * o.value}%`,
        };
      }
      function d(h) {
        return h.from === h.to ? "self" : h.from < h.to ? "right" : "left";
      }
      function f(h) {
        return [h.purpose, h.instanceId].filter(Boolean).join(`
`);
      }
      return (h, x) => (
        k(),
        V("div", Zl, [
          D("div", Xl, [
            D(
              "button",
              {
                type: "button",
                class: "sd-zoom",
                "aria-label": "Zoom out",
                onClick:
                  x[0] ||
                  (x[0] = (w) => (i.value = Math.max(0.4, i.value - 0.1))),
              },
              "-",
            ),
            D("span", Ql, U(Math.round(i.value * 100)) + "%", 1),
            D(
              "button",
              {
                type: "button",
                class: "sd-zoom",
                "aria-label": "Zoom in",
                onClick:
                  x[1] ||
                  (x[1] = (w) => (i.value = Math.min(2, i.value + 0.1))),
              },
              "+",
            ),
            D(
              "button",
              {
                type: "button",
                class: "sd-zoom",
                onClick: x[2] || (x[2] = (w) => (i.value = 1)),
              },
              "Reset",
            ),
          ]),
          D("div", ec, [
            D(
              "div",
              {
                class: "sd-canvas",
                style: ke({ zoom: i.value, minWidth: `${r.value * 260}px` }),
              },
              [
                (k(),
                V(
                  Q,
                  null,
                  Ze(["top", "bottom"], (w) =>
                    D(
                      "div",
                      {
                        key: w,
                        class: Xe(["sd-titles", `sd-titles-${w}`]),
                        style: ke({ order: w === "top" ? 0 : 2 }),
                      },
                      [
                        (k(!0),
                        V(
                          Q,
                          null,
                          Ze(
                            h.model.columns,
                            (C) => (
                              k(),
                              V(
                                "button",
                                {
                                  key: C.instanceId,
                                  type: "button",
                                  class: Xe([
                                    "sd-box",
                                    { "sd-selected": C.selected },
                                  ]),
                                  "data-status": C.status,
                                  "data-instance": C.instanceId,
                                  "data-edge": w,
                                  title: f(C),
                                  "aria-pressed": C.selected,
                                  onClick: (O) =>
                                    n("phase-click", C.instanceId),
                                },
                                [
                                  D("span", sc, [
                                    Tt(U(C.name), 1),
                                    C.attempt
                                      ? (k(),
                                        V(
                                          Q,
                                          { key: 0 },
                                          [Tt(" · attempt " + U(C.attempt), 1)],
                                          64,
                                        ))
                                      : Ie("", !0),
                                  ]),
                                  D("span", nc, U(C.statusLabel), 1),
                                  C.detail
                                    ? (k(), V("span", ic, U(C.detail), 1))
                                    : Ie("", !0),
                                ],
                                10,
                                tc,
                              )
                            ),
                          ),
                          128,
                        )),
                      ],
                      6,
                    ),
                  ),
                  64,
                )),
                D("div", rc, [
                  h.model.rows.length === 0
                    ? (k(),
                      V("div", oc, [
                        (k(!0),
                        V(
                          Q,
                          null,
                          Ze(
                            h.model.columns,
                            (w, C) => (
                              k(),
                              V(
                                "span",
                                {
                                  key: w.instanceId,
                                  class: "sd-lifeline",
                                  style: ke(l(C)),
                                },
                                null,
                                4,
                              )
                            ),
                          ),
                          128,
                        )),
                      ]))
                    : Ie("", !0),
                  (k(!0),
                  V(
                    Q,
                    null,
                    Ze(
                      h.model.rows,
                      (w) => (
                        k(),
                        V(
                          "div",
                          {
                            key: w.id,
                            class: "sd-row",
                          },
                          [
                            (k(!0),
                            V(
                              Q,
                              null,
                              Ze(
                                h.model.columns,
                                (C, O) => (
                                  k(),
                                  V(
                                    "span",
                                    {
                                      key: C.instanceId,
                                      class: "sd-lifeline",
                                      style: ke(l(O)),
                                    },
                                    null,
                                    4,
                                  )
                                ),
                              ),
                              128,
                            )),
                            D(
                              "div",
                              {
                                class: Xe([
                                  "sd-message",
                                  [`sd-${d(w)}`, { "sd-dashed": w.dashed }],
                                ]),
                                "data-kind": w.kind,
                                style: ke(a(w)),
                              },
                              [
                                D("div", cc, U(w.text), 1),
                                x[3] ||
                                  (x[3] = D(
                                    "div",
                                    { class: "sd-line" },
                                    [D("span", { class: "sd-head" })],
                                    -1,
                                  )),
                              ],
                              14,
                              lc,
                            ),
                          ],
                        )
                      ),
                    ),
                    128,
                  )),
                ]),
              ],
              4,
            ),
          ]),
        ])
      );
    },
  }),
  uc = {
    key: 0,
    class: "adwdbg",
    "aria-label": "Live ADW sequence debugger",
  },
  fc = { class: "adwdbg-head" },
  dc = { "data-field": "adw" },
  hc = { "data-field": "run" },
  pc = ["data-run-status"],
  gc = ["data-mode"],
  mc = {
    class: "adwdbg-legend",
    "aria-label": "Status colours",
  },
  _c = ["data-status"],
  bc = {
    key: 0,
    class: "adwdbg-warn",
    "data-warning": "connection",
    role: "status",
  },
  yc = {
    key: 1,
    class: "adwdbg-warn",
    "data-warning": "feed",
    role: "status",
  },
  vc = {
    key: 2,
    class: "adwdbg-warn",
    "data-warning": "render",
    role: "alert",
  },
  wc = {
    key: 4,
    class: "adwdbg-idle",
    "data-field": "idle",
  },
  xc = { class: "adwdbg-bar" },
  Sc = ["disabled"],
  Ic = ["disabled", "title"],
  Ac = {
    key: 0,
    class: "adwdbg-note",
  },
  Cc = {
    class: "adwdbg-note",
    "data-field": "timing",
  },
  Ec = /* @__PURE__ */ Js({
    __name: "DebuggerPanel",
    props: {
      controller: {},
    },
    setup(e) {
      const t = e,
        s = Mr(null),
        n = t.controller.subscribe((r) => {
          s.value = r;
        });
      mi(n),
        bi(
          (r) => (
            t.controller.reportRenderError(
              r instanceof Error ? r.message : String(r),
            ),
            !1
          ),
        );
      const i = [
        ["waiting", "Waiting"],
        ["running", "Running"],
        ["stalled", "Stalled"],
        ["fail", "Fail"],
        ["pass", "Pass"],
      ];
      return (r, o) =>
        s.value
          ? (k(),
            V("section", uc, [
              D("header", fc, [
                o[5] ||
                  (o[5] = D(
                    "strong",
                    { class: "adwdbg-title" },
                    "ADW sequence",
                    -1,
                  )),
                s.value.runId
                  ? (k(),
                    V(
                      Q,
                      { key: 0 },
                      [
                        D("span", dc, U(s.value.adwName), 1),
                        D("span", hc, "run " + U(s.value.runId), 1),
                        D(
                          "span",
                          {
                            class: "adwdbg-chip",
                            "data-run-status": s.value.runStatus,
                            "data-field": "status",
                          },
                          U(s.value.runStatus),
                          9,
                          pc,
                        ),
                      ],
                      64,
                    ))
                  : Ie("", !0),
                D(
                  "span",
                  {
                    class: "adwdbg-chip",
                    "data-mode": s.value.mode,
                    "data-field": "mode",
                  },
                  U(s.value.modeLabel),
                  9,
                  gc,
                ),
                D("span", mc, [
                  (k(),
                  V(
                    Q,
                    null,
                    Ze(i, ([l, a]) =>
                      D(
                        "span",
                        {
                          key: l,
                          class: "adwdbg-key",
                          "data-status": l,
                        },
                        U(a),
                        9,
                        _c,
                      ),
                    ),
                    64,
                  )),
                  o[4] ||
                    (o[4] = D(
                      "span",
                      { class: "adwdbg-key adwdbg-key-selected" },
                      "Selected",
                      -1,
                    )),
                ]),
              ]),
              s.value.connection.status === "disconnected"
                ? (k(),
                  V(
                    "p",
                    bc,
                    " Event feed disconnected (attempt " +
                      U(s.value.connection.attempts) +
                      "): " +
                      U(s.value.connection.reason) +
                      ". The diagram shows the last events received; this is a connection problem, not an ADW failure. ",
                    1,
                  ))
                : s.value.connection.status === "degraded"
                  ? (k(),
                    V(
                      "p",
                      yc,
                      " The dashboard cannot read the ADW trace: " +
                        U(s.value.connection.reason),
                      1,
                    ))
                  : Ie("", !0),
              s.value.renderError
                ? (k(),
                  V(
                    "p",
                    vc,
                    " Diagram could not be redrawn (" +
                      U(s.value.renderError) +
                      "). Showing the last good diagram; the terminal is unaffected. ",
                    1,
                  ))
                : Ie("", !0),
              s.value.diagram.columns.length
                ? (k(),
                  ki(
                    ac,
                    {
                      key: 3,
                      model: s.value.diagram,
                      onPhaseClick:
                        o[0] || (o[0] = (l) => t.controller.selectPhase(l)),
                    },
                    null,
                    8,
                    ["model"],
                  ))
                : (k(),
                  V(
                    "p",
                    wc,
                    U(
                      s.value.runId
                        ? "This run has not constructed a phase yet."
                        : "No pilot ADW run has been recorded yet.",
                    ),
                    1,
                  )),
              D("div", xc, [
                D(
                  "button",
                  {
                    type: "button",
                    class: "am-btn",
                    "data-action": "follow-live",
                    onClick: o[1] || (o[1] = (l) => t.controller.followLive()),
                  },
                  "Follow live",
                ),
                D(
                  "button",
                  {
                    type: "button",
                    class: "am-btn",
                    "data-action": "all-events",
                    disabled: !s.value.phaseSelected,
                    onClick: o[2] || (o[2] = (l) => t.controller.allEvents()),
                  },
                  "All events",
                  8,
                  Sc,
                ),
                D(
                  "button",
                  {
                    type: "button",
                    class: "am-btn",
                    "data-action": "clear-run",
                    disabled: !!s.value.clearDisabledReason,
                    title: s.value.clearDisabledReason,
                    onClick:
                      o[3] || (o[3] = (l) => t.controller.clearSelectedRun()),
                  },
                  U(s.value.clearLabel),
                  9,
                  Ic,
                ),
                s.value.clearDisabledReason
                  ? (k(), V("span", Ac, U(s.value.clearDisabledReason), 1))
                  : Ie("", !0),
                D("span", Cc, [
                  Tt(
                    " stall timeout " + U(s.value.stallTimeoutSeconds) + "s",
                    1,
                  ),
                  s.value.lastDelayMs !== null
                    ? (k(),
                      V(
                        Q,
                        { key: 0 },
                        [
                          Tt(
                            " · last event shown " +
                              U(s.value.lastDelayMs) +
                              " ms after it was recorded",
                            1,
                          ),
                        ],
                        64,
                      ))
                    : Ie("", !0),
                ]),
              ]),
              Te(
                Yl,
                {
                  lines: s.value.lines,
                  label: `ADW events — ${s.value.filterLabel}`,
                  tall: s.value.phaseSelected,
                },
                null,
                8,
                ["lines", "label", "tall"],
              ),
            ]))
          : Ie("", !0);
    },
  });
function Tc(e = document) {
  const t = e.getElementById("terminal"),
    s = e.getElementById("terminal-stream"),
    n = (t == null ? void 0 : t.querySelector(".terminal-toolbar")) ?? s;
  if (!t || !s || !n || e.getElementById("adw-debugger-root")) return null;
  const i = e.createElement("div");
  (i.id = "adw-debugger-root"), n.parentNode.insertBefore(i, n);
  const r = new Hl(),
    o = new Fl({
      source: new Ul(new kl(), r, {
        url: "/api/adw-debugger/feed",
        activeMs: 500,
        idleMs: 5e3,
        retryStepMs: 1e3,
        retryMaxMs: 5e3,
        isActive: () =>
          t.classList.contains("active") && e.visibilityState !== "hidden",
      }),
      selection: new Ll(),
      stall: new Nl(),
      renderer: new Vl(),
      cleared: new Bl(),
      legacy: new Wl(s),
      clock: new jl(),
      timer: r,
    }),
    l = hl(Ec, { controller: o });
  l.mount(i), o.start();
  const a = () => o.wake(),
    d = new MutationObserver(a);
  return (
    d.observe(t, { attributes: !0, attributeFilter: ["class"] }),
    e.addEventListener("visibilitychange", a),
    {
      controller: o,
      unmount() {
        d.disconnect(),
          e.removeEventListener("visibilitychange", a),
          o.dispose(),
          l.unmount(),
          i.remove();
      },
    }
  );
}
window.adwDebugger = Tc();
export { Tc as mountAdwDebugger };
