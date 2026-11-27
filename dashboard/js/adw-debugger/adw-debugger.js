var ai = Object.defineProperty;
var ci = (e, t, s) => t in e ? ai(e, t, { enumerable: !0, configurable: !0, writable: !0, value: s }) : e[t] = s;
var N = (e, t, s) => ci(e, typeof t != "symbol" ? t + "" : t, s);
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
const G = {}, ft = [], Oe = () => {
}, ui = () => !1, os = (e) => e.charCodeAt(0) === 111 && e.charCodeAt(1) === 110 && // uppercase letter
(e.charCodeAt(2) > 122 || e.charCodeAt(2) < 97), Gs = (e) => e.startsWith("onUpdate:"), ie = Object.assign, qs = (e, t) => {
  const s = e.indexOf(t);
  s > -1 && e.splice(s, 1);
}, fi = Object.prototype.hasOwnProperty, B = (e, t) => fi.call(e, t), D = Array.isArray, dt = (e) => ls(e) === "[object Map]", qn = (e) => ls(e) === "[object Set]", F = (e) => typeof e == "function", Q = (e) => typeof e == "string", qe = (e) => typeof e == "symbol", Y = (e) => e !== null && typeof e == "object", Jn = (e) => (Y(e) || F(e)) && F(e.then) && F(e.catch), zn = Object.prototype.toString, ls = (e) => zn.call(e), di = (e) => ls(e).slice(8, -1), Yn = (e) => ls(e) === "[object Object]", Js = (e) => Q(e) && e !== "NaN" && e[0] !== "-" && "" + parseInt(e, 10) === e, At = /* @__PURE__ */ Ks(
  // the leading comma is intentional so empty string "" is also included
  ",key,ref,ref_for,ref_key,onVnodeBeforeMount,onVnodeMounted,onVnodeBeforeUpdate,onVnodeUpdated,onVnodeBeforeUnmount,onVnodeUnmounted"
), as = (e) => {
  const t = /* @__PURE__ */ Object.create(null);
  return (s) => t[s] || (t[s] = e(s));
}, hi = /-(\w)/g, Ge = as(
  (e) => e.replace(hi, (t, s) => s ? s.toUpperCase() : "")
), pi = /\B([A-Z])/g, lt = as(
  (e) => e.replace(pi, "-$1").toLowerCase()
), Xn = as((e) => e.charAt(0).toUpperCase() + e.slice(1)), bs = as(
  (e) => e ? `on${Xn(e)}` : ""
), Ke = (e, t) => !Object.is(e, t), _s = (e, ...t) => {
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
const cs = () => mn || (mn = typeof globalThis < "u" ? globalThis : typeof self < "u" ? self : typeof window < "u" ? window : typeof global < "u" ? global : {});
function ge(e) {
  if (D(e)) {
    const t = {};
    for (let s = 0; s < e.length; s++) {
      const n = e[s], r = Q(n) ? vi(n) : ge(n);
      if (r)
        for (const i in r)
          t[i] = r[i];
    }
    return t;
  } else if (Q(e) || Y(e))
    return e;
}
const mi = /;(?![^(]*\))/g, bi = /:([^]+)/, _i = /\/\*[^]*?\*\//g;
function vi(e) {
  const t = {};
  return e.replace(_i, "").split(mi).forEach((s) => {
    if (s) {
      const n = s.split(bi);
      n.length > 1 && (t[n[0].trim()] = n[1].trim());
    }
  }), t;
}
function Je(e) {
  let t = "";
  if (Q(e))
    t = e;
  else if (D(e))
    for (let s = 0; s < e.length; s++) {
      const n = Je(e[s]);
      n && (t += n + " ");
    }
  else if (Y(e))
    for (const s in e)
      e[s] && (t += s + " ");
  return t.trim();
}
const wi = "itemscope,allowfullscreen,formnovalidate,ismap,nomodule,novalidate,readonly", yi = /* @__PURE__ */ Ks(wi);
function Qn(e) {
  return !!e || e === "";
}
const er = (e) => !!(e && e.__v_isRef === !0), R = (e) => Q(e) ? e : e == null ? "" : D(e) || Y(e) && (e.toString === zn || !F(e.toString)) ? er(e) ? R(e.value) : JSON.stringify(e, tr, 2) : String(e), tr = (e, t) => er(t) ? tr(e, t.value) : dt(t) ? {
  [`Map(${t.size})`]: [...t.entries()].reduce(
    (s, [n, r], i) => (s[vs(n, i) + " =>"] = r, s),
    {}
  )
} : qn(t) ? {
  [`Set(${t.size})`]: [...t.values()].map((s) => vs(s))
} : qe(t) ? vs(t) : Y(t) && !D(t) && !Yn(t) ? String(t) : t, vs = (e, t = "") => {
  var s;
  return (
    // Symbol.description in es2019+ so we need to cast here to pass
    // the lib: es2016 check
    qe(e) ? `Symbol(${(s = e.description) != null ? s : t})` : e
  );
};
/**
* @vue/reactivity v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
let pe;
class Si {
  constructor(t = !1) {
    this.detached = t, this._active = !0, this.effects = [], this.cleanups = [], this._isPaused = !1, this.parent = pe, !t && pe && (this.index = (pe.scopes || (pe.scopes = [])).push(
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
      const s = pe;
      try {
        return pe = this, t();
      } finally {
        pe = s;
      }
    }
  }
  /**
   * This should only be called on non-detached scopes
   * @internal
   */
  on() {
    pe = this;
  }
  /**
   * This should only be called on non-detached scopes
   * @internal
   */
  off() {
    pe = this.parent;
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
function xi() {
  return pe;
}
let K;
const ws = /* @__PURE__ */ new WeakSet();
class sr {
  constructor(t) {
    this.fn = t, this.deps = void 0, this.depsTail = void 0, this.flags = 5, this.next = void 0, this.cleanup = void 0, this.scheduler = void 0, pe && pe.active && pe.effects.push(this);
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
    this.flags |= 2, bn(this), ir(this);
    const t = K, s = we;
    K = this, we = !0;
    try {
      return this.fn();
    } finally {
      or(this), K = t, we = s, this.flags &= -3;
    }
  }
  stop() {
    if (this.flags & 1) {
      for (let t = this.deps; t; t = t.nextDep)
        Xs(t);
      this.deps = this.depsTail = void 0, bn(this), this.onStop && this.onStop(), this.flags &= -2;
    }
  }
  trigger() {
    this.flags & 64 ? ws.add(this) : this.scheduler ? this.scheduler() : this.runIfDirty();
  }
  /**
   * @internal
   */
  runIfDirty() {
    Os(this) && this.run();
  }
  get dirty() {
    return Os(this);
  }
}
let nr = 0, Ct, $t;
function rr(e, t = !1) {
  if (e.flags |= 8, t) {
    e.next = $t, $t = e;
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
function Os(e) {
  for (let t = e.deps; t; t = t.nextDep)
    if (t.dep.version !== t.version || t.dep.computed && (lr(t.dep.computed) || t.dep.version !== t.version))
      return !0;
  return !!e._dirty;
}
function lr(e) {
  if (e.flags & 4 && !(e.flags & 16) || (e.flags &= -17, e.globalVersion === Ot))
    return;
  e.globalVersion = Ot;
  const t = e.dep;
  if (e.flags |= 2, t.version > 0 && !e.isSSR && e.deps && !Os(e)) {
    e.flags &= -3;
    return;
  }
  const s = K, n = we;
  K = e, we = !0;
  try {
    ir(e);
    const r = e.fn(e._value);
    (t.version === 0 || Ke(r, e._value)) && (e._value = r, t.version++);
  } catch (r) {
    throw t.version++, r;
  } finally {
    K = s, we = n, or(e), e.flags &= -3;
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
let we = !0;
const ar = [];
function ze() {
  ar.push(we), we = !1;
}
function Ye() {
  const e = ar.pop();
  we = e === void 0 ? !0 : e;
}
function bn(e) {
  const { cleanup: t } = e;
  if (e.cleanup = void 0, t) {
    const s = K;
    K = void 0;
    try {
      t();
    } finally {
      K = s;
    }
  }
}
let Ot = 0;
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
    if (!K || !we || K === this.computed)
      return;
    let s = this.activeLink;
    if (s === void 0 || s.sub !== K)
      s = this.activeLink = new Ai(K, this), K.deps ? (s.prevDep = K.depsTail, K.depsTail.nextDep = s, K.depsTail = s) : K.deps = K.depsTail = s, cr(s);
    else if (s.version === -1 && (s.version = this.version, s.nextDep)) {
      const n = s.nextDep;
      n.prevDep = s.prevDep, s.prevDep && (s.prevDep.nextDep = n), s.prevDep = K.depsTail, s.nextDep = void 0, K.depsTail.nextDep = s, K.depsTail = s, K.deps === s && (K.deps = n);
    }
    return s;
  }
  trigger(t) {
    this.version++, Ot++, this.notify(t);
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
const Rs = /* @__PURE__ */ new WeakMap(), nt = Symbol(
  ""
), Ps = Symbol(
  ""
), Rt = Symbol(
  ""
);
function se(e, t, s) {
  if (we && K) {
    let n = Rs.get(e);
    n || Rs.set(e, n = /* @__PURE__ */ new Map());
    let r = n.get(s);
    r || (n.set(s, r = new Zs()), r.map = n, r.key = s), r.track();
  }
}
function ke(e, t, s, n, r, i) {
  const o = Rs.get(e);
  if (!o) {
    Ot++;
    return;
  }
  const l = (c) => {
    c && c.trigger();
  };
  if (zs(), t === "clear")
    o.forEach(l);
  else {
    const c = D(e), f = c && Js(s);
    if (c && s === "length") {
      const d = Number(n);
      o.forEach((p, m) => {
        (m === "length" || m === Rt || !qe(m) && m >= d) && l(p);
      });
    } else
      switch ((s !== void 0 || o.has(void 0)) && l(o.get(s)), f && l(o.get(Rt)), t) {
        case "add":
          c ? f && l(o.get("length")) : (l(o.get(nt)), dt(e) && l(o.get(Ps)));
          break;
        case "delete":
          c || (l(o.get(nt)), dt(e) && l(o.get(Ps)));
          break;
        case "set":
          dt(e) && l(o.get(nt));
          break;
      }
  }
  Ys();
}
function at(e) {
  const t = j(e);
  return t === e ? t : (se(t, "iterate", Rt), be(e) ? t : t.map(ne));
}
function us(e) {
  return se(e = j(e), "iterate", Rt), e;
}
const Ci = {
  __proto__: null,
  [Symbol.iterator]() {
    return ys(this, Symbol.iterator, ne);
  },
  concat(...e) {
    return at(this).concat(
      ...e.map((t) => D(t) ? at(t) : t)
    );
  },
  entries() {
    return ys(this, "entries", (e) => (e[1] = ne(e[1]), e));
  },
  every(e, t) {
    return Pe(this, "every", e, t, void 0, arguments);
  },
  filter(e, t) {
    return Pe(this, "filter", e, t, (s) => s.map(ne), arguments);
  },
  find(e, t) {
    return Pe(this, "find", e, t, ne, arguments);
  },
  findIndex(e, t) {
    return Pe(this, "findIndex", e, t, void 0, arguments);
  },
  findLast(e, t) {
    return Pe(this, "findLast", e, t, ne, arguments);
  },
  findLastIndex(e, t) {
    return Pe(this, "findLastIndex", e, t, void 0, arguments);
  },
  // flat, flatMap could benefit from ARRAY_ITERATE but are not straight-forward to implement
  forEach(e, t) {
    return Pe(this, "forEach", e, t, void 0, arguments);
  },
  includes(...e) {
    return Ss(this, "includes", e);
  },
  indexOf(...e) {
    return Ss(this, "indexOf", e);
  },
  join(e) {
    return at(this).join(e);
  },
  // keys() iterator only reads `length`, no optimisation required
  lastIndexOf(...e) {
    return Ss(this, "lastIndexOf", e);
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
    return at(this).toReversed();
  },
  toSorted(e) {
    return at(this).toSorted(e);
  },
  toSpliced(...e) {
    return at(this).toSpliced(...e);
  },
  unshift(...e) {
    return yt(this, "unshift", e);
  },
  values() {
    return ys(this, "values", ne);
  }
};
function ys(e, t, s) {
  const n = us(e), r = n[t]();
  return n !== e && !be(e) && (r._next = r.next, r.next = () => {
    const i = r._next();
    return i.value && (i.value = s(i.value)), i;
  }), r;
}
const $i = Array.prototype;
function Pe(e, t, s, n, r, i) {
  const o = us(e), l = o !== e && !be(e), c = o[t];
  if (c !== $i[t]) {
    const p = c.apply(e, i);
    return l ? ne(p) : p;
  }
  let f = s;
  o !== e && (l ? f = function(p, m) {
    return s.call(this, ne(p), m, e);
  } : s.length > 2 && (f = function(p, m) {
    return s.call(this, p, m, e);
  }));
  const d = c.call(o, f, n);
  return l && r ? r(d) : d;
}
function _n(e, t, s, n) {
  const r = us(e);
  let i = s;
  return r !== e && (be(e) ? s.length > 3 && (i = function(o, l, c) {
    return s.call(this, o, l, c, e);
  }) : i = function(o, l, c) {
    return s.call(this, o, ne(l), c, e);
  }), r[t](i, ...n);
}
function Ss(e, t, s) {
  const n = j(e);
  se(n, "iterate", Rt);
  const r = n[t](...s);
  return (r === -1 || r === !1) && sn(s[0]) ? (s[0] = j(s[0]), n[t](...s)) : r;
}
function yt(e, t, s = []) {
  ze(), zs();
  const n = j(e)[t].apply(e, s);
  return Ys(), Ye(), n;
}
const Ei = /* @__PURE__ */ Ks("__proto__,__v_isRef,__isVue"), ur = new Set(
  /* @__PURE__ */ Object.getOwnPropertyNames(Symbol).filter((e) => e !== "arguments" && e !== "caller").map((e) => Symbol[e]).filter(qe)
);
function Ti(e) {
  qe(e) || (e = String(e));
  const t = j(this);
  return se(t, "has", e), t.hasOwnProperty(e);
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
    const o = D(t);
    if (!r) {
      let c;
      if (o && (c = Ci[s]))
        return c;
      if (s === "hasOwnProperty")
        return Ti;
    }
    const l = Reflect.get(
      t,
      s,
      // if this is a proxy wrapping a ref, return methods using the raw ref
      // as receiver so that we don't have to call `toRaw` on the ref in all
      // its class methods
      re(t) ? t : n
    );
    return (qe(s) ? ur.has(s) : Ei(s)) || (r || se(t, "get", s), i) ? l : re(l) ? o && Js(s) ? l : l.value : Y(l) ? r ? mr(l) : en(l) : l;
  }
}
class dr extends fr {
  constructor(t = !1) {
    super(!1, t);
  }
  set(t, s, n, r) {
    let i = t[s];
    if (!this._isShallow) {
      const c = it(i);
      if (!be(n) && !it(n) && (i = j(i), n = j(n)), !D(t) && re(i) && !re(n))
        return c ? !1 : (i.value = n, !0);
    }
    const o = D(t) && Js(s) ? Number(s) < t.length : B(t, s), l = Reflect.set(
      t,
      s,
      n,
      re(t) ? t : r
    );
    return t === j(r) && (o ? Ke(n, i) && ke(t, "set", s, n) : ke(t, "add", s, n)), l;
  }
  deleteProperty(t, s) {
    const n = B(t, s);
    t[s];
    const r = Reflect.deleteProperty(t, s);
    return r && n && ke(t, "delete", s, void 0), r;
  }
  has(t, s) {
    const n = Reflect.has(t, s);
    return (!qe(s) || !ur.has(s)) && se(t, "has", s), n;
  }
  ownKeys(t) {
    return se(
      t,
      "iterate",
      D(t) ? "length" : nt
    ), Reflect.ownKeys(t);
  }
}
class Mi extends fr {
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
const Oi = /* @__PURE__ */ new dr(), Ri = /* @__PURE__ */ new Mi(), Pi = /* @__PURE__ */ new dr(!0);
const Ds = (e) => e, Vt = (e) => Reflect.getPrototypeOf(e);
function Di(e, t, s) {
  return function(...n) {
    const r = this.__v_raw, i = j(r), o = dt(i), l = e === "entries" || e === Symbol.iterator && o, c = e === "keys" && o, f = r[e](...n), d = s ? Ds : t ? ks : ne;
    return !t && se(
      i,
      "iterate",
      c ? Ps : nt
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
function ki(e, t) {
  const s = {
    get(r) {
      const i = this.__v_raw, o = j(i), l = j(r);
      e || (Ke(r, l) && se(o, "get", r), se(o, "get", l));
      const { has: c } = Vt(o), f = t ? Ds : e ? ks : ne;
      if (c.call(o, r))
        return f(i.get(r));
      if (c.call(o, l))
        return f(i.get(l));
      i !== o && i.get(r);
    },
    get size() {
      const r = this.__v_raw;
      return !e && se(j(r), "iterate", nt), Reflect.get(r, "size", r);
    },
    has(r) {
      const i = this.__v_raw, o = j(i), l = j(r);
      return e || (Ke(r, l) && se(o, "has", r), se(o, "has", l)), r === l ? i.has(r) : i.has(r) || i.has(l);
    },
    forEach(r, i) {
      const o = this, l = o.__v_raw, c = j(l), f = t ? Ds : e ? ks : ne;
      return !e && se(c, "iterate", nt), l.forEach((d, p) => r.call(i, f(d), f(p), o));
    }
  };
  return ie(
    s,
    e ? {
      add: Kt("add"),
      set: Kt("set"),
      delete: Kt("delete"),
      clear: Kt("clear")
    } : {
      add(r) {
        !t && !be(r) && !it(r) && (r = j(r));
        const i = j(this);
        return Vt(i).has.call(i, r) || (i.add(r), ke(i, "add", r, r)), this;
      },
      set(r, i) {
        !t && !be(i) && !it(i) && (i = j(i));
        const o = j(this), { has: l, get: c } = Vt(o);
        let f = l.call(o, r);
        f || (r = j(r), f = l.call(o, r));
        const d = c.call(o, r);
        return o.set(r, i), f ? Ke(i, d) && ke(o, "set", r, i) : ke(o, "add", r, i), this;
      },
      delete(r) {
        const i = j(this), { has: o, get: l } = Vt(i);
        let c = o.call(i, r);
        c || (r = j(r), c = o.call(i, r)), l && l.call(i, r);
        const f = i.delete(r);
        return c && ke(i, "delete", r, void 0), f;
      },
      clear() {
        const r = j(this), i = r.size !== 0, o = r.clear();
        return i && ke(
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
  const s = ki(e, t);
  return (n, r, i) => r === "__v_isReactive" ? !e : r === "__v_isReadonly" ? e : r === "__v_raw" ? n : Reflect.get(
    B(s, r) && r in n ? s : n,
    r,
    i
  );
}
const Fi = {
  get: /* @__PURE__ */ Qs(!1, !1)
}, Ni = {
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
  return it(e) ? e : tn(
    e,
    !1,
    Oi,
    Fi,
    hr
  );
}
function Wi(e) {
  return tn(
    e,
    !1,
    Pi,
    Ni,
    pr
  );
}
function mr(e) {
  return tn(
    e,
    !0,
    Ri,
    Li,
    gr
  );
}
function tn(e, t, s, n, r) {
  if (!Y(e) || e.__v_raw && !(t && e.__v_isReactive))
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
function ht(e) {
  return it(e) ? ht(e.__v_raw) : !!(e && e.__v_isReactive);
}
function it(e) {
  return !!(e && e.__v_isReadonly);
}
function be(e) {
  return !!(e && e.__v_isShallow);
}
function sn(e) {
  return e ? !!e.__v_raw : !1;
}
function j(e) {
  const t = e && e.__v_raw;
  return t ? j(t) : e;
}
function Ui(e) {
  return !B(e, "__v_skip") && Object.isExtensible(e) && Zn(e, "__v_skip", !0), e;
}
const ne = (e) => Y(e) ? en(e) : e, ks = (e) => Y(e) ? mr(e) : e;
function re(e) {
  return e ? e.__v_isRef === !0 : !1;
}
function ut(e) {
  return br(e, !1);
}
function Vi(e) {
  return br(e, !0);
}
function br(e, t) {
  return re(e) ? e : new Ki(e, t);
}
class Ki {
  constructor(t, s) {
    this.dep = new Zs(), this.__v_isRef = !0, this.__v_isShallow = !1, this._rawValue = s ? t : j(t), this._value = s ? t : ne(t), this.__v_isShallow = s;
  }
  get value() {
    return this.dep.track(), this._value;
  }
  set value(t) {
    const s = this._rawValue, n = this.__v_isShallow || be(t) || it(t);
    t = n ? t : j(t), Ke(t, s) && (this._rawValue = t, this._value = n ? t : ne(t), this.dep.trigger());
  }
}
function We(e) {
  return re(e) ? e.value : e;
}
const Gi = {
  get: (e, t, s) => t === "__v_raw" ? e : We(Reflect.get(e, t, s)),
  set: (e, t, s, n) => {
    const r = e[t];
    return re(r) && !re(s) ? (r.value = s, !0) : Reflect.set(e, t, s, n);
  }
};
function _r(e) {
  return ht(e) ? e : new Proxy(e, Gi);
}
class qi {
  constructor(t, s, n) {
    this.fn = t, this.setter = s, this._value = void 0, this.dep = new Zs(this), this.__v_isRef = !0, this.deps = void 0, this.depsTail = void 0, this.flags = 16, this.globalVersion = Ot - 1, this.next = void 0, this.effect = this, this.__v_isReadonly = !s, this.isSSR = n;
  }
  /**
   * @internal
   */
  notify() {
    if (this.flags |= 16, !(this.flags & 8) && // avoid infinite self recursion
    K !== this)
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
  return F(e) ? n = e : (n = e.get, r = e.set), new qi(n, r, s);
}
const Gt = {}, Zt = /* @__PURE__ */ new WeakMap();
let st;
function zi(e, t = !1, s = st) {
  if (s) {
    let n = Zt.get(s);
    n || Zt.set(s, n = []), n.push(e);
  }
}
function Yi(e, t, s = G) {
  const { immediate: n, deep: r, once: i, scheduler: o, augmentJob: l, call: c } = s, f = (M) => r ? M : be(M) || r === !1 || r === 0 ? Ue(M, 1) : Ue(M);
  let d, p, m, S, k = !1, $ = !1;
  if (re(e) ? (p = () => e.value, k = be(e)) : ht(e) ? (p = () => f(e), k = !0) : D(e) ? ($ = !0, k = e.some((M) => ht(M) || be(M)), p = () => e.map((M) => {
    if (re(M))
      return M.value;
    if (ht(M))
      return f(M);
    if (F(M))
      return c ? c(M, 2) : M();
  })) : F(e) ? t ? p = c ? () => c(e, 2) : e : p = () => {
    if (m) {
      ze();
      try {
        m();
      } finally {
        Ye();
      }
    }
    const M = st;
    st = d;
    try {
      return c ? c(e, 3, [S]) : e(S);
    } finally {
      st = M;
    }
  } : p = Oe, t && r) {
    const M = p, ee = r === !0 ? 1 / 0 : r;
    p = () => Ue(M(), ee);
  }
  const J = xi(), H = () => {
    d.stop(), J && J.active && qs(J.effects, d);
  };
  if (i && t) {
    const M = t;
    t = (...ee) => {
      M(...ee), H();
    };
  }
  let X = $ ? new Array(e.length).fill(Gt) : Gt;
  const Z = (M) => {
    if (!(!(d.flags & 1) || !d.dirty && !M))
      if (t) {
        const ee = d.run();
        if (r || k || ($ ? ee.some((Le, Se) => Ke(Le, X[Se])) : Ke(ee, X))) {
          m && m();
          const Le = st;
          st = d;
          try {
            const Se = [
              ee,
              // pass undefined as the old value when it's changed for the first time
              X === Gt ? void 0 : $ && X[0] === Gt ? [] : X,
              S
            ];
            c ? c(t, 3, Se) : (
              // @ts-expect-error
              t(...Se)
            ), X = ee;
          } finally {
            st = Le;
          }
        }
      } else
        d.run();
  };
  return l && l(Z), d = new sr(p), d.scheduler = o ? () => o(Z, !1) : Z, S = (M) => zi(M, !1, d), m = d.onStop = () => {
    const M = Zt.get(d);
    if (M) {
      if (c)
        c(M, 4);
      else
        for (const ee of M) ee();
      Zt.delete(d);
    }
  }, t ? n ? Z(!0) : X = d.run() : o ? o(Z.bind(null, !0), !0) : d.run(), H.pause = d.pause.bind(d), H.resume = d.resume.bind(d), H.stop = H, H;
}
function Ue(e, t = 1 / 0, s) {
  if (t <= 0 || !Y(e) || e.__v_skip || (s = s || /* @__PURE__ */ new Set(), s.has(e)))
    return e;
  if (s.add(e), t--, re(e))
    Ue(e.value, t, s);
  else if (D(e))
    for (let n = 0; n < e.length; n++)
      Ue(e[n], t, s);
  else if (qn(e) || dt(e))
    e.forEach((n) => {
      Ue(n, t, s);
    });
  else if (Yn(e)) {
    for (const n in e)
      Ue(e[n], t, s);
    for (const n of Object.getOwnPropertySymbols(e))
      Object.prototype.propertyIsEnumerable.call(e, n) && Ue(e[n], t, s);
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
function Re(e, t, s, n) {
  if (F(e)) {
    const r = Nt(e, t, s, n);
    return r && Jn(r) && r.catch((i) => {
      fs(i, t, s);
    }), r;
  }
  if (D(e)) {
    const r = [];
    for (let i = 0; i < e.length; i++)
      r.push(Re(e[i], t, s, n));
    return r;
  }
}
function fs(e, t, s, n = !0) {
  const r = t ? t.vnode : null, { errorHandler: i, throwUnhandledErrorInProduction: o } = t && t.appContext.config || G;
  if (t) {
    let l = t.parent;
    const c = t.proxy, f = `https://vuejs.org/error-reference/#runtime-${s}`;
    for (; l; ) {
      const d = l.ec;
      if (d) {
        for (let p = 0; p < d.length; p++)
          if (d[p](e, c, f) === !1)
            return;
      }
      l = l.parent;
    }
    if (i) {
      ze(), Nt(i, null, 10, [
        e,
        c,
        f
      ]), Ye();
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
const ae = [];
let Ee = -1;
const pt = [];
let je = null, ct = 0;
const vr = /* @__PURE__ */ Promise.resolve();
let Qt = null;
function wr(e) {
  const t = Qt || vr;
  return e ? t.then(this ? e.bind(this) : e) : t;
}
function Zi(e) {
  let t = Ee + 1, s = ae.length;
  for (; t < s; ) {
    const n = t + s >>> 1, r = ae[n], i = Pt(r);
    i < e || i === e && r.flags & 2 ? t = n + 1 : s = n;
  }
  return t;
}
function nn(e) {
  if (!(e.flags & 1)) {
    const t = Pt(e), s = ae[ae.length - 1];
    !s || // fast path when the job id is larger than the tail
    !(e.flags & 2) && t >= Pt(s) ? ae.push(e) : ae.splice(Zi(t), 0, e), e.flags |= 1, yr();
  }
}
function yr() {
  Qt || (Qt = vr.then(xr));
}
function Qi(e) {
  D(e) ? pt.push(...e) : je && e.id === -1 ? je.splice(ct + 1, 0, e) : e.flags & 1 || (pt.push(e), e.flags |= 1), yr();
}
function vn(e, t, s = Ee + 1) {
  for (; s < ae.length; s++) {
    const n = ae[s];
    if (n && n.flags & 2) {
      if (e && n.id !== e.uid)
        continue;
      ae.splice(s, 1), s--, n.flags & 4 && (n.flags &= -2), n(), n.flags & 4 || (n.flags &= -2);
    }
  }
}
function Sr(e) {
  if (pt.length) {
    const t = [...new Set(pt)].sort(
      (s, n) => Pt(s) - Pt(n)
    );
    if (pt.length = 0, je) {
      je.push(...t);
      return;
    }
    for (je = t, ct = 0; ct < je.length; ct++) {
      const s = je[ct];
      s.flags & 4 && (s.flags &= -2), s.flags & 8 || s(), s.flags &= -2;
    }
    je = null, ct = 0;
  }
}
const Pt = (e) => e.id == null ? e.flags & 2 ? -1 : 1 / 0 : e.id;
function xr(e) {
  try {
    for (Ee = 0; Ee < ae.length; Ee++) {
      const t = ae[Ee];
      t && !(t.flags & 8) && (t.flags & 4 && (t.flags &= -2), Nt(
        t,
        t.i,
        t.i ? 15 : 14
      ), t.flags & 4 || (t.flags &= -2));
    }
  } finally {
    for (; Ee < ae.length; Ee++) {
      const t = ae[Ee];
      t && (t.flags &= -2);
    }
    Ee = -1, ae.length = 0, Sr(), Qt = null, (ae.length || pt.length) && xr();
  }
}
let Me = null, Ir = null;
function es(e) {
  const t = Me;
  return Me = e, Ir = e && e.type.__scopeId || null, t;
}
function eo(e, t = Me, s) {
  if (!t || e._n)
    return e;
  const n = (...r) => {
    n._d && En(-1);
    const i = es(t);
    let o;
    try {
      o = e(...r);
    } finally {
      es(i), n._d && En(1);
    }
    return o;
  };
  return n._n = !0, n._c = !0, n._d = !0, n;
}
function et(e, t, s, n) {
  const r = e.dirs, i = t && t.dirs;
  for (let o = 0; o < r.length; o++) {
    const l = r[o];
    i && (l.oldValue = i[o].value);
    let c = l.dir[n];
    c && (ze(), Re(c, s, 8, [
      e.el,
      l,
      e,
      t
    ]), Ye());
  }
}
const to = Symbol("_vte"), so = (e) => e.__isTeleport;
function rn(e, t) {
  e.shapeFlag & 6 && e.component ? (e.transition = t, rn(e.component.subTree, t)) : e.shapeFlag & 128 ? (e.ssContent.transition = t.clone(e.ssContent), e.ssFallback.transition = t.clone(e.ssFallback)) : e.transition = t;
}
/*! #__NO_SIDE_EFFECTS__ */
// @__NO_SIDE_EFFECTS__
function Fe(e, t) {
  return F(e) ? (
    // #8236: extend call and options.name access are considered side-effects
    // by Rollup, so we have to wrap it in a pure-annotated IIFE.
    ie({ name: e.name }, t, { setup: e })
  ) : e;
}
function Ar(e) {
  e.ids = [e.ids[0] + e.ids[2]++ + "-", 0, 0];
}
function ts(e, t, s, n, r = !1) {
  if (D(e)) {
    e.forEach(
      (k, $) => ts(
        k,
        t && (D(t) ? t[$] : t),
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
  const i = n.shapeFlag & 4 ? cn(n.component) : n.el, o = r ? null : i, { i: l, r: c } = e, f = t && t.r, d = l.refs === G ? l.refs = {} : l.refs, p = l.setupState, m = j(p), S = p === G ? () => !1 : (k) => B(m, k);
  if (f != null && f !== c && (Q(f) ? (d[f] = null, S(f) && (p[f] = null)) : re(f) && (f.value = null)), F(c))
    Nt(c, l, 12, [o, d]);
  else {
    const k = Q(c), $ = re(c);
    if (k || $) {
      const J = () => {
        if (e.f) {
          const H = k ? S(c) ? p[c] : d[c] : c.value;
          r ? D(H) && qs(H, i) : D(H) ? H.includes(i) || H.push(i) : k ? (d[c] = [i], S(c) && (p[c] = d[c])) : (c.value = [i], e.k && (d[e.k] = c.value));
        } else k ? (d[c] = o, S(c) && (p[c] = o)) : $ && (c.value = o, e.k && (d[e.k] = o));
      };
      o ? (J.id = -1, he(J, s)) : J();
    }
  }
}
cs().requestIdleCallback;
cs().cancelIdleCallback;
const Et = (e) => !!e.type.__asyncLoader, Cr = (e) => e.type.__isKeepAlive;
function no(e, t) {
  $r(e, "a", t);
}
function ro(e, t) {
  $r(e, "da", t);
}
function $r(e, t, s = ce) {
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
      ze();
      const l = Lt(s), c = Re(t, s, e, o);
      return l(), Ye(), c;
    });
    return n ? r.unshift(i) : r.push(i), i;
  }
}
const Ne = (e) => (t, s = ce) => {
  (!kt || e === "sp") && ds(e, (...n) => t(...n), s);
}, oo = Ne("bm"), Er = Ne("m"), lo = Ne(
  "bu"
), ao = Ne("u"), on = Ne(
  "bum"
), Tr = Ne("um"), co = Ne(
  "sp"
), uo = Ne("rtg"), fo = Ne("rtc");
function Mr(e, t = ce) {
  ds("ec", e, t);
}
const ho = Symbol.for("v-ndc");
function _e(e, t, s, n) {
  let r;
  const i = s, o = D(e);
  if (o || Q(e)) {
    const l = o && ht(e);
    let c = !1;
    l && (c = !be(e), e = us(e)), r = new Array(e.length);
    for (let f = 0, d = e.length; f < d; f++)
      r[f] = t(
        c ? ne(e[f]) : e[f],
        f,
        void 0,
        i
      );
  } else if (typeof e == "number") {
    r = new Array(e);
    for (let l = 0; l < e; l++)
      r[l] = t(l + 1, l, void 0, i);
  } else if (Y(e))
    if (e[Symbol.iterator])
      r = Array.from(
        e,
        (l, c) => t(l, c, void 0, i)
      );
    else {
      const l = Object.keys(e);
      r = new Array(l.length);
      for (let c = 0, f = l.length; c < f; c++) {
        const d = l[c];
        r[c] = t(e[d], d, c, i);
      }
    }
  else
    r = [];
  return r;
}
const Fs = (e) => e ? Zr(e) ? cn(e) : Fs(e.parent) : null, Tt = (
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
    $parent: (e) => Fs(e.parent),
    $root: (e) => Fs(e.root),
    $host: (e) => e.ce,
    $emit: (e) => e.emit,
    $options: (e) => Rr(e),
    $forceUpdate: (e) => e.f || (e.f = () => {
      nn(e.update);
    }),
    $nextTick: (e) => e.n || (e.n = wr.bind(e.proxy)),
    $watch: (e) => ko.bind(e)
  })
), xs = (e, t) => e !== G && !e.__isScriptSetup && B(e, t), po = {
  get({ _: e }, t) {
    if (t === "__v_skip")
      return !0;
    const { ctx: s, setupState: n, data: r, props: i, accessCache: o, type: l, appContext: c } = e;
    let f;
    if (t[0] !== "$") {
      const S = o[t];
      if (S !== void 0)
        switch (S) {
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
        if (r !== G && B(r, t))
          return o[t] = 2, r[t];
        if (
          // only cache other properties when instance has declared (thus stable)
          // props
          (f = e.propsOptions[0]) && B(f, t)
        )
          return o[t] = 3, i[t];
        if (s !== G && B(s, t))
          return o[t] = 4, s[t];
        Ns && (o[t] = 0);
      }
    }
    const d = Tt[t];
    let p, m;
    if (d)
      return t === "$attrs" && se(e.attrs, "get", ""), d(e);
    if (
      // css module (injected by vue-loader)
      (p = l.__cssModules) && (p = p[t])
    )
      return p;
    if (s !== G && B(s, t))
      return o[t] = 4, s[t];
    if (
      // global properties
      m = c.config.globalProperties, B(m, t)
    )
      return m[t];
  },
  set({ _: e }, t, s) {
    const { data: n, setupState: r, ctx: i } = e;
    return xs(r, t) ? (r[t] = s, !0) : n !== G && B(n, t) ? (n[t] = s, !0) : B(e.props, t) || t[0] === "$" && t.slice(1) in e ? !1 : (i[t] = s, !0);
  },
  has({
    _: { data: e, setupState: t, accessCache: s, ctx: n, appContext: r, propsOptions: i }
  }, o) {
    let l;
    return !!s[o] || e !== G && B(e, o) || xs(t, o) || (l = i[0]) && B(l, o) || B(n, o) || B(Tt, o) || B(r.config.globalProperties, o);
  },
  defineProperty(e, t, s) {
    return s.get != null ? e._.accessCache[t] = 0 : B(s, "value") && this.set(e, t, s.value, null), Reflect.defineProperty(e, t, s);
  }
};
function wn(e) {
  return D(e) ? e.reduce(
    (t, s) => (t[s] = null, t),
    {}
  ) : e;
}
let Ns = !0;
function go(e) {
  const t = Rr(e), s = e.proxy, n = e.ctx;
  Ns = !1, t.beforeCreate && yn(t.beforeCreate, e, "bc");
  const {
    // state
    data: r,
    computed: i,
    methods: o,
    watch: l,
    provide: c,
    inject: f,
    // lifecycle
    created: d,
    beforeMount: p,
    mounted: m,
    beforeUpdate: S,
    updated: k,
    activated: $,
    deactivated: J,
    beforeDestroy: H,
    beforeUnmount: X,
    destroyed: Z,
    unmounted: M,
    render: ee,
    renderTracked: Le,
    renderTriggered: Se,
    errorCaptured: He,
    serverPrefetch: Ht,
    // public API
    expose: Xe,
    inheritAttrs: bt,
    // assets
    components: jt,
    directives: Bt,
    filters: gs
  } = t;
  if (f && mo(f, n, null), o)
    for (const z in o) {
      const U = o[z];
      F(U) && (n[z] = U.bind(s));
    }
  if (r) {
    const z = r.call(s, s);
    Y(z) && (e.data = en(z));
  }
  if (Ns = !0, i)
    for (const z in i) {
      const U = i[z], Ze = F(U) ? U.bind(s, s) : F(U.get) ? U.get.bind(s, s) : Oe, Wt = !F(U) && F(U.set) ? U.set.bind(s) : Oe, Qe = rt({
        get: Ze,
        set: Wt
      });
      Object.defineProperty(n, z, {
        enumerable: !0,
        configurable: !0,
        get: () => Qe.value,
        set: (xe) => Qe.value = xe
      });
    }
  if (l)
    for (const z in l)
      Or(l[z], n, s, z);
  if (c) {
    const z = F(c) ? c.call(s) : c;
    Reflect.ownKeys(z).forEach((U) => {
      So(U, z[U]);
    });
  }
  d && yn(d, e, "c");
  function oe(z, U) {
    D(U) ? U.forEach((Ze) => z(Ze.bind(s))) : U && z(U.bind(s));
  }
  if (oe(oo, p), oe(Er, m), oe(lo, S), oe(ao, k), oe(no, $), oe(ro, J), oe(Mr, He), oe(fo, Le), oe(uo, Se), oe(on, X), oe(Tr, M), oe(co, Ht), D(Xe))
    if (Xe.length) {
      const z = e.exposed || (e.exposed = {});
      Xe.forEach((U) => {
        Object.defineProperty(z, U, {
          get: () => s[U],
          set: (Ze) => s[U] = Ze
        });
      });
    } else e.exposed || (e.exposed = {});
  ee && e.render === Oe && (e.render = ee), bt != null && (e.inheritAttrs = bt), jt && (e.components = jt), Bt && (e.directives = Bt), Ht && Ar(e);
}
function mo(e, t, s = Oe) {
  D(e) && (e = Ls(e));
  for (const n in e) {
    const r = e[n];
    let i;
    Y(r) ? "default" in r ? i = Jt(
      r.from || n,
      r.default,
      !0
    ) : i = Jt(r.from || n) : i = Jt(r), re(i) ? Object.defineProperty(t, n, {
      enumerable: !0,
      configurable: !0,
      get: () => i.value,
      set: (o) => i.value = o
    }) : t[n] = i;
  }
}
function yn(e, t, s) {
  Re(
    D(e) ? e.map((n) => n.bind(t.proxy)) : e.bind(t.proxy),
    t,
    s
  );
}
function Or(e, t, s, n) {
  let r = n.includes(".") ? Gr(s, n) : () => s[n];
  if (Q(e)) {
    const i = t[e];
    F(i) && zt(r, i);
  } else if (F(e))
    zt(r, e.bind(s));
  else if (Y(e))
    if (D(e))
      e.forEach((i) => Or(i, t, s, n));
    else {
      const i = F(e.handler) ? e.handler.bind(s) : t[e.handler];
      F(i) && zt(r, i, e);
    }
}
function Rr(e) {
  const t = e.type, { mixins: s, extends: n } = t, {
    mixins: r,
    optionsCache: i,
    config: { optionMergeStrategies: o }
  } = e.appContext, l = i.get(t);
  let c;
  return l ? c = l : !r.length && !s && !n ? c = t : (c = {}, r.length && r.forEach(
    (f) => ss(c, f, o, !0)
  ), ss(c, t, o)), Y(t) && i.set(t, c), c;
}
function ss(e, t, s, n = !1) {
  const { mixins: r, extends: i } = t;
  i && ss(e, i, s, !0), r && r.forEach(
    (o) => ss(e, o, s, !0)
  );
  for (const o in t)
    if (!(n && o === "expose")) {
      const l = bo[o] || s && s[o];
      e[o] = l ? l(e[o], t[o]) : t[o];
    }
  return e;
}
const bo = {
  data: Sn,
  props: xn,
  emits: xn,
  // objects
  methods: xt,
  computed: xt,
  // lifecycle
  beforeCreate: le,
  created: le,
  beforeMount: le,
  mounted: le,
  beforeUpdate: le,
  updated: le,
  beforeDestroy: le,
  beforeUnmount: le,
  destroyed: le,
  unmounted: le,
  activated: le,
  deactivated: le,
  errorCaptured: le,
  serverPrefetch: le,
  // assets
  components: xt,
  directives: xt,
  // watch
  watch: vo,
  // provide / inject
  provide: Sn,
  inject: _o
};
function Sn(e, t) {
  return t ? e ? function() {
    return ie(
      F(e) ? e.call(this, this) : e,
      F(t) ? t.call(this, this) : t
    );
  } : t : e;
}
function _o(e, t) {
  return xt(Ls(e), Ls(t));
}
function Ls(e) {
  if (D(e)) {
    const t = {};
    for (let s = 0; s < e.length; s++)
      t[e[s]] = e[s];
    return t;
  }
  return e;
}
function le(e, t) {
  return e ? [...new Set([].concat(e, t))] : t;
}
function xt(e, t) {
  return e ? ie(/* @__PURE__ */ Object.create(null), e, t) : t;
}
function xn(e, t) {
  return e ? D(e) && D(t) ? [.../* @__PURE__ */ new Set([...e, ...t])] : ie(
    /* @__PURE__ */ Object.create(null),
    wn(e),
    wn(t ?? {})
  ) : t;
}
function vo(e, t) {
  if (!e) return t;
  if (!t) return e;
  const s = ie(/* @__PURE__ */ Object.create(null), e);
  for (const n in t)
    s[n] = le(e[n], t[n]);
  return s;
}
function Pr() {
  return {
    app: null,
    config: {
      isNativeTag: ui,
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
    F(n) || (n = ie({}, n)), r != null && !Y(r) && (r = null);
    const i = Pr(), o = /* @__PURE__ */ new WeakSet(), l = [];
    let c = !1;
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
        return o.has(d) || (d && F(d.install) ? (o.add(d), d.install(f, ...p)) : F(d) && (o.add(d), d(f, ...p))), f;
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
        if (!c) {
          const S = f._ceVNode || ye(n, r);
          return S.appContext = i, m === !0 ? m = "svg" : m === !1 && (m = void 0), e(S, d, m), c = !0, f._container = d, d.__vue_app__ = f, cn(S.component);
        }
      },
      onUnmount(d) {
        l.push(d);
      },
      unmount() {
        c && (Re(
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
function So(e, t) {
  if (ce) {
    let s = ce.provides;
    const n = ce.parent && ce.parent.provides;
    n === s && (s = ce.provides = Object.create(n)), s[e] = t;
  }
}
function Jt(e, t, s = !1) {
  const n = ce || Me;
  if (n || gt) {
    const r = gt ? gt._context.provides : n ? n.parent == null ? n.vnode.appContext && n.vnode.appContext.provides : n.parent.provides : void 0;
    if (r && e in r)
      return r[e];
    if (arguments.length > 1)
      return s && F(t) ? t.call(n && n.proxy) : t;
  }
}
const Dr = {}, kr = () => Object.create(Dr), Fr = (e) => Object.getPrototypeOf(e) === Dr;
function xo(e, t, s, n = !1) {
  const r = {}, i = kr();
  e.propsDefaults = /* @__PURE__ */ Object.create(null), Nr(e, t, r, i);
  for (const o in e.propsOptions[0])
    o in r || (r[o] = void 0);
  s ? e.props = n ? r : Wi(r) : e.type.props ? e.props = r : e.props = i, e.attrs = i;
}
function Io(e, t, s, n) {
  const {
    props: r,
    attrs: i,
    vnode: { patchFlag: o }
  } = e, l = j(r), [c] = e.propsOptions;
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
        const S = t[m];
        if (c)
          if (B(i, m))
            S !== i[m] && (i[m] = S, f = !0);
          else {
            const k = Ge(m);
            r[k] = Hs(
              c,
              l,
              k,
              S,
              e,
              !1
            );
          }
        else
          S !== i[m] && (i[m] = S, f = !0);
      }
    }
  } else {
    Nr(e, t, r, i) && (f = !0);
    let d;
    for (const p in l)
      (!t || // for camelCase
      !B(t, p) && // it's possible the original props was passed in as kebab-case
      // and converted to camelCase (#955)
      ((d = lt(p)) === p || !B(t, d))) && (c ? s && // for camelCase
      (s[p] !== void 0 || // for kebab-case
      s[d] !== void 0) && (r[p] = Hs(
        c,
        l,
        p,
        void 0,
        e,
        !0
      )) : delete r[p]);
    if (i !== l)
      for (const p in i)
        (!t || !B(t, p)) && (delete i[p], f = !0);
  }
  f && ke(e.attrs, "set", "");
}
function Nr(e, t, s, n) {
  const [r, i] = e.propsOptions;
  let o = !1, l;
  if (t)
    for (let c in t) {
      if (At(c))
        continue;
      const f = t[c];
      let d;
      r && B(r, d = Ge(c)) ? !i || !i.includes(d) ? s[d] = f : (l || (l = {}))[d] = f : hs(e.emitsOptions, c) || (!(c in n) || f !== n[c]) && (n[c] = f, o = !0);
    }
  if (i) {
    const c = j(s), f = l || G;
    for (let d = 0; d < i.length; d++) {
      const p = i[d];
      s[p] = Hs(
        r,
        c,
        p,
        f[p],
        e,
        !B(f, p)
      );
    }
  }
  return o;
}
function Hs(e, t, s, n, r, i) {
  const o = e[s];
  if (o != null) {
    const l = B(o, "default");
    if (l && n === void 0) {
      const c = o.default;
      if (o.type !== Function && !o.skipFactory && F(c)) {
        const { propsDefaults: f } = r;
        if (s in f)
          n = f[s];
        else {
          const d = Lt(r);
          n = f[s] = c.call(
            null,
            t
          ), d();
        }
      } else
        n = c;
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
const Ao = /* @__PURE__ */ new WeakMap();
function Lr(e, t, s = !1) {
  const n = s ? Ao : t.propsCache, r = n.get(e);
  if (r)
    return r;
  const i = e.props, o = {}, l = [];
  let c = !1;
  if (!F(e)) {
    const d = (p) => {
      c = !0;
      const [m, S] = Lr(p, t, !0);
      ie(o, m), S && l.push(...S);
    };
    !s && t.mixins.length && t.mixins.forEach(d), e.extends && d(e.extends), e.mixins && e.mixins.forEach(d);
  }
  if (!i && !c)
    return Y(e) && n.set(e, ft), ft;
  if (D(i))
    for (let d = 0; d < i.length; d++) {
      const p = Ge(i[d]);
      In(p) && (o[p] = G);
    }
  else if (i)
    for (const d in i) {
      const p = Ge(d);
      if (In(p)) {
        const m = i[d], S = o[p] = D(m) || F(m) ? { type: m } : ie({}, m), k = S.type;
        let $ = !1, J = !0;
        if (D(k))
          for (let H = 0; H < k.length; ++H) {
            const X = k[H], Z = F(X) && X.name;
            if (Z === "Boolean") {
              $ = !0;
              break;
            } else Z === "String" && (J = !1);
          }
        else
          $ = F(k) && k.name === "Boolean";
        S[
          0
          /* shouldCast */
        ] = $, S[
          1
          /* shouldCastTrue */
        ] = J, ($ || B(S, "default")) && l.push(p);
      }
    }
  const f = [o, l];
  return Y(e) && n.set(e, f), f;
}
function In(e) {
  return e[0] !== "$" && !At(e);
}
const Hr = (e) => e[0] === "_" || e === "$stable", ln = (e) => D(e) ? e.map(Te) : [Te(e)], Co = (e, t, s) => {
  if (t._n)
    return t;
  const n = eo((...r) => ln(t(...r)), s);
  return n._c = !1, n;
}, jr = (e, t, s) => {
  const n = e._ctx;
  for (const r in e) {
    if (Hr(r)) continue;
    const i = e[r];
    if (F(i))
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
}, $o = (e, t, s) => {
  const n = e.slots = kr();
  if (e.vnode.shapeFlag & 32) {
    const r = t._;
    r ? (Wr(n, t, s), s && Zn(n, "_", r, !0)) : jr(t, n);
  } else t && Br(e, t);
}, Eo = (e, t, s) => {
  const { vnode: n, slots: r } = e;
  let i = !0, o = G;
  if (n.shapeFlag & 32) {
    const l = t._;
    l ? s && l === 1 ? i = !1 : Wr(r, t, s) : (i = !t.$stable, jr(t, r)), o = t;
  } else t && (Br(e, t), o = { default: 1 });
  if (i)
    for (const l in r)
      !Hr(l) && o[l] == null && delete r[l];
}, he = Wo;
function To(e) {
  return Mo(e);
}
function Mo(e, t) {
  const s = cs();
  s.__VUE__ = !0;
  const {
    insert: n,
    remove: r,
    patchProp: i,
    createElement: o,
    createText: l,
    createComment: c,
    setText: f,
    setElementText: d,
    parentNode: p,
    nextSibling: m,
    setScopeId: S = Oe,
    insertStaticContent: k
  } = e, $ = (a, u, h, _ = null, g = null, b = null, x = void 0, y = null, w = !!u.dynamicChildren) => {
    if (a === u)
      return;
    a && !St(a, u) && (_ = Ut(a), xe(a, g, b, !0), a = null), u.patchFlag === -2 && (w = !1, u.dynamicChildren = null);
    const { type: v, ref: T, shapeFlag: I } = u;
    switch (v) {
      case ps:
        J(a, u, h, _);
        break;
      case ot:
        H(a, u, h, _);
        break;
      case As:
        a == null && X(u, h, _, x);
        break;
      case q:
        jt(
          a,
          u,
          h,
          _,
          g,
          b,
          x,
          y,
          w
        );
        break;
      default:
        I & 1 ? ee(
          a,
          u,
          h,
          _,
          g,
          b,
          x,
          y,
          w
        ) : I & 6 ? Bt(
          a,
          u,
          h,
          _,
          g,
          b,
          x,
          y,
          w
        ) : (I & 64 || I & 128) && v.process(
          a,
          u,
          h,
          _,
          g,
          b,
          x,
          y,
          w,
          vt
        );
    }
    T != null && g && ts(T, a && a.ref, b, u || a, !u);
  }, J = (a, u, h, _) => {
    if (a == null)
      n(
        u.el = l(u.children),
        h,
        _
      );
    else {
      const g = u.el = a.el;
      u.children !== a.children && f(g, u.children);
    }
  }, H = (a, u, h, _) => {
    a == null ? n(
      u.el = c(u.children || ""),
      h,
      _
    ) : u.el = a.el;
  }, X = (a, u, h, _) => {
    [a.el, a.anchor] = k(
      a.children,
      u,
      h,
      _,
      a.el,
      a.anchor
    );
  }, Z = ({ el: a, anchor: u }, h, _) => {
    let g;
    for (; a && a !== u; )
      g = m(a), n(a, h, _), a = g;
    n(u, h, _);
  }, M = ({ el: a, anchor: u }) => {
    let h;
    for (; a && a !== u; )
      h = m(a), r(a), a = h;
    r(u);
  }, ee = (a, u, h, _, g, b, x, y, w) => {
    u.type === "svg" ? x = "svg" : u.type === "math" && (x = "mathml"), a == null ? Le(
      u,
      h,
      _,
      g,
      b,
      x,
      y,
      w
    ) : Ht(
      a,
      u,
      g,
      b,
      x,
      y,
      w
    );
  }, Le = (a, u, h, _, g, b, x, y) => {
    let w, v;
    const { props: T, shapeFlag: I, transition: C, dirs: O } = a;
    if (w = a.el = o(
      a.type,
      b,
      T && T.is,
      T
    ), I & 8 ? d(w, a.children) : I & 16 && He(
      a.children,
      w,
      null,
      _,
      g,
      Is(a, b),
      x,
      y
    ), O && et(a, null, _, "created"), Se(w, a, a.scopeId, x, _), T) {
      for (const V in T)
        V !== "value" && !At(V) && i(w, V, null, T[V], b, _);
      "value" in T && i(w, "value", null, T.value, b), (v = T.onVnodeBeforeMount) && $e(v, _, a);
    }
    O && et(a, null, _, "beforeMount");
    const L = Oo(g, C);
    L && C.beforeEnter(w), n(w, u, h), ((v = T && T.onVnodeMounted) || L || O) && he(() => {
      v && $e(v, _, a), L && C.enter(w), O && et(a, null, _, "mounted");
    }, g);
  }, Se = (a, u, h, _, g) => {
    if (h && S(a, h), _)
      for (let b = 0; b < _.length; b++)
        S(a, _[b]);
    if (g) {
      let b = g.subTree;
      if (u === b || Jr(b.type) && (b.ssContent === u || b.ssFallback === u)) {
        const x = g.vnode;
        Se(
          a,
          x,
          x.scopeId,
          x.slotScopeIds,
          g.parent
        );
      }
    }
  }, He = (a, u, h, _, g, b, x, y, w = 0) => {
    for (let v = w; v < a.length; v++) {
      const T = a[v] = y ? Be(a[v]) : Te(a[v]);
      $(
        null,
        T,
        u,
        h,
        _,
        g,
        b,
        x,
        y
      );
    }
  }, Ht = (a, u, h, _, g, b, x) => {
    const y = u.el = a.el;
    let { patchFlag: w, dynamicChildren: v, dirs: T } = u;
    w |= a.patchFlag & 16;
    const I = a.props || G, C = u.props || G;
    let O;
    if (h && tt(h, !1), (O = C.onVnodeBeforeUpdate) && $e(O, h, u, a), T && et(u, a, h, "beforeUpdate"), h && tt(h, !0), (I.innerHTML && C.innerHTML == null || I.textContent && C.textContent == null) && d(y, ""), v ? Xe(
      a.dynamicChildren,
      v,
      y,
      h,
      _,
      Is(u, g),
      b
    ) : x || U(
      a,
      u,
      y,
      null,
      h,
      _,
      Is(u, g),
      b,
      !1
    ), w > 0) {
      if (w & 16)
        bt(y, I, C, h, g);
      else if (w & 2 && I.class !== C.class && i(y, "class", null, C.class, g), w & 4 && i(y, "style", I.style, C.style, g), w & 8) {
        const L = u.dynamicProps;
        for (let V = 0; V < L.length; V++) {
          const W = L[V], fe = I[W], ue = C[W];
          (ue !== fe || W === "value") && i(y, W, fe, ue, g, h);
        }
      }
      w & 1 && a.children !== u.children && d(y, u.children);
    } else !x && v == null && bt(y, I, C, h, g);
    ((O = C.onVnodeUpdated) || T) && he(() => {
      O && $e(O, h, u, a), T && et(u, a, h, "updated");
    }, _);
  }, Xe = (a, u, h, _, g, b, x) => {
    for (let y = 0; y < u.length; y++) {
      const w = a[y], v = u[y], T = (
        // oldVNode may be an errored async setup() component inside Suspense
        // which will not have a mounted element
        w.el && // - In the case of a Fragment, we need to provide the actual parent
        // of the Fragment itself so it can move its children.
        (w.type === q || // - In the case of different nodes, there is going to be a replacement
        // which also requires the correct parent container
        !St(w, v) || // - In the case of a component, it could contain anything.
        w.shapeFlag & 70) ? p(w.el) : (
          // In other cases, the parent container is not actually used so we
          // just pass the block element here to avoid a DOM parentNode call.
          h
        )
      );
      $(
        w,
        v,
        T,
        null,
        _,
        g,
        b,
        x,
        !0
      );
    }
  }, bt = (a, u, h, _, g) => {
    if (u !== h) {
      if (u !== G)
        for (const b in u)
          !At(b) && !(b in h) && i(
            a,
            b,
            u[b],
            null,
            g,
            _
          );
      for (const b in h) {
        if (At(b)) continue;
        const x = h[b], y = u[b];
        x !== y && b !== "value" && i(a, b, y, x, g, _);
      }
      "value" in h && i(a, "value", u.value, h.value, g);
    }
  }, jt = (a, u, h, _, g, b, x, y, w) => {
    const v = u.el = a ? a.el : l(""), T = u.anchor = a ? a.anchor : l("");
    let { patchFlag: I, dynamicChildren: C, slotScopeIds: O } = u;
    O && (y = y ? y.concat(O) : O), a == null ? (n(v, h, _), n(T, h, _), He(
      // #10007
      // such fragment like `<></>` will be compiled into
      // a fragment which doesn't have a children.
      // In this case fallback to an empty array
      u.children || [],
      h,
      T,
      g,
      b,
      x,
      y,
      w
    )) : I > 0 && I & 64 && C && // #2715 the previous fragment could've been a BAILed one as a result
    // of renderSlot() with no valid children
    a.dynamicChildren ? (Xe(
      a.dynamicChildren,
      C,
      h,
      g,
      b,
      x,
      y
    ), // #2080 if the stable fragment has a key, it's a <template v-for> that may
    //  get moved around. Make sure all root level vnodes inherit el.
    // #2134 or if it's a component root, it may also get moved around
    // as the component is being moved.
    (u.key != null || g && u === g.subTree) && Ur(
      a,
      u,
      !0
      /* shallow */
    )) : U(
      a,
      u,
      h,
      T,
      g,
      b,
      x,
      y,
      w
    );
  }, Bt = (a, u, h, _, g, b, x, y, w) => {
    u.slotScopeIds = y, a == null ? u.shapeFlag & 512 ? g.ctx.activate(
      u,
      h,
      _,
      x,
      w
    ) : gs(
      u,
      h,
      _,
      g,
      b,
      x,
      w
    ) : fn(a, u, w);
  }, gs = (a, u, h, _, g, b, x) => {
    const y = a.component = zo(
      a,
      _,
      g
    );
    if (Cr(a) && (y.ctx.renderer = vt), Yo(y, !1, x), y.asyncDep) {
      if (g && g.registerDep(y, oe, x), !a.el) {
        const w = y.subTree = ye(ot);
        H(null, w, u, h);
      }
    } else
      oe(
        y,
        a,
        u,
        h,
        g,
        b,
        x
      );
  }, fn = (a, u, h) => {
    const _ = u.component = a.component;
    if (jo(a, u, h))
      if (_.asyncDep && !_.asyncResolved) {
        z(_, u, h);
        return;
      } else
        _.next = u, _.update();
    else
      u.el = a.el, _.vnode = u;
  }, oe = (a, u, h, _, g, b, x) => {
    const y = () => {
      if (a.isMounted) {
        let { next: I, bu: C, u: O, parent: L, vnode: V } = a;
        {
          const Ae = Vr(a);
          if (Ae) {
            I && (I.el = V.el, z(a, I, x)), Ae.asyncDep.then(() => {
              a.isUnmounted || y();
            });
            return;
          }
        }
        let W = I, fe;
        tt(a, !1), I ? (I.el = V.el, z(a, I, x)) : I = V, C && _s(C), (fe = I.props && I.props.onVnodeBeforeUpdate) && $e(fe, L, I, V), tt(a, !0);
        const ue = Cn(a), Ie = a.subTree;
        a.subTree = ue, $(
          Ie,
          ue,
          // parent may have changed if it's in a teleport
          p(Ie.el),
          // anchor may have changed if it's in a fragment
          Ut(Ie),
          a,
          g,
          b
        ), I.el = ue.el, W === null && Bo(a, ue.el), O && he(O, g), (fe = I.props && I.props.onVnodeUpdated) && he(
          () => $e(fe, L, I, V),
          g
        );
      } else {
        let I;
        const { el: C, props: O } = u, { bm: L, m: V, parent: W, root: fe, type: ue } = a, Ie = Et(u);
        tt(a, !1), L && _s(L), !Ie && (I = O && O.onVnodeBeforeMount) && $e(I, W, u), tt(a, !0);
        {
          fe.ce && fe.ce._injectChildStyle(ue);
          const Ae = a.subTree = Cn(a);
          $(
            null,
            Ae,
            h,
            _,
            a,
            g,
            b
          ), u.el = Ae.el;
        }
        if (V && he(V, g), !Ie && (I = O && O.onVnodeMounted)) {
          const Ae = u;
          he(
            () => $e(I, W, Ae),
            g
          );
        }
        (u.shapeFlag & 256 || W && Et(W.vnode) && W.vnode.shapeFlag & 256) && a.a && he(a.a, g), a.isMounted = !0, u = h = _ = null;
      }
    };
    a.scope.on();
    const w = a.effect = new sr(y);
    a.scope.off();
    const v = a.update = w.run.bind(w), T = a.job = w.runIfDirty.bind(w);
    T.i = a, T.id = a.uid, w.scheduler = () => nn(T), tt(a, !0), v();
  }, z = (a, u, h) => {
    u.component = a;
    const _ = a.vnode.props;
    a.vnode = u, a.next = null, Io(a, u.props, _, h), Eo(a, u.children, h), ze(), vn(a), Ye();
  }, U = (a, u, h, _, g, b, x, y, w = !1) => {
    const v = a && a.children, T = a ? a.shapeFlag : 0, I = u.children, { patchFlag: C, shapeFlag: O } = u;
    if (C > 0) {
      if (C & 128) {
        Wt(
          v,
          I,
          h,
          _,
          g,
          b,
          x,
          y,
          w
        );
        return;
      } else if (C & 256) {
        Ze(
          v,
          I,
          h,
          _,
          g,
          b,
          x,
          y,
          w
        );
        return;
      }
    }
    O & 8 ? (T & 16 && _t(v, g, b), I !== v && d(h, I)) : T & 16 ? O & 16 ? Wt(
      v,
      I,
      h,
      _,
      g,
      b,
      x,
      y,
      w
    ) : _t(v, g, b, !0) : (T & 8 && d(h, ""), O & 16 && He(
      I,
      h,
      _,
      g,
      b,
      x,
      y,
      w
    ));
  }, Ze = (a, u, h, _, g, b, x, y, w) => {
    a = a || ft, u = u || ft;
    const v = a.length, T = u.length, I = Math.min(v, T);
    let C;
    for (C = 0; C < I; C++) {
      const O = u[C] = w ? Be(u[C]) : Te(u[C]);
      $(
        a[C],
        O,
        h,
        null,
        g,
        b,
        x,
        y,
        w
      );
    }
    v > T ? _t(
      a,
      g,
      b,
      !0,
      !1,
      I
    ) : He(
      u,
      h,
      _,
      g,
      b,
      x,
      y,
      w,
      I
    );
  }, Wt = (a, u, h, _, g, b, x, y, w) => {
    let v = 0;
    const T = u.length;
    let I = a.length - 1, C = T - 1;
    for (; v <= I && v <= C; ) {
      const O = a[v], L = u[v] = w ? Be(u[v]) : Te(u[v]);
      if (St(O, L))
        $(
          O,
          L,
          h,
          null,
          g,
          b,
          x,
          y,
          w
        );
      else
        break;
      v++;
    }
    for (; v <= I && v <= C; ) {
      const O = a[I], L = u[C] = w ? Be(u[C]) : Te(u[C]);
      if (St(O, L))
        $(
          O,
          L,
          h,
          null,
          g,
          b,
          x,
          y,
          w
        );
      else
        break;
      I--, C--;
    }
    if (v > I) {
      if (v <= C) {
        const O = C + 1, L = O < T ? u[O].el : _;
        for (; v <= C; )
          $(
            null,
            u[v] = w ? Be(u[v]) : Te(u[v]),
            h,
            L,
            g,
            b,
            x,
            y,
            w
          ), v++;
      }
    } else if (v > C)
      for (; v <= I; )
        xe(a[v], g, b, !0), v++;
    else {
      const O = v, L = v, V = /* @__PURE__ */ new Map();
      for (v = L; v <= C; v++) {
        const de = u[v] = w ? Be(u[v]) : Te(u[v]);
        de.key != null && V.set(de.key, v);
      }
      let W, fe = 0;
      const ue = C - L + 1;
      let Ie = !1, Ae = 0;
      const wt = new Array(ue);
      for (v = 0; v < ue; v++) wt[v] = 0;
      for (v = O; v <= I; v++) {
        const de = a[v];
        if (fe >= ue) {
          xe(de, g, b, !0);
          continue;
        }
        let Ce;
        if (de.key != null)
          Ce = V.get(de.key);
        else
          for (W = L; W <= C; W++)
            if (wt[W - L] === 0 && St(de, u[W])) {
              Ce = W;
              break;
            }
        Ce === void 0 ? xe(de, g, b, !0) : (wt[Ce - L] = v + 1, Ce >= Ae ? Ae = Ce : Ie = !0, $(
          de,
          u[Ce],
          h,
          null,
          g,
          b,
          x,
          y,
          w
        ), fe++);
      }
      const pn = Ie ? Ro(wt) : ft;
      for (W = pn.length - 1, v = ue - 1; v >= 0; v--) {
        const de = L + v, Ce = u[de], gn = de + 1 < T ? u[de + 1].el : _;
        wt[v] === 0 ? $(
          null,
          Ce,
          h,
          gn,
          g,
          b,
          x,
          y,
          w
        ) : Ie && (W < 0 || v !== pn[W] ? Qe(Ce, h, gn, 2) : W--);
      }
    }
  }, Qe = (a, u, h, _, g = null) => {
    const { el: b, type: x, transition: y, children: w, shapeFlag: v } = a;
    if (v & 6) {
      Qe(a.component.subTree, u, h, _);
      return;
    }
    if (v & 128) {
      a.suspense.move(u, h, _);
      return;
    }
    if (v & 64) {
      x.move(a, u, h, vt);
      return;
    }
    if (x === q) {
      n(b, u, h);
      for (let I = 0; I < w.length; I++)
        Qe(w[I], u, h, _);
      n(a.anchor, u, h);
      return;
    }
    if (x === As) {
      Z(a, u, h);
      return;
    }
    if (_ !== 2 && v & 1 && y)
      if (_ === 0)
        y.beforeEnter(b), n(b, u, h), he(() => y.enter(b), g);
      else {
        const { leave: I, delayLeave: C, afterLeave: O } = y, L = () => n(b, u, h), V = () => {
          I(b, () => {
            L(), O && O();
          });
        };
        C ? C(b, L, V) : V();
      }
    else
      n(b, u, h);
  }, xe = (a, u, h, _ = !1, g = !1) => {
    const {
      type: b,
      props: x,
      ref: y,
      children: w,
      dynamicChildren: v,
      shapeFlag: T,
      patchFlag: I,
      dirs: C,
      cacheIndex: O
    } = a;
    if (I === -2 && (g = !1), y != null && ts(y, null, h, a, !0), O != null && (u.renderCache[O] = void 0), T & 256) {
      u.ctx.deactivate(a);
      return;
    }
    const L = T & 1 && C, V = !Et(a);
    let W;
    if (V && (W = x && x.onVnodeBeforeUnmount) && $e(W, u, a), T & 6)
      li(a.component, h, _);
    else {
      if (T & 128) {
        a.suspense.unmount(h, _);
        return;
      }
      L && et(a, null, u, "beforeUnmount"), T & 64 ? a.type.remove(
        a,
        u,
        h,
        vt,
        _
      ) : v && // #5154
      // when v-once is used inside a block, setBlockTracking(-1) marks the
      // parent block with hasOnce: true
      // so that it doesn't take the fast path during unmount - otherwise
      // components nested in v-once are never unmounted.
      !v.hasOnce && // #1153: fast path should not be taken for non-stable (v-for) fragments
      (b !== q || I > 0 && I & 64) ? _t(
        v,
        u,
        h,
        !1,
        !0
      ) : (b === q && I & 384 || !g && T & 16) && _t(w, u, h), _ && dn(a);
    }
    (V && (W = x && x.onVnodeUnmounted) || L) && he(() => {
      W && $e(W, u, a), L && et(a, null, u, "unmounted");
    }, h);
  }, dn = (a) => {
    const { type: u, el: h, anchor: _, transition: g } = a;
    if (u === q) {
      oi(h, _);
      return;
    }
    if (u === As) {
      M(a);
      return;
    }
    const b = () => {
      r(h), g && !g.persisted && g.afterLeave && g.afterLeave();
    };
    if (a.shapeFlag & 1 && g && !g.persisted) {
      const { leave: x, delayLeave: y } = g, w = () => x(h, b);
      y ? y(a.el, b, w) : w();
    } else
      b();
  }, oi = (a, u) => {
    let h;
    for (; a !== u; )
      h = m(a), r(a), a = h;
    r(u);
  }, li = (a, u, h) => {
    const { bum: _, scope: g, job: b, subTree: x, um: y, m: w, a: v } = a;
    An(w), An(v), _ && _s(_), g.stop(), b && (b.flags |= 8, xe(x, a, u, h)), y && he(y, u), he(() => {
      a.isUnmounted = !0;
    }, u), u && u.pendingBranch && !u.isUnmounted && a.asyncDep && !a.asyncResolved && a.suspenseId === u.pendingId && (u.deps--, u.deps === 0 && u.resolve());
  }, _t = (a, u, h, _ = !1, g = !1, b = 0) => {
    for (let x = b; x < a.length; x++)
      xe(a[x], u, h, _, g);
  }, Ut = (a) => {
    if (a.shapeFlag & 6)
      return Ut(a.component.subTree);
    if (a.shapeFlag & 128)
      return a.suspense.next();
    const u = m(a.anchor || a.el), h = u && u[to];
    return h ? m(h) : u;
  };
  let ms = !1;
  const hn = (a, u, h) => {
    a == null ? u._vnode && xe(u._vnode, null, null, !0) : $(
      u._vnode || null,
      a,
      u,
      null,
      null,
      null,
      h
    ), u._vnode = a, ms || (ms = !0, vn(), Sr(), ms = !1);
  }, vt = {
    p: $,
    um: xe,
    m: Qe,
    r: dn,
    mt: gs,
    mc: He,
    pc: U,
    pbc: Xe,
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
function tt({ effect: e, job: t }, s) {
  s ? (e.flags |= 32, t.flags |= 4) : (e.flags &= -33, t.flags &= -5);
}
function Oo(e, t) {
  return (!e || e && !e.pendingBranch) && t && !t.persisted;
}
function Ur(e, t, s = !1) {
  const n = e.children, r = t.children;
  if (D(n) && D(r))
    for (let i = 0; i < n.length; i++) {
      const o = n[i];
      let l = r[i];
      l.shapeFlag & 1 && !l.dynamicChildren && ((l.patchFlag <= 0 || l.patchFlag === 32) && (l = r[i] = Be(r[i]), l.el = o.el), !s && l.patchFlag !== -2 && Ur(o, l)), l.type === ps && (l.el = o.el);
    }
}
function Ro(e) {
  const t = e.slice(), s = [0];
  let n, r, i, o, l;
  const c = e.length;
  for (n = 0; n < c; n++) {
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
function Kr(e, t, s = G) {
  const { immediate: n, deep: r, flush: i, once: o } = s, l = ie({}, s), c = t && n || !t && i !== "post";
  let f;
  if (kt) {
    if (i === "sync") {
      const S = Do();
      f = S.__watcherHandles || (S.__watcherHandles = []);
    } else if (!c) {
      const S = () => {
      };
      return S.stop = Oe, S.resume = Oe, S.pause = Oe, S;
    }
  }
  const d = ce;
  l.call = (S, k, $) => Re(S, d, k, $);
  let p = !1;
  i === "post" ? l.scheduler = (S) => {
    he(S, d && d.suspense);
  } : i !== "sync" && (p = !0, l.scheduler = (S, k) => {
    k ? S() : nn(S);
  }), l.augmentJob = (S) => {
    t && (S.flags |= 4), p && (S.flags |= 2, d && (S.id = d.uid, S.i = d));
  };
  const m = Yi(e, t, l);
  return kt && (f ? f.push(m) : c && m()), m;
}
function ko(e, t, s) {
  const n = this.proxy, r = Q(e) ? e.includes(".") ? Gr(n, e) : () => n[e] : e.bind(n, n);
  let i;
  F(t) ? i = t : (i = t.handler, s = t);
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
const Fo = (e, t) => t === "modelValue" || t === "model-value" ? e.modelModifiers : e[`${t}Modifiers`] || e[`${Ge(t)}Modifiers`] || e[`${lt(t)}Modifiers`];
function No(e, t, ...s) {
  if (e.isUnmounted) return;
  const n = e.vnode.props || G;
  let r = s;
  const i = t.startsWith("update:"), o = i && Fo(n, t.slice(7));
  o && (o.trim && (r = s.map((d) => Q(d) ? d.trim() : d)), o.number && (r = s.map(gi)));
  let l, c = n[l = bs(t)] || // also try camelCase event handler (#2249)
  n[l = bs(Ge(t))];
  !c && i && (c = n[l = bs(lt(t))]), c && Re(
    c,
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
function qr(e, t, s = !1) {
  const n = t.emitsCache, r = n.get(e);
  if (r !== void 0)
    return r;
  const i = e.emits;
  let o = {}, l = !1;
  if (!F(e)) {
    const c = (f) => {
      const d = qr(f, t, !0);
      d && (l = !0, ie(o, d));
    };
    !s && t.mixins.length && t.mixins.forEach(c), e.extends && c(e.extends), e.mixins && e.mixins.forEach(c);
  }
  return !i && !l ? (Y(e) && n.set(e, null), null) : (D(i) ? i.forEach((c) => o[c] = null) : ie(o, i), Y(e) && n.set(e, o), o);
}
function hs(e, t) {
  return !e || !os(t) ? !1 : (t = t.slice(2).replace(/Once$/, ""), B(e, t[0].toLowerCase() + t.slice(1)) || B(e, lt(t)) || B(e, t));
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
    emit: c,
    render: f,
    renderCache: d,
    props: p,
    data: m,
    setupState: S,
    ctx: k,
    inheritAttrs: $
  } = e, J = es(e);
  let H, X;
  try {
    if (s.shapeFlag & 4) {
      const M = r || n, ee = M;
      H = Te(
        f.call(
          ee,
          M,
          d,
          p,
          S,
          m,
          k
        )
      ), X = l;
    } else {
      const M = t;
      H = Te(
        M.length > 1 ? M(
          p,
          { attrs: l, slots: o, emit: c }
        ) : M(
          p,
          null
        )
      ), X = t.props ? l : Lo(l);
    }
  } catch (M) {
    Mt.length = 0, fs(M, e, 1), H = ye(ot);
  }
  let Z = H;
  if (X && $ !== !1) {
    const M = Object.keys(X), { shapeFlag: ee } = Z;
    M.length && ee & 7 && (i && M.some(Gs) && (X = Ho(
      X,
      i
    )), Z = mt(Z, X, !1, !0));
  }
  return s.dirs && (Z = mt(Z, null, !1, !0), Z.dirs = Z.dirs ? Z.dirs.concat(s.dirs) : s.dirs), s.transition && rn(Z, s.transition), H = Z, es(J), H;
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
  const { props: n, children: r, component: i } = e, { props: o, children: l, patchFlag: c } = t, f = i.emitsOptions;
  if (t.dirs || t.transition)
    return !0;
  if (s && c >= 0) {
    if (c & 1024)
      return !0;
    if (c & 16)
      return n ? $n(n, o, f) : !!o;
    if (c & 8) {
      const d = t.dynamicProps;
      for (let p = 0; p < d.length; p++) {
        const m = d[p];
        if (o[m] !== n[m] && !hs(f, m))
          return !0;
      }
    }
  } else
    return (r || l) && (!l || !l.$stable) ? !0 : n === o ? !1 : n ? o ? $n(n, o, f) : !0 : !!o;
  return !1;
}
function $n(e, t, s) {
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
  t && t.pendingBranch ? D(e) ? t.effects.push(...e) : t.effects.push(e) : Qi(e);
}
const q = Symbol.for("v-fgt"), ps = Symbol.for("v-txt"), ot = Symbol.for("v-cmt"), As = Symbol.for("v-stc"), Mt = [];
let me = null;
function E(e = !1) {
  Mt.push(me = e ? null : []);
}
function Uo() {
  Mt.pop(), me = Mt[Mt.length - 1] || null;
}
let Dt = 1;
function En(e, t = !1) {
  Dt += e, e < 0 && me && t && (me.hasOnce = !0);
}
function zr(e) {
  return e.dynamicChildren = Dt > 0 ? me || ft : null, Uo(), Dt > 0 && me && me.push(e), e;
}
function P(e, t, s, n, r, i) {
  return zr(
    A(
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
function Ve(e, t, s, n, r) {
  return zr(
    ye(
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
function St(e, t) {
  return e.type === t.type && e.key === t.key;
}
const Xr = ({ key: e }) => e ?? null, Yt = ({
  ref: e,
  ref_key: t,
  ref_for: s
}) => (typeof e == "number" && (e = "" + e), e != null ? Q(e) || re(e) || F(e) ? { i: Me, r: e, k: t, f: !!s } : e : null);
function A(e, t = null, s = null, n = 0, r = null, i = e === q ? 0 : 1, o = !1, l = !1) {
  const c = {
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
    ctx: Me
  };
  return l ? (an(c, s), i & 128 && e.normalize(c)) : s && (c.shapeFlag |= Q(s) ? 8 : 16), Dt > 0 && // avoid a block node from tracking itself
  !o && // has current parent block
  me && // presence of a patch flag indicates this node needs patching on updates.
  // component nodes also should always be patched, because even if the
  // component doesn't need to update, it needs to persist the instance on to
  // the next vnode so that it can be properly unmounted later.
  (c.patchFlag > 0 || i & 6) && // the EVENTS flag is only for hydration and if it is the only flag, the
  // vnode should not be considered dynamic due to handler caching.
  c.patchFlag !== 32 && me.push(c), c;
}
const ye = Vo;
function Vo(e, t = null, s = null, n = 0, r = null, i = !1) {
  if ((!e || e === ho) && (e = ot), Yr(e)) {
    const l = mt(
      e,
      t,
      !0
      /* mergeRef: true */
    );
    return s && an(l, s), Dt > 0 && !i && me && (l.shapeFlag & 6 ? me[me.indexOf(e)] = l : me.push(l)), l.patchFlag = -2, l;
  }
  if (el(e) && (e = e.__vccOpts), t) {
    t = Ko(t);
    let { class: l, style: c } = t;
    l && !Q(l) && (t.class = Je(l)), Y(c) && (sn(c) && !D(c) && (c = ie({}, c)), t.style = ge(c));
  }
  const o = Q(e) ? 1 : Jr(e) ? 128 : so(e) ? 64 : Y(e) ? 4 : F(e) ? 2 : 0;
  return A(
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
  return e ? sn(e) || Fr(e) ? ie({}, e) : e : null;
}
function mt(e, t, s = !1, n = !1) {
  const { props: r, ref: i, patchFlag: o, children: l, transition: c } = e, f = t ? Go(r || {}, t) : r, d = {
    __v_isVNode: !0,
    __v_skip: !0,
    type: e.type,
    props: f,
    key: f && Xr(f),
    ref: t && t.ref ? (
      // #2078 in the case of <component :is="vnode" ref="extra"/>
      // if the vnode itself already has a ref, cloneVNode will need to merge
      // the refs so the single vnode can be set on multiple refs
      s && i ? D(i) ? i.concat(Yt(t)) : [i, Yt(t)] : Yt(t)
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
    patchFlag: t && e.type !== q ? o === -1 ? 16 : o | 16 : o,
    dynamicProps: e.dynamicProps,
    dynamicChildren: e.dynamicChildren,
    appContext: e.appContext,
    dirs: e.dirs,
    transition: c,
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
  return c && n && rn(
    d,
    c.clone(d)
  ), d;
}
function ve(e = " ", t = 0) {
  return ye(ps, null, e, t);
}
function te(e = "", t = !1) {
  return t ? (E(), Ve(ot, null, e)) : ye(ot, null, e);
}
function Te(e) {
  return e == null || typeof e == "boolean" ? ye(ot) : D(e) ? ye(
    q,
    null,
    // #3666, avoid reference pollution when reusing vnode
    e.slice()
  ) : Yr(e) ? Be(e) : ye(ps, null, String(e));
}
function Be(e) {
  return e.el === null && e.patchFlag !== -1 || e.memo ? e : mt(e);
}
function an(e, t) {
  let s = 0;
  const { shapeFlag: n } = e;
  if (t == null)
    t = null;
  else if (D(t))
    s = 16;
  else if (typeof t == "object")
    if (n & 65) {
      const r = t.default;
      r && (r._c && (r._d = !1), an(e, r()), r._c && (r._d = !0));
      return;
    } else {
      s = 32;
      const r = t._;
      !r && !Fr(t) ? t._ctx = Me : r === 3 && Me && (Me.slots._ === 1 ? t._ = 1 : (t._ = 2, e.patchFlag |= 1024));
    }
  else F(t) ? (t = { default: t, _ctx: Me }, s = 32) : (t = String(t), n & 64 ? (s = 16, t = [ve(t)]) : s = 8);
  e.children = t, e.shapeFlag |= s;
}
function Go(...e) {
  const t = {};
  for (let s = 0; s < e.length; s++) {
    const n = e[s];
    for (const r in n)
      if (r === "class")
        t.class !== n.class && (t.class = Je([t.class, n.class]));
      else if (r === "style")
        t.style = ge([t.style, n.style]);
      else if (os(r)) {
        const i = t[r], o = n[r];
        o && i !== o && !(D(i) && i.includes(o)) && (t[r] = i ? [].concat(i, o) : o);
      } else r !== "" && (t[r] = n[r]);
  }
  return t;
}
function $e(e, t, s, n = null) {
  Re(e, t, 7, [
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
    scope: new Si(
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
    propsDefaults: G,
    // inheritAttrs
    inheritAttrs: n.inheritAttrs,
    // state
    ctx: G,
    data: G,
    props: G,
    attrs: G,
    slots: G,
    refs: G,
    setupState: G,
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
  return i.ctx = { _: i }, i.root = t ? t.root : i, i.emit = No.bind(null, i), e.ce && e.ce(i), i;
}
let ce = null, ns, js;
{
  const e = cs(), t = (s, n) => {
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
    (s) => kt = s
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
let kt = !1;
function Yo(e, t = !1, s = !1) {
  t && js(t);
  const { props: n, children: r } = e.vnode, i = Zr(e);
  xo(e, n, i, t), $o(e, r, s);
  const o = i ? Xo(e, t) : void 0;
  return t && js(!1), o;
}
function Xo(e, t) {
  const s = e.type;
  e.accessCache = /* @__PURE__ */ Object.create(null), e.proxy = new Proxy(e.ctx, po);
  const { setup: n } = s;
  if (n) {
    ze();
    const r = e.setupContext = n.length > 1 ? Qo(e) : null, i = Lt(e), o = Nt(
      n,
      e,
      0,
      [
        e.props,
        r
      ]
    ), l = Jn(o);
    if (Ye(), i(), (l || e.sp) && !Et(e) && Ar(e), l) {
      if (o.then(Tn, Tn), t)
        return o.then((c) => {
          Mn(e, c);
        }).catch((c) => {
          fs(c, e, 0);
        });
      e.asyncDep = o;
    } else
      Mn(e, o);
  } else
    Qr(e);
}
function Mn(e, t, s) {
  F(t) ? e.type.__ssrInlineRender ? e.ssrRender = t : e.render = t : Y(t) && (e.setupState = _r(t)), Qr(e);
}
function Qr(e, t, s) {
  const n = e.type;
  e.render || (e.render = n.render || Oe);
  {
    const r = Lt(e);
    ze();
    try {
      go(e);
    } finally {
      Ye(), r();
    }
  }
}
const Zo = {
  get(e, t) {
    return se(e, "get", ""), e[t];
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
function cn(e) {
  return e.exposed ? e.exposeProxy || (e.exposeProxy = new Proxy(_r(Ui(e.exposed)), {
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
  return F(e) && "__vccOpts" in e;
}
const rt = (e, t) => Ji(e, t, kt), tl = "3.5.13";
/**
* @vue/runtime-dom v3.5.13
* (c) 2018-present Yuxi (Evan) You and Vue contributors
* @license MIT
**/
let Bs;
const On = typeof window < "u" && window.trustedTypes;
if (On)
  try {
    Bs = /* @__PURE__ */ On.createPolicy("vue", {
      createHTML: (e) => e
    });
  } catch {
  }
const ei = Bs ? (e) => Bs.createHTML(e) : (e) => e, sl = "http://www.w3.org/2000/svg", nl = "http://www.w3.org/1998/Math/MathML", De = typeof document < "u" ? document : null, Rn = De && /* @__PURE__ */ De.createElement("template"), rl = {
  insert: (e, t, s) => {
    t.insertBefore(e, s || null);
  },
  remove: (e) => {
    const t = e.parentNode;
    t && t.removeChild(e);
  },
  createElement: (e, t, s, n) => {
    const r = t === "svg" ? De.createElementNS(sl, e) : t === "mathml" ? De.createElementNS(nl, e) : s ? De.createElement(e, { is: s }) : De.createElement(e);
    return e === "select" && n && n.multiple != null && r.setAttribute("multiple", n.multiple), r;
  },
  createText: (e) => De.createTextNode(e),
  createComment: (e) => De.createComment(e),
  setText: (e, t) => {
    e.nodeValue = t;
  },
  setElementText: (e, t) => {
    e.textContent = t;
  },
  parentNode: (e) => e.parentNode,
  nextSibling: (e) => e.nextSibling,
  querySelector: (e) => De.querySelector(e),
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
      Rn.innerHTML = ei(
        n === "svg" ? `<svg>${e}</svg>` : n === "mathml" ? `<math>${e}</math>` : e
      );
      const l = Rn.content;
      if (n === "svg" || n === "mathml") {
        const c = l.firstChild;
        for (; c.firstChild; )
          l.appendChild(c.firstChild);
        l.removeChild(c);
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
const Pn = Symbol("_vod"), ll = Symbol("_vsh"), al = Symbol(""), cl = /(^|;)\s*display\s*:/;
function ul(e, t, s) {
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
      const o = n[al];
      o && (s += ";" + o), n.cssText = s, i = cl.test(s);
    }
  } else t && e.removeAttribute("style");
  Pn in e && (e[Pn] = i ? n.display : "", e[ll] && (n.display = "none"));
}
const Dn = /\s*!important$/;
function Xt(e, t, s) {
  if (D(s))
    s.forEach((n) => Xt(e, t, n));
  else if (s == null && (s = ""), t.startsWith("--"))
    e.setProperty(t, s);
  else {
    const n = fl(e, t);
    Dn.test(s) ? e.setProperty(
      lt(n),
      s.replace(Dn, ""),
      "important"
    ) : e[n] = s;
  }
}
const kn = ["Webkit", "Moz", "ms"], Cs = {};
function fl(e, t) {
  const s = Cs[t];
  if (s)
    return s;
  let n = Ge(t);
  if (n !== "filter" && n in e)
    return Cs[t] = n;
  n = Xn(n);
  for (let r = 0; r < kn.length; r++) {
    const i = kn[r] + n;
    if (i in e)
      return Cs[t] = i;
  }
  return t;
}
const Fn = "http://www.w3.org/1999/xlink";
function Nn(e, t, s, n, r, i = yi(t)) {
  n && t.startsWith("xlink:") ? s == null ? e.removeAttributeNS(Fn, t.slice(6, t.length)) : e.setAttributeNS(Fn, t, s) : s == null || i && !Qn(s) ? e.removeAttribute(t) : e.setAttribute(
    t,
    i ? "" : qe(s) ? String(s) : s
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
    const l = i === "OPTION" ? e.getAttribute("value") || "" : e.value, c = s == null ? (
      // #11647: value should be set as empty string for null and undefined,
      // but <input type="checkbox"> should be set as 'on'.
      e.type === "checkbox" ? "on" : ""
    ) : String(s);
    (l !== c || !("_value" in e)) && (e.value = c), s == null && e.removeAttribute(t), e._value = s;
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
    const [l, c] = gl(t);
    if (n) {
      const f = i[t] = _l(
        n,
        r
      );
      dl(e, l, f, c);
    } else o && (hl(e, l, o, c), i[t] = void 0);
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
  return [e[2] === ":" ? e.slice(3) : lt(e.slice(2)), t];
}
let $s = 0;
const ml = /* @__PURE__ */ Promise.resolve(), bl = () => $s || (ml.then(() => $s = 0), $s = Date.now());
function _l(e, t) {
  const s = (n) => {
    if (!n._vts)
      n._vts = Date.now();
    else if (n._vts <= s.attached)
      return;
    Re(
      vl(n, s.value),
      t,
      5,
      [n]
    );
  };
  return s.value = e, s.attached = bl(), s;
}
function vl(e, t) {
  if (D(t)) {
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
  t === "class" ? ol(e, n, o) : t === "style" ? ul(e, s, n) : os(t) ? Gs(t) || pl(e, t, s, n, i) : (t[0] === "." ? (t = t.slice(1), !0) : t[0] === "^" ? (t = t.slice(1), !1) : yl(e, t, n, o)) ? (Ln(e, t, n), !e.tagName.includes("-") && (t === "value" || t === "checked" || t === "selected") && Nn(e, t, n, o, i, t !== "value")) : /* #11081 force set props for possible async custom element */ e._isVueCE && (/[A-Z]/.test(t) || !Q(n)) ? Ln(e, Ge(t), n, i, t) : (t === "true-value" ? e._trueValue = n : t === "false-value" && (e._falseValue = n), Nn(e, t, n, o));
};
function yl(e, t, s, n) {
  if (n)
    return !!(t === "innerHTML" || t === "textContent" || t in e && Bn(t) && F(s));
  if (t === "spellcheck" || t === "draggable" || t === "translate" || t === "form" || t === "list" && e.tagName === "INPUT" || t === "type" && e.tagName === "TEXTAREA")
    return !1;
  if (t === "width" || t === "height") {
    const r = e.tagName;
    if (r === "IMG" || r === "VIDEO" || r === "CANVAS" || r === "SOURCE")
      return !1;
  }
  return Bn(t) && Q(s) ? !1 : t in e;
}
const Sl = /* @__PURE__ */ ie({ patchProp: wl }, rl);
let Wn;
function xl() {
  return Wn || (Wn = To(Sl));
}
const Il = (...e) => {
  const t = xl().createApp(...e), { mount: s } = t;
  return t.mount = (n) => {
    const r = Cl(n);
    if (!r) return;
    const i = t._component;
    !F(i) && !i.render && !i.template && (i.template = r.innerHTML), r.nodeType === 1 && (r.textContent = "");
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
  return Q(e) ? document.querySelector(e) : e;
}
const $l = /* @__PURE__ */ new Set();
function Es(e) {
  return e.executionHost !== null && $l.has(e.executionHost.trim().toLowerCase());
}
function El(e) {
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
function Ml(e, t, s) {
  s.set(t, Math.max(s.get(t), e.maxCursor));
}
const Ws = "@runner", Un = 5e3;
function Ol() {
  return { runs: {}, logs: [], seen: {}, maxCursor: 0 };
}
function ti(e) {
  return e.outcome !== null || e.abandoned;
}
function Rl(e) {
  return Object.values(e.phases).sort((t, s) => t.order - s.order);
}
function qt(e) {
  e.visible = Rl(e).map((t) => t.instanceId);
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
function kl(e, t) {
  return t.phase_id && e.instanceOfPhase[t.phase_id] ? e.instanceOfPhase[t.phase_id] : t.instance_id || t.phase_id;
}
function Fl(e, t) {
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
function Nl(e, t, s) {
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
  const s = Date.parse(t.recorded_at) || 0, n = kl(e, t);
  if (!n) return;
  let r;
  if (t.kind === "bound" ? r = Fl(e, t) : ((i = e.phases)[n] ?? (i[n] = si(t, n)), r = e.phases[n]), t.attempt !== null && t.attempt !== void 0 && (r.attempt = t.attempt), Nl(e, t, r.instanceId), t.kind === "constructed" ? (r.constructed = !0, r.className = t.message) : t.kind === "purpose" ? r.purpose = t.message : t.kind === "cleanup" ? (r.cleanup = t.message, !r.started && r.outcome === null && (r.abandoned = !0)) : t.kind === "error" && (r.error = t.message), r.outcome !== null || r.abandoned) {
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
  var i, o, l, c;
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
    r.seen[f.event_id] = !0, r.maxCursor = Math.max(r.maxCursor, f.cursor), (l = r.runs)[c = f.run_id] ?? (l[c] = Vn({
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
    const c = r.evaluate(
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
    o = c ? "stalled" : e.waitDeadlineAt !== null ? "waiting" : "running", l = [
      Us(e.startedAt, s),
      (c == null ? void 0 : c.reason) ?? e.waitReason
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
    o.map((m, S) => [m.instanceId, S])
  ), c = Date.parse(e.startedAt) || (((p = e.arrows[0]) == null ? void 0 : p.at) ?? 0), d = e.arrows.filter((m) => l.has(m.from) && l.has(m.to)).sort((m, S) => m.cursor - S.cursor).map((m) => ({
    id: m.id,
    from: l.get(m.from),
    to: l.get(m.to),
    text: m.text,
    dashed: m.dashed,
    kind: m.kind,
    elapsed: Xl(c, m.at)
  }));
  for (const m of o) {
    if (m.kind === "runner") {
      m.activeFrom = d.length ? 0 : null, m.activeTo = e.status === "running" ? null : d.length - 1;
      continue;
    }
    const S = l.get(m.instanceId), k = d.findIndex((H) => H.to === S || H.from === S), $ = d.findIndex(
      (H) => H.kind === "phase_end" && H.from === S
    ), J = e.phases[m.instanceId];
    m.activeFrom = J != null && J.started && k >= 0 ? k : null, m.activeTo = $ >= 0 ? $ : null;
  }
  return { runId: e.runId, columns: o, rows: d };
}
function Ql(e) {
  const t = e.replace(/\.py$/, "").replace(/^adw_/, "").replace(/^(interface|op)_/, "").replace(/_/g, " ").trim();
  return t ? t[0].toUpperCase() + t.slice(1) : "An ADW";
}
function ea(e) {
  if (!e) return "No ADW has run yet -- the next one started will show here";
  const t = Ql(e.adwName), s = e.visible.map((f) => e.phases[f]).filter(Boolean), n = s.length, i = s.filter((f) => f.started && !ti(f)).at(-1), o = s.find((f) => f.outcome === "fail"), l = (f) => `step ${s.indexOf(f) + 1} of ${n}, ${f.name.replace(/_/g, " ")}`, c = (f) => `${f} step${f === 1 ? "" : "s"}`;
  switch (e.status) {
    case "running":
      return i ? `Running now: ${t} -- ${l(i)}` : n === 0 ? `Running now: ${t} -- starting up` : `Running now: ${t} -- between steps, ${s.filter((f) => f.outcome).length} of ${n} done`;
    case "success":
      return `Finished: ${t} -- all ${c(n)} passed`;
    case "fail":
      return o ? `Failed: ${t} -- stopped at ${l(o)}` : `Failed: ${t} -- after ${c(n)}`;
    case "interrupted":
      return i ? `Stopped: ${t} -- its process ended during ${l(i)}` : `Stopped: ${t} -- its process ended without finishing`;
    default:
      return `${t} -- ${c(n)}`;
  }
}
function ta(e, t, s, n) {
  var i;
  const r = s.mode === "phase" ? (i = n.runs[s.runId]) == null ? void 0 : i.phases[s.instanceId] : void 0;
  return {
    headline: ea(e),
    modeLabel: ql[t],
    filterLabel: s.mode === "all" ? "All events" : `Run ${s.runId} -- phase ${(r == null ? void 0 : r.name) ?? s.instanceId} (${s.instanceId}${r != null && r.attempt ? `, attempt ${r.attempt}` : ""})`,
    clearLabel: e ? `Clear displayed logs for ${e.runId}` : "Clear displayed logs",
    clearDisabledReason: e ? "" : "No ADW run is selected, so there is nothing run-scoped to clear."
  };
}
class sa {
  constructor(t) {
    N(this, "state", Ol());
    N(this, "selected", { runId: null, pinReleased: !1 });
    N(this, "filter", { mode: "all" });
    N(this, "connection", { status: "connecting" });
    N(this, "timeoutSeconds", 120);
    N(this, "lastDelayMs", null);
    N(this, "renderError", "");
    N(this, "dadsComputerOnly", !1);
    N(this, "supervisorEvents", []);
    N(this, "supervisorGaps", []);
    N(this, "supervisorError", "");
    N(this, "supervisorMachine", "");
    N(this, "supervisorAgent", "");
    N(this, "supervisorCorrelate", !1);
    N(this, "unsubscribeSupervisor", null);
    N(this, "tick", null);
    N(this, "unsubscribe", null);
    N(this, "listeners", /* @__PURE__ */ new Set());
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
    this.dadsComputerOnly && t && !Es(t) && (this.selected = { runId: null, pinReleased: !1 }, this.filter = { mode: "all" }), this.follow(this.deps.selection.select(this.selected, this.runs())), this.publish();
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
    this.selected.runId && (Ml(this.state, this.selected.runId, this.deps.cleared), this.publish());
  }
  reportRenderError(t) {
    this.renderError = t, this.publish();
  }
  runs() {
    return Object.values(this.state.runs).filter((t) => !this.dadsComputerOnly || Es(t)).map((t) => ({
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
    ), i = Object.values(this.state.runs), o = this.dadsComputerOnly ? i.filter(Es) : i;
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
      dadsComputerFilterAvailable: i.some(El),
      dadsComputerVisibleRuns: o.length,
      supervisor: this.supervisorView((t == null ? void 0 : t.runId) ?? null),
      ...ta(t, s, this.filter, this.state)
    };
  }
  publish() {
    this.deps.legacy.setVisible(this.filter.mode === "all");
    const t = this.view();
    for (const s of this.listeners) s(t);
  }
}
function na(e, t) {
  return e.startedAt.localeCompare(t.startedAt) || e.runId.localeCompare(t.runId);
}
class ra {
  select(t, s) {
    const n = [...s].sort(na).at(-1);
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
function Ts(e) {
  return `${Math.max(0, Math.round(e / 1e3))}s`;
}
class ia {
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
class Kn {
  async getJSON(t) {
    const s = await fetch(t, { cache: "no-store" });
    if (!s.ok) throw new Error(`HTTP ${s.status} from ${t}`);
    return s.json();
  }
}
class oa {
  set(t, s) {
    return window.setTimeout(t, s);
  }
  clear(t) {
    window.clearTimeout(t);
  }
}
class la {
  constructor() {
    N(this, "offset", 0);
  }
  align(t) {
    const s = Date.parse(t);
    Number.isNaN(s) || (this.offset = s - Date.now());
  }
  now() {
    return Date.now() + this.offset;
  }
}
class aa {
  constructor(t = "adwDebugger.clearedThrough.v1") {
    N(this, "marks", {});
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
class ca {
  constructor(t) {
    this.node = t;
  }
  setVisible(t) {
    this.node && (this.node.style.display = t ? "" : "none");
  }
}
class ua {
  constructor(t, s, n) {
    N(this, "listeners", /* @__PURE__ */ new Set());
    N(this, "cursor", null);
    N(this, "handle", null);
    N(this, "running", !1);
    N(this, "inflight", !1);
    N(this, "failures", 0);
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
class fa {
  constructor(t, s, n) {
    N(this, "listeners", /* @__PURE__ */ new Set());
    N(this, "machine", "");
    N(this, "handle", null);
    N(this, "running", !1);
    N(this, "inflight", !1);
    N(this, "failures", 0);
    N(this, "generation", 0);
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
  setMachine(t) {
    t !== this.machine && (this.machine = t, this.generation += 1, this.failures = 0, this.emit({ status: "connecting" }), this.running && (this.timer.clear(this.handle), this.inflight = !1, this.poll()));
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
  urlFor() {
    return this.machine ? `${this.options.url}${this.options.url.includes("?") ? "&" : "?"}machine=${encodeURIComponent(this.machine)}` : this.options.url;
  }
  async poll() {
    if (this.inflight || !this.running) return;
    this.inflight = !0;
    const t = this.generation;
    try {
      const s = await this.http.getJSON(this.urlFor());
      if (!this.running || t !== this.generation) return;
      if (this.failures = 0, s.ok) {
        this.emit({ status: "connected" });
        for (const n of this.listeners) n.onPage(s);
      } else
        this.emit({
          status: "degraded",
          reason: s.error || "the supervisor records could not be read"
        });
    } catch (s) {
      if (t !== this.generation) return;
      this.failures += 1, this.emit({
        status: "disconnected",
        attempts: this.failures,
        reason: s instanceof Error ? s.message : String(s)
      });
    } finally {
      t === this.generation && (this.inflight = !1, this.schedule());
    }
  }
}
class da {
  constructor() {
    N(this, "lastGood", { runId: "", columns: [], rows: [] });
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
const ha = { class: "adwdbg-log" }, pa = { class: "adwdbg-log-head" }, ga = { class: "adwdbg-log-label" }, ma = {
  key: 0,
  class: "adwdbg-log-empty"
}, ba = ["data-kind", "data-run"], _a = /* @__PURE__ */ Fe({
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
      n.value && (await wr(), s.value && (s.value.scrollTop = s.value.scrollHeight));
    }, { immediate: !0 }), (i, o) => (E(), P("div", ha, [
      A("div", pa, [
        A("span", ga, R(i.label), 1),
        A("span", null, R(i.lines.length) + " line" + R(i.lines.length === 1 ? "" : "s") + R(n.value ? "" : " · paused (scroll to bottom to follow)"), 1)
      ]),
      A("div", {
        ref_key: "host",
        ref: s,
        class: Je(["adwdbg-log-lines", { "adwdbg-log-tall": i.tall }]),
        role: "log",
        onScroll: r
      }, [
        i.lines.length === 0 ? (E(), P("div", ma, "No ADW events to show.")) : te("", !0),
        (E(!0), P(q, null, _e(i.lines, (l) => (E(), P("div", {
          key: l.eventId,
          class: "adwdbg-log-line",
          "data-kind": l.kind,
          "data-run": l.runId
        }, R(l.text), 9, ba))), 128))
      ], 34)
    ]));
  }
}), It = 78, va = 170, Ft = 40, un = 22, Ms = 11;
function Vs(e, t) {
  return (e + 0.5) / Math.max(1, t) * 100;
}
function wa(e) {
  return 100 / Math.max(1, e);
}
function is(e) {
  return un + e * Ft + Ft * 0.62;
}
function ii(e) {
  return un * 2 + Math.max(1, e) * Ft;
}
function ya(e, t, s) {
  const n = is(e) - Ms, r = t === null ? ii(s) - un / 2 : is(Math.max(e, t)) + Ms;
  return { top: n, height: Math.max(Ms * 2, r - n) };
}
function Sa(e, t) {
  return e === t ? "self" : e < t ? "right" : "left";
}
const xa = ["data-status"], Ia = /* @__PURE__ */ Fe({
  __name: "ActivationBar",
  props: {
    from: {},
    to: {},
    rows: {},
    status: {}
  },
  setup(e) {
    const t = e, s = rt(() => ya(t.from, t.to, t.rows));
    return (n, r) => (E(), P("span", {
      class: Je(["sd-bar", { "sd-bar-open": n.to === null }]),
      "data-status": n.status,
      style: ge({ top: `${s.value.top}px`, height: `${s.value.height}px` })
    }, null, 14, xa));
  }
}), Aa = ["data-lifeline"], Ca = /* @__PURE__ */ Fe({
  __name: "Lifeline",
  props: {
    column: {},
    centre: {},
    rows: {}
  },
  setup(e) {
    return (t, s) => (E(), P("div", {
      class: "sd-lifeline-track",
      "data-lifeline": t.column.instanceId,
      style: ge({ left: `${t.centre}%` })
    }, [
      s[0] || (s[0] = A("span", { class: "sd-lifeline" }, null, -1)),
      t.column.activeFrom !== null && t.column.activeFrom !== void 0 ? (E(), Ve(Ia, {
        key: 0,
        from: t.column.activeFrom,
        to: t.column.activeTo ?? null,
        rows: t.rows,
        status: t.column.status
      }, null, 8, ["from", "to", "rows", "status"])) : te("", !0)
    ], 12, Aa));
  }
}), $a = ["data-kind", "data-row"], Ea = ["title"], Ta = { class: "sd-label-text" }, Ma = /* @__PURE__ */ Fe({
  __name: "MessageArrow",
  props: {
    row: {},
    index: {},
    count: {}
  },
  setup(e) {
    const t = e, s = rt(() => Sa(t.row.from, t.row.to)), n = rt(() => {
      const r = `${is(t.index) - Ft * 0.62}px`, i = `${Ft}px`, o = Vs(t.row.from, t.count);
      if (s.value === "self") {
        const c = t.row.from === t.count - 1 ? 0.46 : 0.92;
        return { top: r, height: i, left: `${o}%`, width: `${wa(t.count) * c}%` };
      }
      const l = Vs(t.row.to, t.count);
      return { top: r, height: i, left: `${Math.min(o, l)}%`, width: `${Math.abs(l - o)}%` };
    });
    return (r, i) => (E(), P("div", {
      class: Je(["sd-message", [`sd-${s.value}`, { "sd-dashed": r.row.dashed }]]),
      "data-kind": r.row.kind,
      "data-row": r.index,
      style: ge(n.value)
    }, [
      A("div", {
        class: "sd-label",
        title: r.row.text
      }, [
        A("span", Ta, R(r.row.text), 1)
      ], 8, Ea),
      i[0] || (i[0] = A("div", { class: "sd-line" }, [
        A("span", { class: "sd-head" })
      ], -1))
    ], 14, $a));
  }
}), Oa = ["data-status", "data-instance", "data-edge", "data-participant", "title", "aria-pressed"], Ra = { class: "sd-name" }, Pa = { class: "sd-status" }, Gn = /* @__PURE__ */ Fe({
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
    return (i, o) => (E(), P("button", {
      type: "button",
      class: Je(["sd-box", { "sd-selected": i.column.selected, "sd-runner": i.column.kind === "runner" }]),
      "data-status": i.column.status,
      "data-instance": i.column.instanceId,
      "data-edge": i.edge,
      "data-participant": i.column.kind ?? "phase",
      title: r(),
      "aria-pressed": i.column.selected,
      onClick: o[0] || (o[0] = (l) => n("select", i.column))
    }, [
      A("span", Ra, [
        ve(R(i.column.name), 1),
        i.column.attempt && i.column.attempt > 1 ? (E(), P(q, { key: 0 }, [
          ve(" · attempt " + R(i.column.attempt), 1)
        ], 64)) : te("", !0)
      ]),
      A("span", Pa, [
        ve(R(i.column.statusLabel), 1),
        i.column.detail ? (E(), P(q, { key: 0 }, [
          ve(" · " + R(i.column.detail), 1)
        ], 64)) : te("", !0)
      ])
    ], 10, Oa));
  }
}), Da = /* @__PURE__ */ Fe({
  __name: "TimeAxis",
  props: {
    rows: {}
  },
  setup(e) {
    return (t, s) => (E(), P("div", {
      class: "sd-axis",
      style: ge({ width: `${We(It)}px` }),
      "aria-hidden": "true"
    }, [
      (E(!0), P(q, null, _e(t.rows, (n, r) => (E(), P("span", {
        key: n.id,
        class: "sd-tick",
        style: ge({ top: `${We(is)(r)}px` })
      }, R(n.elapsed), 5))), 128))
    ], 4));
  }
}), ka = { class: "sd" }, Fa = { class: "sd-tools" }, Na = { class: "sd-zoom-value" }, La = { class: "sd-hint" }, Ha = { class: "sd-frozen" }, ja = /* @__PURE__ */ Fe({
  __name: "SequenceDiagram",
  props: {
    model: {},
    hint: { default: "Click a phase box to filter the events below; click the ADW box for all events." }
  },
  emits: ["phase-click", "runner-click"],
  setup(e, { emit: t }) {
    const s = e, n = t, r = ut(1), i = ut(null), o = ut(null), l = ut(!1);
    let c = null;
    Er(() => {
      typeof IntersectionObserver > "u" || !i.value || !o.value || (c = new IntersectionObserver(([S]) => {
        l.value = S.isIntersecting;
      }, { root: i.value }), c.observe(o.value));
    }), on(() => c == null ? void 0 : c.disconnect());
    const f = rt(() => Math.max(1, s.model.columns.length)), d = rt(() => s.model.rows.length), p = rt(() => `${It + f.value * va}px`);
    function m(S) {
      S.kind === "runner" ? n("runner-click") : n("phase-click", S.instanceId);
    }
    return (S, k) => (E(), P("div", ka, [
      A("div", Fa, [
        A("button", {
          type: "button",
          class: "sd-zoom",
          "aria-label": "Zoom out",
          onClick: k[0] || (k[0] = ($) => r.value = Math.max(0.4, r.value - 0.1))
        }, "-"),
        A("span", Na, R(Math.round(r.value * 100)) + "%", 1),
        A("button", {
          type: "button",
          class: "sd-zoom",
          "aria-label": "Zoom in",
          onClick: k[1] || (k[1] = ($) => r.value = Math.min(2, r.value + 0.1))
        }, "+"),
        A("button", {
          type: "button",
          class: "sd-zoom",
          onClick: k[2] || (k[2] = ($) => r.value = 1)
        }, "Reset"),
        A("span", La, R(S.hint), 1)
      ]),
      A("div", {
        ref_key: "scroller",
        ref: i,
        class: "sd-scroll"
      }, [
        A("div", {
          class: "sd-canvas",
          style: ge({ zoom: r.value, minWidth: p.value })
        }, [
          A("div", Ha, [
            A("div", {
              class: Je(["sd-titles sd-titles-top", { "sd-pinned": !l.value }]),
              style: ge({ paddingLeft: `${We(It)}px` })
            }, [
              (E(!0), P(q, null, _e(S.model.columns, ($) => (E(), Ve(Gn, {
                key: $.instanceId,
                column: $,
                edge: "top",
                onSelect: m
              }, null, 8, ["column"]))), 128))
            ], 6),
            A("div", {
              class: "sd-body",
              style: ge({ height: `${We(ii)(d.value)}px` })
            }, [
              ye(Da, {
                rows: S.model.rows
              }, null, 8, ["rows"]),
              A("div", {
                class: "sd-plot",
                style: ge({ left: `${We(It)}px` })
              }, [
                (E(!0), P(q, null, _e(S.model.columns, ($, J) => (E(), Ve(Ca, {
                  key: $.instanceId,
                  column: $,
                  centre: We(Vs)(J, f.value),
                  rows: d.value
                }, null, 8, ["column", "centre", "rows"]))), 128)),
                (E(!0), P(q, null, _e(S.model.rows, ($, J) => (E(), Ve(Ma, {
                  key: $.id,
                  row: $,
                  index: J,
                  count: f.value
                }, null, 8, ["row", "index", "count"]))), 128))
              ], 4)
            ], 4)
          ]),
          A("div", {
            ref_key: "bottomRow",
            ref: o,
            class: "sd-titles sd-titles-bottom",
            style: ge({ marginLeft: `${We(It)}px` })
          }, [
            (E(!0), P(q, null, _e(S.model.columns, ($) => (E(), Ve(Gn, {
              key: $.instanceId,
              column: $,
              edge: "bottom",
              onSelect: m
            }, null, 8, ["column"]))), 128))
          ], 4)
        ], 4)
      ], 512)
    ]));
  }
}), Ba = {
  class: "adwsup",
  "aria-label": "Supervisor activity",
  "data-field": "supervisor"
}, Wa = { class: "adwsup-bar" }, Ua = { class: "adwdbg-note" }, Va = ["value"], Ka = ["value"], Ga = { class: "adwdbg-note" }, qa = ["value"], Ja = ["value"], za = ["aria-pressed"], Ya = ["data-supervisor-state"], Xa = { class: "adwdbg-note" }, Za = {
  key: 0,
  class: "adwdbg-warn",
  "data-warning": "supervisor",
  role: "status"
}, Qa = { class: "adwdbg-log" }, ec = {
  class: "adwdbg-log-lines adwsup-lines",
  role: "log",
  "aria-label": "Supervisor records"
}, tc = {
  key: 0,
  class: "adwsup-empty",
  "data-field": "supervisor-empty"
}, sc = ["data-kind", "data-state"], nc = { class: "adwsup-at" }, rc = { class: "adwsup-who" }, ic = { class: "adwsup-kind" }, oc = { class: "adwsup-text" }, lc = {
  key: 0,
  class: "adwsup-ids"
}, ac = /* @__PURE__ */ Fe({
  __name: "SupervisorPane",
  props: {
    supervisor: {}
  },
  emits: ["machine", "agent", "correlate"],
  setup(e, { emit: t }) {
    const s = t;
    function n(r, i) {
      const o = r.target.value;
      s(i === "machine" ? "machine" : "agent", o);
    }
    return (r, i) => (E(), P("section", Ba, [
      A("div", Wa, [
        i[6] || (i[6] = A("strong", null, "Supervisors", -1)),
        A("label", Ua, [
          i[3] || (i[3] = ve("Machine ")),
          A("select", {
            "data-field": "supervisor-machine",
            value: r.supervisor.machine,
            onChange: i[0] || (i[0] = (o) => n(o, "machine"))
          }, [
            (E(!0), P(q, null, _e(r.supervisor.machines, (o) => (E(), P("option", {
              key: o,
              value: o
            }, R(o || "This machine"), 9, Ka))), 128))
          ], 40, Va)
        ]),
        A("label", Ga, [
          i[5] || (i[5] = ve("Agent ")),
          A("select", {
            "data-field": "supervisor-agent",
            value: r.supervisor.agent,
            onChange: i[1] || (i[1] = (o) => n(o, "agent"))
          }, [
            i[4] || (i[4] = A("option", { value: "" }, "All agents", -1)),
            (E(!0), P(q, null, _e(r.supervisor.agents, (o) => (E(), P("option", {
              key: o,
              value: o
            }, R(o), 9, Ja))), 128))
          ], 40, qa)
        ]),
        A("button", {
          type: "button",
          class: "am-btn",
          "data-action": "supervisor-correlate",
          "aria-pressed": r.supervisor.correlate,
          onClick: i[2] || (i[2] = (o) => s("correlate"))
        }, R(r.supervisor.correlateLabel), 9, za),
        r.supervisor.awake ? (E(), P("span", {
          key: 0,
          class: "adwdbg-chip",
          "data-field": "supervisor-state",
          "data-supervisor-state": r.supervisor.awake
        }, R(r.supervisor.awake), 9, Ya)) : te("", !0),
        A("span", Xa, R(r.supervisor.lines.length) + " of " + R(r.supervisor.total) + " records", 1)
      ]),
      r.supervisor.error ? (E(), P("p", Za, " Supervisor records could not be read: " + R(r.supervisor.error) + ". This is a connection problem, not a supervisor failure. ", 1)) : te("", !0),
      (E(!0), P(q, null, _e(r.supervisor.gaps, (o) => (E(), P("p", {
        key: o,
        class: "adwdbg-note",
        "data-field": "supervisor-gap"
      }, "Not shown: " + R(o), 1))), 128)),
      A("div", Qa, [
        A("div", ec, [
          r.supervisor.lines.length ? te("", !0) : (E(), P("p", tc, R(r.supervisor.total ? "No supervisor record matches this filter." : "No supervisor record has been read yet."), 1)),
          (E(!0), P(q, null, _e(r.supervisor.lines, (o) => (E(), P("div", {
            key: o.key,
            class: "adwsup-line",
            "data-kind": o.kind,
            "data-state": o.state
          }, [
            A("span", nc, R(o.at), 1),
            A("span", rc, R(o.machine) + "/" + R(o.agent), 1),
            A("span", ic, [
              ve(R(o.kind), 1),
              o.state ? (E(), P(q, { key: 0 }, [
                ve(" · " + R(o.state), 1)
              ], 64)) : te("", !0)
            ]),
            A("span", oc, R(o.text), 1),
            o.ids ? (E(), P("span", lc, R(o.ids), 1)) : te("", !0)
          ], 8, sc))), 128))
        ])
      ])
    ]));
  }
}), cc = {
  key: 0,
  class: "adwdbg",
  "aria-label": "Live ADW sequence debugger"
}, uc = { class: "adwdbg-head" }, fc = ["title"], dc = {
  "data-field": "adw",
  class: "adwdbg-note"
}, hc = {
  "data-field": "run",
  class: "adwdbg-note"
}, pc = ["data-run-status"], gc = ["data-mode"], mc = {
  class: "adwdbg-legend",
  "aria-label": "Status colours"
}, bc = ["data-status"], _c = {
  key: 0,
  class: "adwdbg-warn",
  "data-warning": "connection",
  role: "status"
}, vc = {
  key: 1,
  class: "adwdbg-warn",
  "data-warning": "feed",
  role: "status"
}, wc = {
  key: 2,
  class: "adwdbg-warn",
  "data-warning": "render",
  role: "alert"
}, yc = {
  key: 4,
  class: "adwdbg-idle",
  "data-field": "idle"
}, Sc = { class: "adwdbg-bar" }, xc = ["aria-pressed"], Ic = {
  key: 0,
  class: "adwdbg-note"
}, Ac = {
  key: 1,
  class: "adwdbg-note"
}, Cc = ["disabled"], $c = ["disabled", "title"], Ec = {
  key: 2,
  class: "adwdbg-note"
}, Tc = {
  class: "adwdbg-note",
  "data-field": "timing"
}, Mc = /* @__PURE__ */ Fe({
  __name: "DebuggerPanel",
  props: {
    controller: {}
  },
  setup(e) {
    const t = e, s = Vi(null), n = t.controller.subscribe((i) => {
      s.value = i;
    });
    on(n), Mr((i) => (t.controller.reportRenderError(i instanceof Error ? i.message : String(i)), !1));
    const r = [
      ["waiting", "Waiting"],
      ["running", "Running"],
      ["stalled", "Stalled"],
      ["fail", "Fail"],
      ["pass", "Pass"]
    ];
    return (i, o) => s.value ? (E(), P("section", cc, [
      A("header", uc, [
        A("strong", {
          class: "adwdbg-title",
          "data-field": "headline",
          title: s.value.adwName || void 0,
          "aria-live": "polite"
        }, R(s.value.headline), 9, fc),
        s.value.runId ? (E(), P(q, { key: 0 }, [
          A("span", dc, R(s.value.adwName), 1),
          A("span", hc, "run " + R(s.value.runId), 1),
          A("span", {
            class: "adwdbg-chip",
            "data-run-status": s.value.runStatus,
            "data-field": "status"
          }, R(s.value.runStatus), 9, pc)
        ], 64)) : te("", !0),
        A("span", {
          class: "adwdbg-chip",
          "data-mode": s.value.mode,
          "data-field": "mode"
        }, R(s.value.modeLabel), 9, gc),
        A("span", mc, [
          (E(), P(q, null, _e(r, ([l, c]) => A("span", {
            key: l,
            class: "adwdbg-key",
            "data-status": l
          }, R(c), 9, bc)), 64)),
          o[9] || (o[9] = A("span", { class: "adwdbg-key adwdbg-key-selected" }, "Selected", -1))
        ])
      ]),
      s.value.connection.status === "disconnected" ? (E(), P("p", _c, " Event feed disconnected (attempt " + R(s.value.connection.attempts) + "): " + R(s.value.connection.reason) + ". The diagram shows the last events received; this is a connection problem, not an ADW failure. ", 1)) : s.value.connection.status === "degraded" ? (E(), P("p", vc, " The dashboard cannot read the ADW trace: " + R(s.value.connection.reason), 1)) : te("", !0),
      s.value.renderError ? (E(), P("p", wc, " Diagram could not be redrawn (" + R(s.value.renderError) + "). Showing the last good diagram; the terminal is unaffected. ", 1)) : te("", !0),
      s.value.diagram.columns.length ? (E(), Ve(ja, {
        key: 3,
        model: s.value.diagram,
        onPhaseClick: o[0] || (o[0] = (l) => t.controller.selectPhase(l)),
        onRunnerClick: o[1] || (o[1] = (l) => t.controller.allEvents())
      }, null, 8, ["model"])) : (E(), P("p", yc, R(s.value.runId ? "This run has not started a step yet." : "No ADW run has been recorded yet."), 1)),
      A("div", Sc, [
        A("button", {
          type: "button",
          class: "am-btn",
          "data-action": "follow-live",
          onClick: o[2] || (o[2] = (l) => t.controller.followLive())
        }, "Follow live"),
        A("button", {
          type: "button",
          class: "am-btn",
          "data-action": "dads-computer-only",
          "aria-pressed": s.value.dadsComputerOnly,
          onClick: o[3] || (o[3] = (l) => t.controller.toggleDadsComputerOnly())
        }, " Dad's Computer Only ", 8, xc),
        s.value.dadsComputerOnly && !s.value.dadsComputerFilterAvailable ? (E(), P("span", Ic, " Execution host metadata is not available; no runs can be verified as Dad's computer. ")) : s.value.dadsComputerOnly && s.value.dadsComputerVisibleRuns === 0 ? (E(), P("span", Ac, " No verified Dad's computer runs. ")) : te("", !0),
        A("button", {
          type: "button",
          class: "am-btn",
          "data-action": "all-events",
          disabled: !s.value.phaseSelected,
          onClick: o[4] || (o[4] = (l) => t.controller.allEvents())
        }, "All events", 8, Cc),
        A("button", {
          type: "button",
          class: "am-btn",
          "data-action": "clear-run",
          disabled: !!s.value.clearDisabledReason,
          title: s.value.clearDisabledReason,
          onClick: o[5] || (o[5] = (l) => t.controller.clearSelectedRun())
        }, R(s.value.clearLabel), 9, $c),
        s.value.clearDisabledReason ? (E(), P("span", Ec, R(s.value.clearDisabledReason), 1)) : te("", !0),
        A("span", Tc, [
          ve(" stall timeout " + R(s.value.stallTimeoutSeconds) + "s", 1),
          s.value.lastDelayMs !== null ? (E(), P(q, { key: 0 }, [
            ve(" · last event shown " + R(s.value.lastDelayMs) + " ms after it was recorded", 1)
          ], 64)) : te("", !0)
        ])
      ]),
      ye(_a, {
        lines: s.value.lines,
        label: `ADW events — ${s.value.filterLabel}`,
        tall: s.value.phaseSelected
      }, null, 8, ["lines", "label", "tall"]),
      s.value.supervisor.available ? (E(), Ve(ac, {
        key: 5,
        supervisor: s.value.supervisor,
        onMachine: o[6] || (o[6] = (l) => t.controller.selectSupervisorMachine(l)),
        onAgent: o[7] || (o[7] = (l) => t.controller.selectSupervisorAgent(l)),
        onCorrelate: o[8] || (o[8] = (l) => t.controller.toggleSupervisorCorrelation())
      }, null, 8, ["supervisor"])) : te("", !0)
    ])) : te("", !0);
  }
});
function Oc(e = document) {
  const t = e.getElementById("terminal"), s = e.getElementById("terminal-stream"), n = (t == null ? void 0 : t.querySelector(".terminal-toolbar")) ?? s;
  if (!t || !s || !n || e.getElementById("adw-debugger-root"))
    return null;
  const r = e.createElement("div");
  r.id = "adw-debugger-root", n.parentNode.insertBefore(r, n);
  const i = new oa(), o = new sa({
    source: new ua(new Kn(), i, {
      url: "/api/adw-debugger/feed",
      activeMs: 500,
      idleMs: 5e3,
      retryStepMs: 1e3,
      retryMaxMs: 5e3,
      isActive: () => t.classList.contains("active") && e.visibilityState !== "hidden"
    }),
    selection: new ra(),
    stall: new ia(),
    renderer: new da(),
    cleared: new aa(),
    legacy: new ca(s),
    clock: new la(),
    timer: i,
    supervisor: new fa(new Kn(), i, {
      url: "/api/live-activity",
      activeMs: 3e3,
      idleMs: 15e3,
      retryStepMs: 2e3,
      retryMaxMs: 15e3,
      isActive: () => t.classList.contains("active") && e.visibilityState !== "hidden"
    }),
    machines: ["", "SQMC", "BATI", "R46"]
  }), l = Il(Mc, { controller: o });
  l.mount(r), o.start();
  const c = () => o.wake(), f = new MutationObserver(c);
  return f.observe(t, { attributes: !0, attributeFilter: ["class"] }), e.addEventListener("visibilitychange", c), {
    controller: o,
    unmount() {
      f.disconnect(), e.removeEventListener("visibilitychange", c), o.dispose(), l.unmount(), r.remove();
    }
  };
}
window.adwDebugger = Oc();
export {
  Oc as mountAdwDebugger
};
