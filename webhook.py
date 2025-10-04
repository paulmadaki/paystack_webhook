from flask import Flask, request, jsonify
import hmac, hashlib, os
import requests

app = Flask(_name_)
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")

@app.route('/')
def home():
    return 'Webhook server is live and ready!'

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_data()
    signature = request.headers.get('x-paystack-signature')

    print("📩 Received webhook request.")
    print("Headers:", dict(request.headers))
    print("Raw payload:", payload)

    if not PAYSTACK_SECRET:
        print("⚠ PAYSTACK_SECRET is missing from environment variables.")
        return jsonify({'status': 'server_error'}), 500

    computed_signature = hmac.new(
        PAYSTACK_SECRET.encode(),
        msg=payload,
        digestmod=hashlib.sha512
    ).hexdigest()

    if signature != computed_signature:
        print("❌ Signature mismatch! Unauthorized request.")
        return jsonify({'status': 'unauthorized'}), 401

    print("✅ Signature verified successfully.")

    data = request.json
    event = data.get('event')
    reference = data['data'].get('reference')
    email = data['data'].get('customer', {}).get('email')

    print(f"Event: {event}, Reference: {reference}, Email: {email}")

    if event == 'charge.success' and email:
        print("🔄 Updating Supabase record for:", email)
        update_supabase(email, reference)
        print("✅ Supabase update complete.")

    return jsonify({'status': 'success'}), 200

def update_supabase(email, reference):
    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json"
    }

    user_res = requests.get(
        f"{SUPABASE_URL}/rest/v1/users?email=eq.{email}",
        headers=headers
    )
    user_data = user_res.json()

    if not user_data:
        print(f"⚠ No user found for {email}")
        return

    uid = user_data[0]['id']

    payload = {
        "form_purchased": True
    }
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/users?id=eq.{uid}",
        headers=headers,
        json=payload
    )

    log_payload = {
        "action": "webhook_payment",
        "details": {
            "email": email,
            "user_id": uid,
            "paystack_ref": reference
        },
        "created_at": str(requests.get("https://worldtimeapi.org/api/timezone/Africa/Lagos").json()["datetime"])
    }
    requests.post(
        f"{SUPABASE_URL}/rest/v1/admin_logs",
        headers=headers,
        json=log_payload
    )

if _name_ == '_main_':
    app.run(host='0.0.0.0', port=10000)