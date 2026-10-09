/* Multiply physical waypoint speeds, never the normalized export ratios. */
(function (root) {
  function scaleSpeeds(speeds, indices, factor, minimum, maximum) {
    if (!Number.isFinite(factor) || factor <= 0 || !Number.isFinite(minimum) ||
        !Number.isFinite(maximum) || minimum > maximum) throw new Error('Invalid speed multiplier');
    const result = speeds.slice();
    for (const i of new Set(indices)) {
      if (!Number.isInteger(i) || i < 0 || i >= speeds.length || !Number.isFinite(speeds[i])) {
        throw new Error('Invalid waypoint selection');
      }
      result[i] = Math.max(minimum, Math.min(maximum, speeds[i] * factor));
    }
    return result;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {scaleSpeeds};
  else root.speedMath = {scaleSpeeds};
})(typeof window !== 'undefined' ? window : globalThis);
