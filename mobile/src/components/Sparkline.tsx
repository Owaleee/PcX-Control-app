import Svg, { Path } from 'react-native-svg';

export type SeriesPoint = { t: number; v: number };

const round = (v: number) => Math.round(v * 100) / 100;

/**
 * Caminho SVG (M x y L x y ...) com o eixo X pelo tempo.
 * `span` (segundos) fixa a janela que termina no ultimo ponto; sem ele, vai do 1o ao ultimo ponto.
 */
export function sparklinePath(
  points: SeriesPoint[],
  width: number,
  height: number,
  min = 0,
  max = 100,
  span?: number,
): string {
  if (points.length === 0) return '';
  const range = max - min;
  const y = (v: number) => {
    if (range <= 0) return height;
    const clamped = Math.min(max, Math.max(min, v));
    return round(height - ((clamped - min) / range) * height);
  };
  if (points.length === 1) {
    const only = y(points[0]?.v ?? min);
    return `M0 ${only} L${round(width)} ${only}`;
  }
  const end = points[points.length - 1]?.t ?? 0;
  const start = span !== undefined ? end - span : (points[0]?.t ?? 0);
  const total = end - start;
  const x = (t: number) => (total <= 0 ? width : round(Math.max(0, ((t - start) / total) * width)));
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.t)} ${y(p.v)}`).join(' ');
}

type Props = {
  points: SeriesPoint[];
  width?: number;
  height?: number;
  color: string;
  min?: number;
  max?: number;
  span?: number;
};

export function Sparkline({ points, width = 100, height = 36, color, min = 0, max = 100, span }: Props) {
  return (
    <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <Path
        d={sparklinePath(points, width, height, min, max, span)}
        stroke={color}
        strokeWidth={2}
        fill="none"
        vectorEffect="non-scaling-stroke"
      />
    </Svg>
  );
}
