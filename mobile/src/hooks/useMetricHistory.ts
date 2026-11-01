import { useEffect, useState } from 'react';

import { baseUrl, getHistory, userMessage } from '../api/http';
import { snapshotMetrics } from '../protocol/metrics';
import type { HistoryPoint, MetricName, Range, SnapshotMessage } from '../protocol/types';
import type { SavedPc } from '../storage/storage';

const WINDOW_S: Record<Range, number> = { '15m': 900, '1h': 3600, '24h': 86400 };

/** Acrescenta um ponto mantendo a ordem e descartando o que saiu da janela. */
export function appendWindow(points: HistoryPoint[], point: HistoryPoint, windowS: number): HistoryPoint[] {
  const last = points[points.length - 1];
  if (last && point.t < last.t) return points;
  const base = last && last.t === point.t ? points.slice(0, -1) : points;
  return [...base, point].filter((p) => p.t >= point.t - windowS);
}

type Loaded = { key: string; points: HistoryPoint[]; error: string | null };

export function useMetricHistory(
  pc: SavedPc | null,
  metric: MetricName,
  range: Range,
  snapshot: SnapshotMessage | null,
) {
  const host = pc?.host;
  const port = pc?.port;
  const token = pc?.token;
  const key = `${host}:${port}:${token}:${metric}:${range}`;

  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [seen, setSeen] = useState<SnapshotMessage | null>(null);

  useEffect(() => {
    if (!host || !port || !token) return undefined;
    let active = true;
    getHistory(baseUrl(host, port), token, metric, range)
      .then((result) => {
        if (active) setLoaded({ key, points: result.points, error: null });
      })
      .catch((err: unknown) => {
        if (active) setLoaded({ key, points: [], error: userMessage(err) });
      });
    return () => {
      active = false;
    };
  }, [host, port, token, metric, range, key]);

  const current = loaded?.key === key ? loaded : null;

  // Leitura nova: acrescenta durante a renderizacao (padrao do React para estado derivado).
  if (snapshot !== seen) {
    setSeen(snapshot);
    const value = snapshot ? snapshotMetrics(snapshot.data)[metric] : undefined;
    const t = snapshot ? Date.parse(snapshot.t) / 1000 : Number.NaN;
    if (current && value !== undefined && Number.isFinite(t)) {
      setLoaded({ ...current, points: appendWindow(current.points, { t, avg: value, max: value }, WINDOW_S[range]) });
    }
  }

  return {
    points: current?.points ?? [],
    loading: current === null && Boolean(host && port && token),
    error: current?.error ?? null,
  };
}
