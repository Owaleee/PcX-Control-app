// Protecao contra marcas na tela (burn-in): o painel anda alguns pixels em volta do centro.
const DIRECTIONS: readonly [number, number][] = [
  [0, 0],
  [1, 0],
  [1, 1],
  [0, 1],
  [-1, 1],
  [-1, 0],
  [-1, -1],
  [0, -1],
];

export function pixelShiftOffset(step: number, max = 4): { x: number; y: number } {
  const index = ((Math.trunc(step) % DIRECTIONS.length) + DIRECTIONS.length) % DIRECTIONS.length;
  const [dx, dy] = DIRECTIONS[index] ?? [0, 0];
  return { x: dx * max, y: dy * max };
}
