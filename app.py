from flask import Flask, request, jsonify
import os
import razorpay
import requests
import hmac
import hashlib
import json

app = Flask(__name__)

# Load keys from environment variables
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
WHATSAPP_TOKEN = os.getenv("EAAKqFTeha2oBPIVGfReqcdwGTrRN5lbWpD3j6SZBWkDreE4c8Lnr0DG8OippMugpA1ZBLZCUeJWGVNODDE8OVGNZAyORJzAHBXZCUeZBXAHPQm37ZAqIHOn3nsUejf4SmSNbbt6jIzFTK1RXZASOPg0loQFryLhBaGZAlWBzWNwOcZCgdc5bSDK2bODUtgeoZAT6vpOQRXRlok7AZA9pc43JwIWb6haZAEDd5A11qu0dDQYZBNRw4KOwZDZD")
WHATSAPP_PHONE_ID = os.getenv("744771188719813")
VERIFY_TOKEN = os.getenv("PrintingWalla")

# Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Store phone-payment mapping temporarily (in-memory, use DB in production)
pending_payments = {}

# =========================
# SEND WHATSAPP MESSAGE
# =========================
def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    response = requests.post(url, headers=headers, json=payload)
    print(f"[WhatsApp] Sent to {to}: {text}")
    return response.status_code

# =========================
# WHATSAPP WEBHOOK
# =========================
@app.route("/whatsapp", methods=["GET", "POST"])
def whatsapp_webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Invalid verification token", 403

    if request.method == "POST":
        data = request.json
        print("[Webhook Received]", json.dumps(data, indent=2))

        try:
            message = data["entry"][0]["changes"][0]["value"]["messages"][0]
            sender = message["from"]
            text = message["text"]["body"].strip().lower()

            if text == "pay":
                if sender in pending_payments.values():
                    send_whatsapp_message(sender, "🕓 You already have a pending payment. Please complete it.")
                else:
                    amount = 5000  # in paise (₹50)
                    order = razorpay_client.order.create({
                        "amount": amount,
                        "currency": "INR",
                        "payment_capture": 1
                    })
                    pending_payments[order["id"]] = sender
                    payment_url = f"https://rzp.io/i/{order['id']}"
                    send_whatsapp_message(sender, f"💳 Click to pay ₹50: {payment_url}")

            elif text == "help":
                send_whatsapp_message(sender, "💬 Commands:\n- Type `pay` to get payment link\n- Type `status` to check payment")

            elif text == "status":
                matching = [k for k, v in pending_payments.items() if v == sender]
                if matching:
                    send_whatsapp_message(sender, "💡 Your payment is still pending. Please complete it.")
                else:
                    send_whatsapp_message(sender, "✅ No pending payments found.")

            else:
                send_whatsapp_message(sender, "👋 Hi there! Type `pay` to start payment.")

        except Exception as e:
            print("❌ Error:", e)

        return "EVENT_RECEIVED", 200

# =========================
# RAZORPAY PAYMENT WEBHOOK
# =========================
@app.route("/payment_webhook", methods=["POST"])
def payment_webhook():
    payload = request.data
    received_signature = request.headers.get("X-Razorpay-Signature")
    webhook_secret = RAZORPAY_KEY_SECRET  # Use a separate webhook secret in production

    # Verify signature
    try:
        hmac_obj = hmac.new(webhook_secret.encode(), payload, hashlib.sha256)
        expected_signature = hmac_obj.hexdigest()

        if not hmac.compare_digest(received_signature, expected_signature):
            print("❌ Invalid signature")
            return "Invalid signature", 400

    except Exception as e:
        print("❌ Signature error:", e)
        return "Signature error", 400

    # Process payment event
    event = json.loads(payload)
    if event.get("event") == "payment.captured":
        payment = event["payload"]["payment"]["entity"]
        order_id = payment.get("order_id")
        customer = pending_payments.get(order_id)

        if customer:
            send_whatsapp_message(customer, f"✅ Payment received of ₹{int(payment['amount'])/100:.2f}! Thank you.")
            del pending_payments[order_id]

    return jsonify({"status": "success"}), 200

# =========================
# DEFAULT ROUTE
# =========================
@app.route("/")
def root():
    return "✅ WhatsApp + Razorpay App is running!", 200

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
