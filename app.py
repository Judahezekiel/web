from flask import Flask, request, jsonify
import requests
import os
import json

app = Flask(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v19.0/YOUR_PHONE_NUMBER_ID/messages"
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")  # from .env
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")  # for webhook setup
RAZORPAY_API_KEY = os.getenv("RAZORPAY_API_KEY")
RAZORPAY_API_SECRET = os.getenv("RAZORPAY_API_SECRET")
QR_CODE_LINK = "https://api.razorpay.com/v1/payment_links"

user_data = {}
print_queue = []

# Verify webhook
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Unauthorized", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print(json.dumps(data, indent=2))

    if "messages" in data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}):
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        sender = message["from"]
        msg_text = message.get("text", {}).get("body", "").lower()

        if sender not in user_data:
            user_data[sender] = {}

        if msg_text.startswith("hi"):
            send_whatsapp_message(sender, "👋 Hi! Send your Room No. (e.g. 1105)")

        elif msg_text.isdigit() and len(msg_text) in [3, 4]:
            user_data[sender]["room"] = msg_text
            send_whatsapp_message(sender, "How many black & white pages? ₹2 per page")

        elif msg_text.isdigit():
            user_data[sender]["pages"] = int(msg_text)
            total = user_data[sender]["pages"] * 2
            if total >= 50:
                discount = total * 0.1
                total -= discount
            user_data[sender]["amount"] = round(total)

            # Create QR
            qr = create_payment_qr(sender, user_data[sender]["amount"])
            send_whatsapp_message(sender, f"Please scan to pay ₹{user_data[sender]['amount']}:")
            send_whatsapp_image(sender, qr)
            send_whatsapp_message(sender, "After payment, send the file to print 📄")

        elif "document" in message:
            filename = message["document"]["filename"]
            user_data[sender]["file"] = filename
            print_queue.append((user_data[sender]["room"], filename))
            print_queue.sort()
            send_whatsapp_message(sender, f"✅ File '{filename}' received and added to queue. We will print soon.")

    return "ok", 200

def send_whatsapp_message(to, text):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    requests.post(WHATSAPP_API_URL, headers=headers, json=payload)

def send_whatsapp_image(to, image_url):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"link": image_url},
    }
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    requests.post(WHATSAPP_API_URL, headers=headers, json=payload)

def create_payment_qr(phone_number, amount):
    payload = {
        "amount": amount * 100,
        "currency": "INR",
        "description": f"Print Payment for {phone_number}",
        "customer": {"contact": phone_number[-10:]},
        "notify": {"sms": False, "email": False},
        "callback_url": "https://yourdomain.com/payment-callback",
        "callback_method": "get"
    }
    response = requests.post(QR_CODE_LINK, auth=(RAZORPAY_API_KEY, RAZORPAY_API_SECRET), json=payload)
    return response.json()["short_url"]

if __name__ == "__main__":
    app.run(debug=True)
