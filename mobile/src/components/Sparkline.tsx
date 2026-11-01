import Svg, { Path } from 'react-native-svg';

const round = (v: number) => Math.round(v * 100) / 100;

/** Caminho SVG da linha (M x y L x y ...). Valores limitados a [min, max]. */
export function sparklinePath(values: number[], width: number, height: number, min = 0, max = 100): string {
  if (values.length === 0) return '';
  const span = max - min;
  const y = (v: number) => {
    if (span <= 0) return height;
    const clamped = Math.min(max, Math.max(min, v));
    return round(height - ((clamped - min) / span) * height);
  };
  if (values.length === 1) {
    const only = y(values[0] ?? min);
    return `M0 ${only} L${round(width)} ${only}`;
  }
  const step = width / (values.length - 1);
  return values.map((v, i) => `${i === 0 ? 'M' : 'L'}${round(i * step)} ${y(v)}`).join(' ');
}

type Props = { values: number[]; width?: number; height?: number; color: string; min?: number; max?: number };

export function Sparkline({ values, width = 100, height = 36, color, min = 0, max = 100 }: Props) {
  return (
    <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <Path
        d={sparklinePath(values, width, height, min, max)}
        stroke={color}
        strokeWidth={2}
        fill="none"
        vectorEffect="non-scaling-stroke"
      />
    </Svg>
  );
}
