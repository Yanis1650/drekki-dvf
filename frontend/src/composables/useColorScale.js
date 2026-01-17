import { scaleLinear } from 'd3-scale';

/**
 * Composable for creating dynamic D3-based color scales
 * Inspired by DVF government app's choropleth implementation
 * 
 * @param {Object} options Configuration options
 * @param {number[]} options.domain - Array of domain values [min, median, max]
 * @param {string[]} options.range - Array of color values matching domain points
 * @returns {Object} Scale utilities
 */
export function useColorScale(options = {}) {
    const {
        // Default: prix/m² scale (green=cheap, yellow=medium, red=expensive)
        domain = [1000, 5000, 10000],
        range = ['#22c55e', '#eab308', '#ef4444']
    } = options;

    // Create D3 linear scale
    const scale = scaleLinear()
        .domain(domain)
        .range(range)
        .clamp(true); // Clamp values outside domain

    /**
     * Get color for a single value
     * @param {number} value
     * @returns {string} Hex color
     */
    const getColor = (value) => scale(value);

    /**
     * Generate MapLibre GL expression for data-driven styling
     * @param {string} property - GeoJSON property name to read value from
     * @returns {Array} MapLibre expression
     */
    const getMapLibreExpression = (property) => {
        // Build interpolate expression dynamically from domain/range
        const stops = [];
        for (let i = 0; i < domain.length; i++) {
            stops.push(domain[i], range[i]);
        }

        return [
            'interpolate',
            ['linear'],
            ['coalesce', ['get', property], domain[1]], // Default to median
            ...stops
        ];
    };

    /**
     * Generate legend data for UI display
     * @returns {Array} Array of {value, color, label} objects
     */
    const getLegendItems = () => {
        return domain.map((val, idx) => ({
            value: val,
            color: range[idx],
            label: `${val.toLocaleString('fr-FR')} €/m²`
        }));
    };

    /**
     * Reconfigure the scale with new domain/range
     * @param {number[]} newDomain
     * @param {string[]} newRange
     */
    const reconfigure = (newDomain, newRange) => {
        scale.domain(newDomain);
        if (newRange) scale.range(newRange);
    };

    return {
        scale,
        getColor,
        getMapLibreExpression,
        getLegendItems,
        reconfigure
    };
}

// Pre-configured scales for common use cases
export const prixScale = () => useColorScale({
    domain: [1000, 3000, 5000, 7000, 10000],
    range: ['#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444']
});

export const zanScale = () => useColorScale({
    domain: [0, 0.5, 1],
    range: ['#ef4444', '#eab308', '#22c55e']
});
