import { ref, watch, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

/**
 * Composable for managing parcel selection state with URL synchronization
 * Inspired by DVF government app's deep linking implementation
 * 
 * Features:
 * - Automatic URL sync (?parcelle=ID)
 * - Browser history integration (back/forward buttons work)
 * - Shareable links
 * 
 * @returns {Object} Selection state and methods
 */
export function useParcelSelection() {
    const route = useRoute();
    const router = useRouter();

    // Core state
    const selectedParcelId = ref(null);
    const selectedParcelData = ref(null);
    const isLoading = ref(false);

    // Computed for easy template binding
    const hasSelection = computed(() => selectedParcelId.value !== null);

    /**
     * Sync selection to URL query params
     * Triggers on every selection change
     */
    watch(selectedParcelId, (newId) => {
        const query = { ...route.query };

        if (newId) {
            query.parcelle = newId;
        } else {
            delete query.parcelle;
        }

        // Use replace to avoid cluttering history with every click
        router.replace({ query }).catch(() => {
            // Ignore navigation errors (e.g., same route)
        });
    });

    /**
     * Restore selection from URL on component mount
     */
    onMounted(() => {
        const parcelleFromUrl = route.query.parcelle;
        if (parcelleFromUrl && typeof parcelleFromUrl === 'string') {
            selectedParcelId.value = parcelleFromUrl;
        }
    });

    /**
     * Select a parcel
     * @param {string} id - Parcel ID (14 characters)
     * @param {Object} data - Optional parcel feature data
     */
    const selectParcel = (id, data = null) => {
        selectedParcelId.value = id;
        selectedParcelData.value = data;
    };

    /**
     * Clear current selection
     */
    const clearSelection = () => {
        selectedParcelId.value = null;
        selectedParcelData.value = null;
    };

    /**
     * Generate MapLibre match expression for highlighting selected parcel
     * @param {string} defaultColor - Color for non-selected parcels
     * @param {string} selectedColor - Color for selected parcel
     * @returns {Array} MapLibre style expression
     */
    const getHighlightExpression = (defaultColor = 'rgba(0, 0, 255, 0.2)', selectedColor = 'rgba(239, 68, 68, 0.6)') => {
        if (!selectedParcelId.value) {
            return defaultColor;
        }

        return [
            'case',
            ['==', ['get', 'id_parcelle'], selectedParcelId.value],
            selectedColor,
            defaultColor
        ];
    };

    /**
     * Generate MapLibre match expression for border highlighting
     * @returns {Array|number} MapLibre style expression for line-width
     */
    const getHighlightBorderWidth = () => {
        if (!selectedParcelId.value) {
            return 1.5;
        }

        return [
            'case',
            ['==', ['get', 'id_parcelle'], selectedParcelId.value],
            4,
            1.5
        ];
    };

    return {
        // State
        selectedParcelId,
        selectedParcelData,
        isLoading,
        hasSelection,

        // Methods
        selectParcel,
        clearSelection,

        // MapLibre helpers
        getHighlightExpression,
        getHighlightBorderWidth
    };
}
