import os
import json
import uuid
import razorpay
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configuration
WHATSAPP_API_URL = "https://graph.facebook.com/v19.0/744771188719813/messages"
ACCESS_TOKEN = os.getenv("EAAKqFTeha2oBPIVGfReqcdwGTrRN5lbWpD3j6SZBWkDreE4c8Lnr0DG8OippMugpA1ZBLZCUeJWGVNODDE8OVGNZAyORJzAHBXZCUeZBXAHPQm37ZAqIHOn3nsUejf4SmSNbbt6jIzFTK1RXZASOPg0loQFryLhBaGZAlWBzWNwOcZCgdc5bSDK2bODUtgeoZAT6vpOQRXRlok7AZA9pc43JwIWb6haZAEDd5A11qu0dDQYZBNRw4KOwZDZD")
VERIFY_TOKEN = os.getenv("PrintWalla")
RAZORPAY_API_KEY = os.getenv("RAZORPAY_API_KEY")
RAZORPAY_API_SECRET = os.getenv("RAZORPAY_API_SECRET")
QR_CODE_LINK = "https://api.razorpay.com/v1/payment_links"

# Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_API_KEY, RAZORPAY_API_SECRET))

# Temporary in-memory storage (replace with database for production)
orders = {}

# Webhook verification for WhatsApp
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Verification failed", 403

    if request.method == "POST":
        data = request.get_json()
        try:
            phone_number = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
            send_payment_link(phone_number)
        except Exception as e:
            print("Webhook processing error:", e)
        return "EVENT_RECEIVED", 200

# Send payment link via WhatsApp
def send_payment_link(phone_number):
    order_id = str(uuid.uuid4())  # Unique order ID per customer
    amount = 5000  # Amount in paise (₹50)
    payment_link = razorpay_client.payment_link.create({
        "amount": amount,
        "currency": "INR",
        "description": f"Payment for Order {order_id}",
        "customer": {"contact": phone_number, "name": "Customer"},
        "callback_url": "https://web-wn9p.onrender.com/payment-success",
        "callback_method": "get"
    })

    orders[order_id] = {"phone_number": phone_number, "payment_id": None, "status": "pending"}

    message_data = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": f"Please complete your payment here: {payment_link['short_url']}"}
    }
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    requests.post(WHATSAPP_API_URL, headers=headers, json=message_data)

# Razorpay webhook to confirm payment
@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    data = request.get_json()
    try:
        payment_id = data["payload"]["payment"]["entity"]["id"]
        order_id = data["payload"]["payment"]["entity"]["notes"].get("order_id")
        status = data["payload"]["payment"]["entity"]["status"]

        if order_id in orders:
            orders[order_id]["payment_id"] = payment_id
            orders[order_id]["status"] = status
            if status == "captured":
                send_whatsapp_message(orders[order_id]["phone_number"], "✅ Payment received! Thank you.")
        return jsonify({"status": "ok"})
    except Exception as e:
        print("Webhook error:", e)
        return jsonify({"error": str(e)}), 400

# Helper: Send message via WhatsApp
def send_whatsapp_message(phone_number, message):
    message_data = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message}
    }
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    requests.post(WHATSAPP_API_URL, headers=headers, json=message_data)

if __name__ == "__main__":
    app.run(debug=True)
