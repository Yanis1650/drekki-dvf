import axios from 'axios';

// Prod (VITE_API_BASE_URL=/api/v1) : URLs relatives via nginx proxy
// Dev : fallback localhost:8000
const client = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
    headers: {
        'Content-Type': 'application/json',
    },
});

export default client;
