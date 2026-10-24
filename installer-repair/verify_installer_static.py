"""Static artifact gate only; never starts the supplied executable."""
from pathlib import Path
import hashlib, struct, sys
p=Path(sys.argv[1]);b=p.read_bytes()
assert b[:6]==b'\x7fELF\x02\x01', 'Expected ELF64 little endian'
assert struct.unpack_from('<H',b,18)[0]==183, 'Expected ARM64'
assert b'https://github.com/phairo-enterprises/ph.git?' in b, 'Required repository delimiter missing'
assert b'comma4-accord26-all-v2?' in b, 'Required branch delimiter missing'
assert b'git remote set-url origin %s' in b, 'Cached-origin correction string missing'
assert len(b)<2_500_000, 'Installer exceeds source build size limit'
print('PASS static artifact invariants; this does not execute the installer or prove boot')
print(hashlib.sha256(b).hexdigest(),p.name)
