from flask import Flask, request, jsonify, send_file
import os
import razorpay
import requests
import hmac
import hashlib
import json
import qrcode
from io import BytesIO

app = Flask(__name__)

# Load keys from environment variables
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
WHATSAPP_TOKEN = os.getenv("EAAKqFTeha2oBPIVGfReqcdwGTrRN5lbWpD3j6SZBWkDreE4c8Lnr0DG8OippMugpA1ZBLZCUeJWGVNODDE8OVGNZAyORJzAHBXZCUeZBXAHPQm37ZAqIHOn3nsUejf4SmSNbbt6jIzFTK1RXZASOPg0loQFryLhBaGZAlWBzWNwOcZCgdc5bSDK2bODUtgeoZAT6vpOQRXRlok7AZA9pc43JwIWb6haZAEDd5A11qu0dDQYZBNRw4KOwZDZD")
WHATSAPP_PHONE_ID = os.getenv("744771188719813")
VERIFY_TOKEN = os.getenv("PrintingWalla")

# Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Temporary storage for mapping
pending_payments = {}
qr_codes = {}  # order_id -> QR code binary (BytesIO object)

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

def send_whatsapp_image(to, image_url, caption="Scan this QR to pay"):
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    requests.post(url, headers=headers, json=data)

# =========================
# WHATSAPP WEBHOOK
# =========================
@app.route("/whatsapp", methods=["GET", "POST"])
def whatsapp_webhook():
    if request.method == "GET":
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

                order_id = order["id"]
                payment_link = f"https://rzp.io/i/{order_id}"

                # Save user phone for follow-up
                pending_payments[order_id] = sender

                # Generate QR Code
                qr = qrcode.make(payment_link)
                buffer = BytesIO()
                qr.save(buffer, format="PNG")
                buffer.seek(0)
                qr_codes[order_id] = buffer

                # Send messages
                send_whatsapp_message(sender, f"Please complete your payment: {payment_link}")
                send_whatsapp_message(sender, f"Or scan the QR code below 👇")

                # Hosting the QR via dynamic endpoint
                send_whatsapp_image(sender, f"{request.url_root}qr/{order_id}")

            else:
                send_whatsapp_message(sender, "Hi! Send 'pay' to get a payment link and QR code.")
        except Exception as e:
            print("Error handling message:", e)

        return "EVENT_RECEIVED", 200

# =========================
# QR CODE IMAGE ENDPOINT
# =========================
@app.route("/qr/<order_id>")
def serve_qr(order_id):
    qr_buffer = qr_codes.get(order_id)
    if not qr_buffer:
        return "QR code not found", 404
    return send_file(qr_buffer, mimetype="image/png")

# =========================
# RAZORPAY WEBHOOK
# =========================
@app.route("/payment_webhook", methods=["POST"])
def payment_webhook():
    payload = request.data
    signature = request.headers.get("X-Razorpay-Signature")
    webhook_secret = RAZORPAY_KEY_SECRET

    try:
        hmac_obj = hmac.new(webhook_secret.encode(), payload, hashlib.sha256)
        expected_signature = hmac_obj.hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            return "Invalid signature", 400
    except Exception as e:
        print("Webhook verification failed:", e)
        return "Error", 400

    data = json.loads(payload)
    if data.get("event") == "payment.captured":
        order_id = data["payload"]["payment"]["entity"]["order_id"]
        customer_number = pending_payments.get(order_id)
        if customer_number:
            send_whatsapp_message(customer_number, "✅ Payment received! Thank you.")
            del pending_payments[order_id]
            qr_codes.pop(order_id, None)

    return jsonify({"status": "ok"}), 200

# =========================
# ROOT ENDPOINT
# =========================
@app.route("/")
def home():
    return "✅ WhatsApp + Razorpay Bot with QR Code is running!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
