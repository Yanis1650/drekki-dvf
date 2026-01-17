# Project Analysis & Documentation (explore.data.gouv.fr)

## Overview
`explore.data.gouv.fr` is a Vue.js 2 application designed to visualize various public datasets, with a primary focus on DVF (Demandes de Valeurs Foncières - Real Estate Transactions). It functions as a monorepo containing multiple sub-applications located in `src/apps/`.

## Tech Stack
-   **Framework**: Vue.js 2 (`^2.7.14`)
-   **State Management**: Vuex
-   **Routing**: Vue Router
-   **Maps**: MapLibre GL JS
-   **UI**: BootstrapVue, @gouvfr/dsfr
-   **Charts**: Chart.js, D3 Scale
-   **Build Tool**: Vue CLI (Webpack)

## Data Architecture & APIs

### External APIs
The application communicates with several external services to fetch data:

1.  **DVF API** (`https://dvf-api.data.gouv.fr` or `VUE_APP_DVF_API`)
    *   **Purpose**: Core real estate transaction data.
    *   **Endpoints**:
        *   `/epci`: Fetches aggregate statistics for ChoroMap coloring.
        *   `/dvf?level={level}&code={code}`: Fetches transaction lists for the table view.
2.  **Geo API** (`https://geo.api.gouv.fr`)
    *   **Purpose**: Contextual geographical information (names of communes, departments, etc.).
    *   **Endpoints**:
        *   `/communes?code={code}`: Get commune name from code.
        *   `/communes?codePostal={code}`: Search by postal code.
        *   `/departements`, `/regions`: Fetch lists for search/filtering.
3.  **Tabular API** (`https://tabular-api.data.gouv.fr`)
    *   **Purpose**: Generic API for tabular resources on data.gouv.fr.
    *   **Usage**: Used in `tabular` app and `ExploreTableView.vue`.
4.  **Adresse API** (`https://api-adresse.data.gouv.fr`)
    *   **Purpose**: Geocoding and reverse geocoding.
    *   **Usage**: `Table.vue` generates links to the Base Adresse Nationale.
5.  **Recherche Entreprises** (`https://recherche-entreprises.api.gouv.fr`)
    *   **Purpose**: Search for companies (used in `Table.vue`).

### Deep Dive: Parcel Click Logic
When a user clicks on a parcel in the map (MapLibre), the following flow occurs:

1.  **Event Listener**: In `ChoroMap.vue`, a listener is attached to the `parcelles_fill` layer:
    ```javascript
    this.map.on("click", "parcelles_fill", (e) => { ... })
    ```
2.  **Visual Feedback**:
    *   The clicked parcel's ID is extracted: `let parcelleId = e.features[0]["properties"]["id"]`.
    *   A Paint Property update is triggered to highlight the selected parcel in red (`rgba(255, 0, 0, 0.5)`) while dimming others (`rgba(0, 0, 255, 0.2)`).
    ```javascript
    this.map.setPaintProperty("parcelles_fill", "fill-color", matchExpression);
    ```
3.  **State Update**:
    *   The component calls `changeLocation` which commits to the Vuex Store (`store/index.js`).
    *   Mutation: `changeUserLocation` updates `state.userLocation.parcelle` to the clicked ID.
    *   The level is set to `parcelle`.
4.  **Routing & Data Fetch**:
    *   The `userLocation` change is watched in `AppDvf.vue`.
    *   It triggers `updateActivePosition`, which pushes the new state to the URL Query Params (e.g., `?level=parcelle&code=...`).
    *   The `TableauView.vue` watches route changes and triggers a fetch to the DVF API (`/dvf?parcelle={id}`) to load the transactions for that specific parcel.

## Data Visualization & Formatting

### 1. Map Colors (`ChoroMap.vue`)
The choropleth map dynamically colors administrative areas (Communes, EPCIs) based on real estate data.
*   **Logic**:
    *   Fetches statistics (e.g., price/m²) from the API (`/epci`, `/communes`).
    *   Calculates statistical bounds: `Min`, `Max`, and `Median` (Pivot).
*   **D3.js Integration**:
    *   Uses `d3-scale` (`scaleLinear`) to generate a color gradient.
    *   **Domain**: `[min, median, max]`
    *   **Range**: `["#028758" (Green), "#FFF64E" (Yellow), "#CC000A" (Red)]`
*   **Rendering**:
    *   Constructs a massive Mapbox GL `match` expression containing `[feature_code, color]` pairs for every geometry.
    *   Applies this expression to the `fill-color` property of the relevant layer (e.g., `communes_fill`).

### 2. Tabular Data (`Table.vue`)
Displays list of transactions or resources.
*   **Structure**: standard HTML `<table>` with sticky headers.
*   **Data Source**: `store.state.rows` and `store.state.fields`.
*   **Pagination**: Handled by `changePage()` which queries the DVF API with `&page=N`.
*   **Export**: Generates a CSV download link pointing to `/dvf/csv/?...`.

### 3. Charts
Charts are implemented using `Chart.js` via wrapper components:
*   `Histogram.vue`: For price distribution.
*   `LineChart.vue`: For time-series analysis (e.g., price evolution over years).
*   `BarOrGraph.vue`: Generic bar/graph wrapper.

## Core Components Structure
*   `src/main.js`: Entry point, installs plugins (`VueResource`, `Meta`).
*   `src/router.js`: Maps routes like `/immobilier` to `AppDvf`.
*   `src/apps/dvf/AppDvf.vue`: Main layout for DVF. Manages "panels" (Map, Table, FAQ).
*   `src/apps/dvf/store/index.js`: Central store for DVF. Tracks `activePanel`, `mapProperties` (zoom, lat/lng), and `userLocation`.
*   `src/apps/dvf/views/MapView.vue`: Wrapper for the map view.
*   `src/apps/dvf/components/ChoroMap.vue`: Heavy component containing MapLibre initialization, layer definitions (fill/line for parcelles, communes), and interaction logic.

## Environment Variables
Key variables from `.env` (or `.env.sample`):
*   `VUE_APP_DVF_API`: Backend for DVF data.
*   `VUE_APP_TABULAR_API`: Backend for tabular data.
*   `VUE_APP_DATAGOUV_URL`: Link to main data.gouv.fr site.

## Commands
*   `npm run serve`: Start local dev server (Vue CLI).
*   `npm run build`: Build for production.
