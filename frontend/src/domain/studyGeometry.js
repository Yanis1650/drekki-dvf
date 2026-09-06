// Spherical destination points, WGS84, radius in metres.
export function studyBoundary([lon, lat], radius) {
  const rad = Math.PI / 180, d = radius / 6371000, phi = lat * rad, lambda = lon * rad;
  const coordinates = Array.from({ length: 65 }, (_, i) => {
    const bearing = i / 64 * Math.PI * 2;
    const p = Math.asin(Math.sin(phi) * Math.cos(d) + Math.cos(phi) * Math.sin(d) * Math.cos(bearing));
    const l = lambda + Math.atan2(Math.sin(bearing) * Math.sin(d) * Math.cos(phi), Math.cos(d) - Math.sin(phi) * Math.sin(p));
    return [l / rad, p / rad];
  });
  coordinates[64] = [...coordinates[0]];
  return { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [coordinates] } };
}
