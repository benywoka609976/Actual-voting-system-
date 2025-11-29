from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import hashlib, json
from utils import merkle_tree_insert
db = SQLAlchemy()

class Voter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    idno = db.Column(db.String, nullable=False, unique=True)
    selfie_path = db.Column(db.String, nullable=True)
    biometric_hash = db.Column(db.String, nullable=True)
    registered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def as_dict(self):
        return {'id':self.id,'name':self.name,'idno':self.idno,'registered_at':self.registered_at.isoformat()}

    @staticmethod
    def create_manual(name,idno):
        v = Voter(name=name,idno=idno)
        db.session.add(v); db.session.commit()
        return v

class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    manifesto = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    def as_dict(self):
        return {'id':self.id,'name':self.name,'manifesto':self.manifesto}

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    voter_id = db.Column(db.Integer, db.ForeignKey('voter.id'))
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.id'))
    biometric_hash = db.Column(db.String, nullable=True)
    cast_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def as_dict(self):
        return {'id':self.id,'voter_id':self.voter_id,'candidate_id':self.candidate_id,'cast_at':self.cast_at.isoformat()}

    @staticmethod
    def cast(voter_id,candidate_id,biometric_hash):
        v = Vote(voter_id=voter_id,candidate_id=candidate_id,biometric_hash=biometric_hash)
        db.session.add(v)
        db.session.flush()
        return v

    @staticmethod
    def counts():
        res = {}
        for c in Candidate.query.all():
            res[c.id] = Vote.query.filter_by(candidate_id=c.id).count()
        return res

class LedgerEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payload = db.Column(db.String, nullable=False)
    hash = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @staticmethod
    def append_vote(vote):
        payload = json.dumps(vote.as_dict(), sort_keys=True)
        h = hashlib.sha256(payload.encode()).hexdigest()
        le = LedgerEntry(payload=payload, hash=h)
        db.session.add(le)
        db.session.flush()
        merkle_tree_insert(h)
        return le

class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    account_ref = db.Column(db.String, nullable=True)
    status = db.Column(db.String, default='PENDING')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    raw_request = db.Column(db.String, nullable=True)
    raw_callback = db.Column(db.String, nullable=True)

    @staticmethod
    def create_pending(phone, amount, account_ref, request_payload):
        d = Donation(phone=phone, amount=amount, account_ref=account_ref, raw_request=json.dumps(request_payload))
        db.session.add(d); db.session.flush()
        return d

    @staticmethod
    def confirm_from_callback(payload):
        try:
            tx = Donation.query.order_by(Donation.id.desc()).first()
            tx.status = 'CONFIRMED'
            tx.raw_callback = json.dumps(payload)
            db.session.add(tx); db.session.flush()
            return tx
        except Exception as e:
            raise
def init_db(app):
    with app.app_context():
        db.init_app(app)
        db.create_all()
