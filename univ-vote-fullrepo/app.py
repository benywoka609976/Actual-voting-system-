import os, base64, time, json, requests
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from models import db, init_db, Voter, Candidate, Vote, LedgerEntry, Donation
from ai_monitor import AIMonitor
from utils import merkle_root, sign_bytes, save_file_secure, load_env
from datetime import datetime, timezone

env = load_env()
USE_MOCK_MPESA = os.getenv("USE_MOCK_MPESA", env.get("USE_MOCK_MPESA","1")) == "1"
MOCK_BASE = os.getenv("MOCK_DARAJA_BASE", env.get("MOCK_DARAJA_BASE","http://localhost:5005"))

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', env.get('DATABASE_URL','sqlite:///univvote.db'))
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', env.get('SECRET_KEY','replace-me'))
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

ai_monitor = AIMonitor()

@app.before_first_request
def setup():
    init_db(app)
    if Candidate.query.count() == 0:
        c1 = Candidate(name='Alice for Student Rep', manifesto='Transparency & Health')
        c2 = Candidate(name='Bob for Student Rep', manifesto='Fair Fees')
        db.session.add_all([c1,c2])
        db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

def mpesa_oauth_token():
    if USE_MOCK_MPESA:
        try:
            r = requests.get(f"{MOCK_BASE}/oauth/v1/generate", timeout=5)
            r.raise_for_status()
            return r.json().get('access_token'), None
        except Exception as e:
            return None, str(e)
    key = os.getenv('MPESA_CONSUMER_KEY', env.get('MPESA_CONSUMER_KEY'))
    secret = os.getenv('MPESA_CONSUMER_SECRET', env.get('MPESA_CONSUMER_SECRET'))
    if not (key and secret):
        return None, 'MPESA credentials not set'
    auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
    url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    headers = {'Authorization': f'Basic {auth}'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json().get('access_token'), None
    except Exception as e:
        return None, str(e)

@app.route('/mpesa/auth', methods=['POST'])
def mpesa_auth():
    token, err = mpesa_oauth_token()
    if err:
        return jsonify({'error':err}), 500
    return jsonify({'access_token': token})

@app.route('/mpesa/stkpush', methods=['POST'])
def mpesa_stkpush():
    data = request.json or {}
    phone = data.get('phone'); amount = data.get('amount'); acc_ref = data.get('account_ref','Donation')
    if not phone or not amount:
        return jsonify({'error':'phone and amount required'}), 400
    token, err = mpesa_oauth_token()
    if err:
        return jsonify({'error':'auth failure: '+err}), 500
    shortcode = os.getenv('MPESA_SHORTCODE', env.get('MPESA_SHORTCODE'))
    passkey = os.getenv('MPESA_PASSKEY', env.get('MPESA_PASSKEY'))
    callback = os.getenv('MPESA_CALLBACK_URL', env.get('MPESA_CALLBACK_URL', f"{request.host_url.rstrip('/')}/mpesa/webhook"))
    timestamp = time.strftime('%Y%m%d%H%M%S', time.gmtime())
    password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": shortcode,
        "PhoneNumber": phone,
        "CallBackURL": callback,
        "AccountReference": acc_ref,
        "TransactionDesc": data.get('description','Donation')
    }
    headers = {'Authorization': f'Bearer {token}'}
    if USE_MOCK_MPESA:
        stk_url = f"{MOCK_BASE}/mpesa/stkpush/v1/processrequest"
    else:
        stk_url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
    try:
        r = requests.post(stk_url, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        resp = r.json()
        d = Donation.create_pending(phone=phone, amount=amount, account_ref=acc_ref, request_payload=resp)
        return jsonify({'status':'initiated','daraja_response':resp,'donation_id': d.id})
    except Exception as e:
        return jsonify({'error':'stkpush failed: '+str(e)}), 500

@app.route('/mpesa/webhook', methods=['POST'])
def mpesa_webhook():
    data = request.json or {}
    try:
        result = data.get('Body') or data
        invoice = Donation.confirm_from_callback(result)
        # notify or process as needed
        return jsonify({'status':'ok','donation_id': getattr(invoice,'id',None)})
    except Exception as e:
        return jsonify({'error':'failed to process callback: '+str(e)}), 500

@app.route('/mpesa/simulate_callback', methods=['POST'])
def trigger_local_callback():
    data = request.json or {}
    donation_id = data.get('donation_id')
    amount = data.get('amount', 10)
    try:
        r = requests.post(f"{MOCK_BASE}/simulate_callback", json={"donation_id": donation_id, "amount": amount}, timeout=5)
        r.raise_for_status()
        cb = r.json()
        webhook_url = request.host_url.rstrip('/') + "/mpesa/webhook"
        r2 = requests.post(webhook_url, json=cb, timeout=5)
        return jsonify({"simulated_callback": cb, "forwarded_to_webhook": r2.json()})
    except Exception as e:
        return jsonify({'error':'simulate failed: '+str(e)}), 500

# -- core minimal voting endpoints --
@app.route('/register/manual', methods=['POST'])
def register_manual():
    data = request.json or {}
    name = data.get('name'); idno = data.get('idno')
    if not (name and idno):
        return jsonify({'error':'name and idno required'}),400
    v = Voter.create_manual(name=name,idno=idno)
    return jsonify({'status':'ok','voter_id':v.id})

@app.route('/candidates', methods=['GET','POST'])
def candidates():
    if request.method == 'GET':
        return jsonify([c.as_dict() for c in Candidate.query.all()])
    data = request.json or {}
    name = data.get('name'); manifesto = data.get('manifesto','')
    if not name:
        return jsonify({'error':'name required'}),400
    c = Candidate(name=name, manifesto=manifesto)
    db.session.add(c); db.session.commit()
    return jsonify({'status':'ok','candidate_id':c.id})

@app.route('/vote', methods=['POST'])
def cast_vote():
    data = request.json or {}
    voter_id, candidate_id = data.get('voter_id'), data.get('candidate_id')
    biometric_hash = data.get('biometric_hash')
    vote = Vote.cast(voter_id=voter_id, candidate_id=candidate_id, biometric_hash=biometric_hash)
    entry = LedgerEntry.append_vote(vote)
    db.session.commit()
    socketio.emit('vote_update', {'candidate_id':candidate_id, 'counts': Vote.counts()})
    return jsonify({'status':'ok','vote_id':vote.id,'merkle_root':merkle_root()})

@app.route('/results', methods=['GET'])
def results():
    counts = Vote.counts()
    root = merkle_root()
    signature = sign_bytes(root.encode())
    return jsonify({'counts':counts,'merkle_root':root,'signature':signature.hex()})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.getenv('PORT',5000)))
