// Environment-independent part of the Maple kernel: boots Pyodide, installs the
// symflex_maple engine from its zip and exposes run/complete/reset/reload.
// Used by worker.js in the browser and directly by Node tests.

const ENGINE_DIR = '/home/pyodide/symflex'

const GLUE = `
import sys, json, importlib
if ${JSON.stringify(ENGINE_DIR)} not in sys.path:
    sys.path.insert(0, ${JSON.stringify(ENGINE_DIR)})

def _sf_json(x):
    return json.dumps(x, default=str)

def _sf_new_session():
    global _sf_session
    for name in [m for m in sys.modules if m == 'symflex_maple' or m.startswith('symflex_maple.')]:
        del sys.modules[name]
    importlib.invalidate_caches()
    from symflex_maple import Session
    _sf_session = Session()

def _sf_run(code):
    try:
        return _sf_json(_sf_session.run(code))
    except KeyboardInterrupt:
        return _sf_json([{'kind': 'error', 'text': 'Error, computation interrupted'}])
    except Exception as e:
        return _sf_json([{'kind': 'error', 'text': f'Error, (internal) {type(e).__name__}: {e}'}])

def _sf_complete(prefix):
    try:
        return _sf_json(_sf_session.complete(prefix))
    except Exception:
        return '[]'

def _sf_reset():
    _sf_session.reset()
`

/**
 * @param {object} o
 * @param {Function} o.loadPyodide  pyodide's loadPyodide
 * @param {string} o.indexURL       directory holding pyodide.asm.* and the wheels
 * @param {() => Promise<ArrayBuffer>} o.fetchEngine  returns symflex_maple.zip bytes
 * @param {(pct:number, msg:string) => void} [o.onProgress]
 * @param {Int32Array} [o.interruptBuffer]  SharedArrayBuffer view for pyodide.setInterruptBuffer
 */
export async function createKernel({ loadPyodide, indexURL, fetchEngine, onProgress = () => {}, interruptBuffer }) {
  let stray = []  // anything the engine prints to stdout instead of returning
  onProgress(5, 'Loading Python runtime')
  const pyodide = await loadPyodide({
    indexURL,
    // SymPy results can depend on set iteration order; a fixed seed gives the same output on every reload.
    env: { PYTHONHASHSEED: '0' },
    stdout: (s) => stray.push(s),
    stderr: (s) => stray.push(s),
  })
  if (interruptBuffer) pyodide.setInterruptBuffer(interruptBuffer)
  onProgress(45, 'Loading SymPy')
  await pyodide.loadPackage(['mpmath', 'sympy'], { messageCallback: () => {}, errorCallback: (m) => stray.push(m) })
  stray = []

  async function installEngine() {
    onProgress(80, 'Loading Maple engine')
    const zip = await fetchEngine()
    pyodide.FS.mkdirTree(ENGINE_DIR)
    pyodide.unpackArchive(zip, 'zip', { extractDir: ENGINE_DIR })
    pyodide.runPython(GLUE)
    pyodide.globals.get('_sf_new_session')()
  }
  await installEngine()
  onProgress(100, 'Ready')

  const call = (fn, arg) => {
    if (interruptBuffer) interruptBuffer[0] = 0
    return JSON.parse(pyodide.globals.get(fn)(arg))
  }

  return {
    pyodide,
    run(code) {
      stray = []
      const outputs = call('_sf_run', code)
      if (stray.length) outputs.unshift({ kind: 'print', text: stray.join('\n') })
      return outputs
    },
    complete: (prefix) => call('_sf_complete', prefix),
    reset() { pyodide.globals.get('_sf_reset')() },
    /** Re-fetch the engine zip and start a fresh Session (Python modules reloaded). */
    reload: installEngine,
  }
}
