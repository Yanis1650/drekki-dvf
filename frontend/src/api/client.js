import axios from 'axios';

const client = axios.create({
    baseURL: 'http://localhost:8000/api/v1',
    headers: {
        'Content-Type': 'application/json',
        'X-User-Id': 'demo_user_123', // Hardcoded for MVP
    },
});

export default client;
