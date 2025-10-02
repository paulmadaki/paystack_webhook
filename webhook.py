from flask import Flask, request, jsonify
import hmac, hashlib, os
import requests

app = Flask(__name__)
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_data()
    signature = request.headers.get('x-paystack-signature')

    computed_signature = hmac.new(
        PAYSTACK_SECRET.encode(),
        msg=payload,
        digestmod=hashlib.sha512
    ).hexdigest()

    if signature != computed_signature:
        return jsonify({'status': 'unauthorized'}), 401

    data = request.json
    event = data.get('event')
    reference = data['data'].get('reference')
    email = data['data'].get('customer', {}).get('email')

    if event == 'charge.success' and email:
        update_supabase(email, reference)

    return jsonify({'status': 'success'}), 200

def update_supabase(email, reference):
    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json"
    }

    # Find user by email
    user_res = requests.get(
        f"{SUPABASE_URL}/rest/v1/users?email=eq.{email}",
        headers=headers
    )
    user_data = user_res.json()
    if not user_data:
        return

    uid = user_data[0]['id']

    # Update user record
    payload = {
        "form_purchased": True
    }
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/users?id=eq.{uid}",
        headers=headers,
        json=payload
    )

    # Log payment
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