/**
 * MapLibre color schemes for prix, zan and urbanisme modes.
 * Used by MapContainer for parcel and point styling.
 */
export const mapColorSchemes = {
  prix: {
    parcelles: [
      'interpolate', ['linear'],
      ['coalesce', ['get', 'prix_m2_moyen'], 3000],
      1000, '#22c55e', 3000, '#84cc16', 5000, '#eab308',
      7000, '#f97316', 10000, '#ef4444'
    ],
    points: [
      'interpolate', ['linear'], ['get', 'prix_m2'],
      1000, '#22c55e', 3000, '#84cc16', 5000, '#eab308',
      7000, '#f97316', 10000, '#ef4444', 15000, '#dc2626'
    ]
  },
  zan: {
    parcelles: [
      'match', ['get', 'densification_categorie'],
      'FORT', '#10b981', 'MOYEN', '#eab308', 'FAIBLE', '#f97316',
      'SATURE', '#ef4444', '#94a3b8'
    ],
    points: [
      'interpolate', ['linear'], ['coalesce', ['get', 'zan_score'], 0.5],
      0, '#ef4444', 0.3, '#f97316', 0.5, '#eab308',
      0.7, '#22c55e', 1, '#059669'
    ]
  },
  urbanisme: {
    parcelles: [
      'match', ['get', 'zone_plu'],
      'U', '#f59e0b', 'AU', '#f97316', 'N', '#22c55e',
      'A', '#84cc16', '#94a3b8'
    ],
    points: [
      'interpolate', ['linear'], ['get', 'prix_m2'],
      1000, '#22c55e', 5000, '#eab308', 10000, '#ef4444'
    ],
    opacity: 0.4
  }
};
