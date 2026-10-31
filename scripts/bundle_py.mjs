// Zips py/symflex_maple into public/symflex_maple.zip for the Pyodide worker.
// Tiny stored/deflate zip writer on node:zlib so no extra dependency is needed.
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { crc32, deflateRawSync } from 'node:zlib'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
export const PY_DIR = join(root, 'py', 'symflex_maple')
const OUT = join(root, 'public', 'symflex_maple.zip')

function* walk(dir) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (e.name === '__pycache__' || e.name.startsWith('.')) continue
    const p = join(dir, e.name)
    if (e.isDirectory()) yield* walk(p)
    else if (!e.name.endsWith('.pyc')) yield p
  }
}

/** Build a zip archive from [{name, data}] entries. */
export function makeZip(entries) {
  const locals = [], centrals = []
  let offset = 0
  for (const { name, data } of entries) {
    const nameBuf = Buffer.from(name, 'utf8')
    const comp = deflateRawSync(data)
    const crc = crc32(data)
    const head = Buffer.alloc(30)
    head.writeUInt32LE(0x04034b50, 0)
    head.writeUInt16LE(20, 4)        // version needed
    head.writeUInt16LE(0x0800, 6)    // utf-8 names
    head.writeUInt16LE(8, 8)         // deflate
    head.writeUInt32LE(0x00210000, 10) // fixed dos time/date (1980-01-01) for reproducible zips
    head.writeUInt32LE(crc, 14)
    head.writeUInt32LE(comp.length, 18)
    head.writeUInt32LE(data.length, 22)
    head.writeUInt16LE(nameBuf.length, 26)
    locals.push(head, nameBuf, comp)
    const cen = Buffer.alloc(46)
    cen.writeUInt32LE(0x02014b50, 0)
    cen.writeUInt16LE(20, 4)
    cen.writeUInt16LE(20, 6)
    cen.writeUInt16LE(0x0800, 8)
    cen.writeUInt16LE(8, 10)
    cen.writeUInt32LE(0x00210000, 12)
    cen.writeUInt32LE(crc, 16)
    cen.writeUInt32LE(comp.length, 20)
    cen.writeUInt32LE(data.length, 24)
    cen.writeUInt16LE(nameBuf.length, 28)
    cen.writeUInt32LE(offset, 42)
    centrals.push(cen, nameBuf)
    offset += 30 + nameBuf.length + comp.length
  }
  const cenSize = centrals.reduce((n, b) => n + b.length, 0)
  const end = Buffer.alloc(22)
  end.writeUInt32LE(0x06054b50, 0)
  end.writeUInt16LE(entries.length, 8)
  end.writeUInt16LE(entries.length, 10)
  end.writeUInt32LE(cenSize, 12)
  end.writeUInt32LE(offset, 16)
  return Buffer.concat([...locals, ...centrals, end])
}

/** Returns true when the zip was written, false when py/symflex_maple does not exist yet. */
export function bundlePy({ quiet = false } = {}) {
  if (!existsSync(PY_DIR)) {
    if (!quiet) console.warn('bundle_py: py/symflex_maple not found, skipping')
    return false
  }
  const base = dirname(PY_DIR)
  const entries = [...walk(PY_DIR)].sort().map((p) => ({
    name: relative(base, p).split(sep).join('/'),
    data: readFileSync(p),
  }))
  mkdirSync(dirname(OUT), { recursive: true })
  writeFileSync(OUT, makeZip(entries))
  if (!quiet) console.log(`bundle_py: ${entries.length} files -> public/symflex_maple.zip`)
  return true
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) bundlePy()
