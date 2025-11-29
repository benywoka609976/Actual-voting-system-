# UnivVote Prototype (with Mock Daraja)

This repository contains a prototype university voting system with MPESA donation endpoints and a **local mock Daraja server** for full STK Push simulation without real credentials.

## Quick local run (mock enabled)
1. copy .env.example to .env and set USE_MOCK_MPESA=1 (default in example)
2. Build & run both services:
   ```bash
   docker-compose up --build
   ```
3. App: http://localhost:5000
   Mock Daraja: http://localhost:5005

## Testing MPESA flow (local)
1. Initiate STK push:
   POST http://localhost:5000/mpesa/stkpush
   Body: { "phone": "254700000000", "amount": 100, "account_ref": "DEV" }

2. Simulate Daraja callback and forward to webhook:
   POST http://localhost:5000/mpesa/simulate_callback
   Body: { "donation_id": 1, "amount": 100 }

## Notes
- This is a prototype. Secure secrets for production.
- Webhook endpoints must be HTTPS in production.
