from flask import Flask, request, jsonify
import os
import razorpay
import requests
import hmac
import hashlib
import json

app = Flask(__name__)

# Load keys
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
WHATSAPP_TOKEN = os.getenv("EAAKqFTeha2oBPIVGfReqcdwGTrRN5lbWpD3j6SZBWkDreE4c8Lnr0DG8OippMugpA1ZBLZCUeJWGVNODDE8OVGNZAyORJzAHBXZCUeZBXAHPQm37ZAqIHOn3nsUejf4SmSNbbt6jIzFTK1RXZASOPg0loQFryLhBaGZAlWBzWNwOcZCgdc5bSDK2bODUtgeoZAT6vpOQRXRlok7AZA9pc43JwIWb6haZAEDd5A11qu0dDQYZBNRw4KOwZDZD")
WHATSAPP_PHONE_ID = os.getenv("744771188719813")
VERIFY_TOKEN = os.getenv("PrintingWalla")

# Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Store phone-payment map temporarily (use DB in production)
pending_payments = {}

# =========================
# WHATSAPP FUNCTIONS
# =========================
def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": text}
    }
    requests.post(url, headers=headers, json=data)

# =========================
# WHATSAPP WEBHOOK
# =========================
@app.route("/whatsapp", methods=["GET", "POST"])
def whatsapp_webhook():
    if request.method == "GET":
        # Verification challenge
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Invalid verification token", 403

    elif request.method == "POST":
        data = request.json
        try:
            message = data["entry"][0]["changes"][0]["value"]["messages"][0]
            sender = message["from"]
            text = message["text"]["body"].strip().lower()

            if text == "pay":
                order_amount = 5000  # ₹50.00 in paise
                order = razorpay_client.order.create({
                    "amount": order_amount,
                    "currency": "INR",
                    "payment_capture": 1
                })
                pending_payments[order["id"]] = sender
                payment_link = f"https://rzp.io/i/{order['id']}"  # Short link if you have one
                send_whatsapp_message(sender, f"Please complete your payment here: {payment_link}")

            else:
                send_whatsapp_message(sender, "Hello! Send 'pay' to get a payment link.")
        except Exception as e:
            print("Error processing WhatsApp message:", e)

        return "EVENT_RECEIVED", 200

# =========================
# RAZORPAY WEBHOOK
# =========================
@app.route("/payment_webhook", methods=["POST"])
def payment_webhook():
    payload = request.data
    signature = request.headers.get("X-Razorpay-Signature")
    webhook_secret = RAZORPAY_KEY_SECRET  # Use separate secret for webhook ideally

    # Verify signature
    try:
        hmac_obj = hmac.new(webhook_secret.encode(), payload, hashlib.sha256)
        expected_signature = hmac_obj.hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            return "Invalid signature", 400
    except Exception as e:
        print("Signature verification failed:", e)
        return "Error", 400

    data = json.loads(payload)
    if data.get("event") == "payment.captured":
        order_id = data["payload"]["payment"]["entity"]["order_id"]
        customer_number = pending_payments.get(order_id)
        if customer_number:
            send_whatsapp_message(customer_number, "✅ Payment received! Thank you.")
            del pending_payments[order_id]

    return jsonify({"status": "ok"}), 200

# =========================
# ROOT
# =========================
@app.route("/")
def home():
    return "WhatsApp + Razorpay bot running!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
