from flask import Flask, request, jsonify
import time, random
app = Flask(__name__)

@app.route("/oauth/v1/generate", methods=["GET"])
def oauth():
    return jsonify({
        "access_token": "mock_access_token_123",
        "expires_in": "3600"
    })

@app.route("/mpesa/stkpush/v1/processrequest", methods=["POST"])
def stkpush():
    data = request.json
    return jsonify({
        "MerchantRequestID": f"MR{random.randint(1000,9999)}",
        "CheckoutRequestID": f"CR{random.randint(1000,9999)}",
        "ResponseCode": "0",
        "ResponseDescription": "Success. Request accepted for processing",
        "CustomerMessage": "STK push simulated"
    })

@app.route("/simulate_callback", methods=["POST"])
def simulate_callback():
    payload = request.json
    return jsonify({
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "12345",
                "CheckoutRequestID": "67890",
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": payload.get("amount")},
                        {"Name": "MpesaReceiptNumber", "Value": "MOCK123"},
                        {"Name": "PhoneNumber", "Value": "254700000000"}
                    ]
                }
            }
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)
