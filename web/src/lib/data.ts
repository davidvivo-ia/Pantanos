/**
 * Data loader for Astro static site generation.
 * Reads JSON committed in `data/` and exposes typed accessors.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.resolve(__dirname, '../../../data');

export interface LevelPoint {
  date: string;
  volume_hm3: number;
  pct: number | null;
}

export interface RainfallPoint {
  date: string;
  mm: number | null;
  source?: string;
  station?: string;
  distance_km?: number;
}

export interface SaihPoint {
  ts: string;
  level_m?: number | null;
  volume_hm3?: number | null;
  pct?: number | null;
  outflow_m3s?: number | null;
  inflow_m3s?: number | null;
  source?: string;
}

export interface Reservoir {
  id: string;
  name: string;
  basin: string;
  basin_name: string;
  is_hydroelectric: boolean;
  capacity_hm3: number;
  first_record?: string;
  last_record?: string;
  levels: LevelPoint[];
  rainfall_local: RainfallPoint[];
  saih: SaihPoint[];
  last_updated: string;
  sources: string[];
}

export interface ReservoirMeta {
  id: string;
  name?: string;
  coords?: [number, number] | null;
  river?: string | null;
  province?: string | null;
  ccaa?: string | null;
  dam?: { type?: string | null; height_m?: number | null; length_m?: number | null; year?: string | number | null };
  capacity_hm3?: number | null;
  surface_ha?: number | null;
  wikipedia_url?: string | null;
  wikidata_id?: string | null;
  history?: { extract_html: string; extract: string; url: string; license: string } | null;
  photo?: { url: string; credit: string; source_url: string } | null;
  osm?: { type: string; id: number; url: string };
  source?: string;
}

export interface Route {
  osm_id: string;
  name: string;
  ref?: string | null;
  network?: string | null;
  sac_scale?: string | null;
  operator?: string | null;
  length_km: number;
  url: string;
  track?: [number, number][];
}

export interface Routes {
  id: string;
  fetched: string;
  search_radius_km: number;
  n: number;
  routes: Route[];
}

export interface BasinAggregate {
  id: string;
  name: string;
  n_reservoirs: number;
  capacity_hm3: number;
  current_hm3: number;
  pct: number | null;
  last_updated: string;
  history: { date: string; current_hm3: number; pct: number | null }[];
}

export interface Summary {
  generated: string;
  snapshot_date: string;
  national: { capacity_hm3: number; current_hm3: number; pct: number; n_reservoirs: number };
  reservoirs: Array<{
    id: string;
    name: string;
    basin: string;
    basin_name: string;
    capacity_hm3: number;
    volume_hm3: number;
    pct: number | null;
    date: string;
  }>;
}

function readJson<T>(p: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8')) as T;
  } catch {
    return null;
  }
}

export function getSummary(): Summary {
  const s = readJson<Summary>(path.join(DATA_DIR, 'summary.json'));
  if (!s) throw new Error('data/summary.json missing — run scrapers first');
  return s;
}

export function listReservoirSlugs(): string[] {
  return fs
    .readdirSync(path.join(DATA_DIR, 'reservoirs'))
    .filter((f) => f.endsWith('.json') && !f.endsWith('.meta.json') && !f.endsWith('.routes.json'))
    .map((f) => f.replace(/\.json$/, ''));
}

export function getReservoir(slug: string): Reservoir {
  const r = readJson<Reservoir>(path.join(DATA_DIR, 'reservoirs', `${slug}.json`));
  if (!r) throw new Error(`reservoir ${slug} not found`);
  return r;
}

export function getReservoirMeta(slug: string): ReservoirMeta | null {
  return readJson<ReservoirMeta>(path.join(DATA_DIR, 'reservoirs', `${slug}.meta.json`));
}

export function getReservoirRoutes(slug: string): Routes | null {
  return readJson<Routes>(path.join(DATA_DIR, 'reservoirs', `${slug}.routes.json`));
}

export function listBasins(): BasinAggregate[] {
  const dir = path.join(DATA_DIR, 'basins');
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith('.json'))
    .map((f) => readJson<BasinAggregate>(path.join(dir, f))!)
    .filter(Boolean)
    .sort((a, b) => b.capacity_hm3 - a.capacity_hm3);
}

export function getBasin(slug: string): BasinAggregate | null {
  return readJson<BasinAggregate>(path.join(DATA_DIR, 'basins', `${slug}.json`));
}

export function getNationalRainfall(): { fetched: string; n: number; observations: any[] } | null {
  return readJson(path.join(DATA_DIR, 'rainfall', 'national.json'));
}

export function fmt(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return n.toLocaleString('es-ES', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function colorForPct(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return '#94a3b8';
  if (pct < 25) return '#dc2626';   // rojo
  if (pct < 50) return '#f59e0b';   // ámbar
  if (pct < 75) return '#eab308';   // amarillo
  if (pct < 90) return '#22c55e';   // verde
  return '#0284c7';                  // azul (lleno)
}
