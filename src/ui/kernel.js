// Main-thread clients for the Maple (Pyodide) worker and the FlexPDE worker.

/**
 * Maple kernel, shared by every open notebook. Emits 'status' events with detail {status, pct, msg}
 * (status is 'loading' | 'idle' | 'busy' | 'error') and 'restart' when the Maple session was wiped.
 * Runs wait in a main-thread queue and go to the worker one at a time, so a notebook can cancel
 * its own waiting runs without touching the one another notebook is executing.
 */
export class MapleKernel extends EventTarget {
  constructor(baseUrl = new URL(import.meta.env?.BASE_URL ?? './', location.href).href) {
    super()
    this.baseUrl = baseUrl
    this.pending = new Map()
    this.seq = 0
    this.jobs = []        // [{code, owner, resolve, reject}] not yet sent to the worker
    this.current = null   // the job the worker is executing
    this.start()
  }

  get interruptible() { return !!this.interruptBuffer }

  #emit(status, extra = {}) {
    this.status = status
    this.dispatchEvent(new CustomEvent('status', { detail: { status, ...extra } }))
  }

  start() {
    this.worker = new Worker(new URL('../maple/worker.js', import.meta.url), { type: 'module' })
    this.interruptBuffer = globalThis.crossOriginIsolated ? new Int32Array(new SharedArrayBuffer(4)) : null
    this.ready = new Promise((resolve, reject) => { this.#readyResolve = resolve; this.#readyReject = reject })
    this.ready.catch(() => {})
    this.#emit('loading', { pct: 0, msg: 'Starting kernel' })
    this.worker.onmessage = ({ data }) => this.#onMessage(data)
    this.worker.onerror = (e) => { this.#emit('error', { msg: e.message || 'worker failed' }); this.#readyReject(new Error(e.message)) }
    this.worker.postMessage({ type: 'init', baseUrl: this.baseUrl, interruptBuffer: this.interruptBuffer })
  }

  #readyResolve
  #readyReject

  #onMessage(m) {
    if (m.type === 'progress') return this.#emit('loading', { pct: m.pct, msg: m.msg })
    if (m.type === 'ready') { this.#emit('idle'); return this.#readyResolve() }
    if (m.type === 'fatal') { this.#emit('error', { msg: m.message }); return this.#readyReject(new Error(m.message)) }
    const p = this.pending.get(m.id)
    if (!p) return
    this.pending.delete(m.id)
    if (![...this.pending.values()].some((q) => q.busy)) this.#emit('idle')
    p.resolve(m.type === 'result' ? m.outputs : m.type === 'items' ? m.items : undefined)
  }

  async #request(type, payload, busy = false) {
    await this.ready
    const id = ++this.seq
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, busy })
      if (busy) this.#emit('busy')
      this.worker.postMessage({ type, id, ...payload })
    })
  }

  /** Runs a cell for owner (a notebook view); resolves to the output list. Rejects with {interrupted:true} on cancel or restart. */
  run(code, owner = null) {
    return new Promise((resolve, reject) => {
      this.jobs.push({ code, owner, resolve, reject })
      this.#pump()
    })
  }

  async #pump() {
    if (this.current || !this.jobs.length) return
    const job = this.current = this.jobs.shift()
    try { job.resolve(await this.#request('run', { code: job.code }, true)) } catch (e) { job.reject(e) }
    if (this.current === job) this.current = null
    this.#pump()
  }

  /** True when owner's run is the one executing now. */
  isRunning(owner) { return this.current?.owner === owner }

  /** Drops owner's runs that are still waiting (never reach the worker). */
  cancel(owner) {
    const mine = this.jobs.filter((j) => j.owner === owner)
    this.jobs = this.jobs.filter((j) => j.owner !== owner)
    for (const j of mine) j.reject(Object.assign(new Error('Cancelled'), { interrupted: true }))
  }

  /** Names for autocompletion; never waits behind a long computation. */
  complete(prefix) {
    if (this.status !== 'idle') return Promise.resolve([])
    return this.#request('complete', { prefix })
  }

  /** Engine changed on disk (dev): re-import it in place, keeping Pyodide loaded. */
  reloadEngine() { return this.#request('reload', {}, true) }

  /** Interrupt the running computation. Returns true if state survived. */
  interrupt() {
    if (this.interruptBuffer && this.status === 'busy') {
      this.interruptBuffer[0] = 2  // SIGINT -> KeyboardInterrupt in Python
      return true
    }
    this.restart()
    return false
  }

  /** Hard restart: terminates the worker; all kernel state is lost. */
  restart() {
    this.worker.terminate()
    const stopped = Object.assign(new Error('Kernel restarted'), { interrupted: true })
    for (const p of this.pending.values()) p.reject(stopped)
    for (const j of this.jobs) j.reject(stopped)
    this.pending.clear()
    this.jobs = []
    this.current = null
    this.start()
    this.dispatchEvent(new Event('restart'))
  }

  /** Soft restart (Maple restart): fast when the kernel is idle. */
  async reset() {
    if (this.status === 'idle' && !this.current) {
      await this.#request('reset', {})
      this.dispatchEvent(new Event('restart'))
    } else this.restart()
  }
}

/** FlexPDE runner: one worker, recreated on interrupt (runs are stateless). */
export class FlexRunner {
  constructor() { this.seq = 0; this.pending = new Map(); this.#spawn() }

  #spawn() {
    this.worker = new Worker(new URL('./flexWorker.js', import.meta.url), { type: 'module' })
    this.worker.onmessage = ({ data: m }) => {
      const p = this.pending.get(m.id)
      if (!p) return
      if (m.type === 'progress') return p.onProgress?.(m.msg)
      this.pending.delete(m.id)
      p.resolve(m.type === 'result' ? m.result : m.diagnostics)
    }
    this.worker.onerror = (e) => {
      for (const p of this.pending.values()) p.reject(new Error(e.message || 'FlexPDE worker failed'))
      this.pending.clear()
    }
  }

  #request(type, payload, onProgress, owner = null) {
    const id = ++this.seq
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, onProgress, type, payload, owner })
      this.worker.postMessage({ type, id, ...payload })
    })
  }

  run(code, onProgress, owner = null) { return this.#request('run', { code }, onProgress, owner) }
  lint(code) { return this.#request('lint', { code }) }

  get busy() { return [...this.pending.values()].some((p) => p.type === 'run') }

  /**
   * Stops owner's runs. The worker handles requests in order, so the oldest pending one is executing:
   * if that is owner's, the worker is replaced and everyone else's requests are sent to the new one.
   */
  interrupt(owner = null) {
    const [executing] = this.pending.values()
    const stopped = Object.assign(new Error('Stopped'), { interrupted: true })
    for (const [id, p] of this.pending) {
      if (owner && p.owner !== owner) continue
      this.pending.delete(id)
      p.reject(stopped)
    }
    if (!executing || (owner && executing.owner !== owner)) return
    this.worker.terminate()
    this.#spawn()
    for (const [id, p] of this.pending) this.worker.postMessage({ type: p.type, id, ...p.payload })
  }
}
