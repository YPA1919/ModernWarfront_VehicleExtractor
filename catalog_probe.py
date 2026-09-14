import base64
import json
import struct

c = json.load(open(r"D:\DeepSeek Harness\mw\catalog.json", encoding="utf-8"))


def sec(name):
    return base64.b64decode(c[name])


kd = sec("m_KeyDataString")
bd = sec("m_BucketDataString")
ed = sec("m_EntryDataString")
xd = sec("m_ExtraDataString")

print("KeyData  head:", kd[:32].hex(" "))
print("BucketData head:", bd[:48].hex(" "))
print("EntryData head:", ed[:48].hex(" "))

i32 = lambda b, o: struct.unpack_from("<i", b, o)[0]

print("\nKeyData count int32 =", i32(kd, 0))
print("BucketData count int32 =", i32(bd, 0))
print("EntryData first int32 =", i32(ed, 0))
print("EntryData len/?? =", len(ed), len(ed) / 24, len(ed) / 28, len(ed) / 32)

# try to decode keys: [byte type][int32 len][bytes] x N
n = i32(kd, 0)
pos = 4
keys = []
ok = True
try:
    for _ in range(n):
        t = kd[pos]
        ln = i32(kd, pos + 1)
        s = kd[pos + 5:pos + 5 + ln].decode("utf-8", "replace")
        keys.append((t, s))
        pos += 5 + ln
except Exception as e:
    ok = False
    print("decode fail at", len(keys), e)
print("\nlayout [byte type][int32 len][bytes]: ok=", ok, "decoded", len(keys), "consumed", pos, "of", len(kd))
for t, s in keys[:12]:
    print("   t=%d %r" % (t, s[:120]))
print("   ...")
for t, s in keys[-5:]:
    print("   t=%d %r" % (t, s[:120]))

import collections
print("\ntypes:", collections.Counter(t for t, _ in keys))
tank = [s for t, s in keys if "/Tanks/" in s]
print("tank keys:", len(tank))
for s in tank[:8]:
    print("   ", s)
