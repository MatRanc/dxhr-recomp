"""Minimal ISO9660 extractor for 3k3y/Redump PS3 ISOs. usage: iso_extract.py ISO DKEY OUTDIR [prefix]"""
import struct, sys, os
iso, dkey, out = sys.argv[1], sys.argv[2], sys.argv[3]; prefix = sys.argv[4].strip('/') if len(sys.argv) > 4 else ''
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
raw = open(dkey, 'rb').read().strip(); KEY = bytes.fromhex(raw.decode()) if len(raw) == 32 else raw
assert len(KEY) == 16
# Redump .dkey = data1; the sector key is data1 AES-CBC-encrypted with the public PS3 disc constants
KEY = Cipher(algorithms.AES(bytes.fromhex('380bcf0b53455b3c7817ab4fa3ba90ed')), modes.CBC(bytes.fromhex('69474772af6fdab342743aefaa186287'))).encryptor().update(KEY)
f0 = open(iso, 'rb'); R = struct.unpack('>6I', f0.read(24)); assert R[0] == 2
P1, P2 = R[3], R[4]  # plain: lba<=P1 and lba>=P2; encrypted between
def dec(lba, b): return Cipher(algorithms.AES(KEY), modes.CBC(lba.to_bytes(16, 'big'))).decryptor().update(b)
S = 2048
def rd(lba, n):
    f0.seek(lba * S); b = f0.read(n); o = bytearray()
    for i in range(0, len(b), S):
        c = b[i:i+S]; l = lba + i // S
        o += dec(l, c) if not os.environ.get('NODEC') and P1 < l < P2 and len(c) == S else c
    return bytes(o)
pvd = rd(16, S); assert pvd[1:6] == b'CD001'
root = struct.unpack('<I', pvd[158:162])[0], struct.unpack('<I', pvd[166:170])[0]
def entries(lba, size):
    data = rd(lba, size); i = 0
    while i < size:
        l = data[i]
        if l == 0: i = (i // S + 1) * S; continue
        loc, ln = struct.unpack('<I', data[i+2:i+6])[0], struct.unpack('<I', data[i+10:i+14])[0]
        fl, nl = data[i+25], data[i+32]; name = data[i+33:i+33+nl]
        i += l
        if name in (b'\x00', b'\x01'): continue
        yield name.decode('latin1').split(';')[0], loc, ln, fl & 2
total = 0
seen = set()  # multi-extent files: later records for the same path append
def walk(lba, size, rel):
    global total
    for name, loc, ln, isdir in entries(lba, size):
        r = f'{rel}/{name}' if rel else name
        if isdir: walk(loc, ln, r); continue
        if prefix and not (r + '/').startswith(prefix + '/') and not r.startswith(prefix + '/'): continue
        if os.environ.get('DBG'): print(r, loc, ln)
        if os.environ.get('LISTONLY'): continue
        p = os.path.join(out, r); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'ab' if r in seen else 'wb') as o:
            seen.add(r)
            done = 0
            while done < ln: n = min(ln - done, 1 << 24); o.write(rd(loc + done // S, n)); done += n
        total += ln
walk(root[0], root[1], '')
print('extracted', total / 1e9, 'GB ->', out)
