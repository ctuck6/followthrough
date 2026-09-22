export function executionMarkers(candles, executions) {
  const times = new Set(candles.map(candle => candle.time));
  return executions.flatMap(fill => {
    const time = Math.floor(fill.time / 60) * 60;
    if (!times.has(time)) return [];
    return [{time, position: fill.side === 'BUY' ? 'belowBar' : 'aboveBar',
      color: fill.side === 'BUY' ? '#46956a' : '#cc6969',
      shape: fill.side === 'BUY' ? 'arrowUp' : 'arrowDown',
      text: `${fill.kind} ${Number(fill.quantity)}`, id: fill.id}];
  }).sort((a, b) => a.time - b.time);
}
