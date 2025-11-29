import os, hashlib, json
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

KEYFILE = os.getenv('ED25519_KEY_PATH', 'ed25519_key.pem')
MERKLE_STORE = 'merkle_nodes.json'

def load_env():
    env = {}
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    k,v = line.strip().split('=',1)
                    env[k]=v
    return env

def current_epoch():
    return datetime.now(timezone.utc).isoformat()

def save_file_secure(fileobj, subdir='uploads'):
    os.makedirs(subdir, exist_ok=True)
    filename = f"{int(datetime.now(timezone.utc).timestamp())}_{fileobj.filename}"
    path = os.path.join(subdir, filename)
    fileobj.save(path)
    return path

def merkle_tree_insert(leaf_hex):
    nodes = []
    if os.path.exists(MERKLE_STORE):
        with open(MERKLE_STORE,'r') as f: nodes = json.load(f)
    nodes.append(leaf_hex)
    with open(MERKLE_STORE,'w') as f: json.dump(nodes,f)
    return nodes

def merkle_root():
    if not os.path.exists(MERKLE_STORE): return ''
    with open(MERKLE_STORE,'r') as f:
        leaves = json.load(f)
    def pairwise(hs):
        out = []
        for i in range(0,len(hs),2):
            a = hs[i]
            b = hs[i+1] if i+1<len(hs) else a
            out.append(hashlib.sha256((a+b).encode()).hexdigest())
        return out
    cur = leaves[:]
    while len(cur) > 1:
        cur = pairwise(cur)
    return cur[0] if cur else ''

def _ensure_key():
    if os.path.exists(KEYFILE):
        with open(KEYFILE,'rb') as f:
            return Ed25519PrivateKey.from_private_bytes(f.read())
    key = Ed25519PrivateKey.generate()
    with open(KEYFILE,'wb') as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        ))
    return key

def sign_bytes(b):
    key = _ensure_key()
    return key.sign(b)
