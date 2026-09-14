"""Parse a Unity Addressables ContentCatalogData (catalog.json).

Layouts (little endian, validated against this catalog):
  KeyDataString    : int32 count, then count records:
                       byte type; 0=ascii, 1=utf16, 2=uint16, 3=uint32, 4=int32, 5=hash128
                       string types: int32 byte-length INCLUDING trailing NUL, then bytes
  BucketDataString : int32 bucketCount, then per bucket:
                       int32 keyOffset (into KeyDataString), int32 entryCount,
                       int32 entryIndex[entryCount]
  EntryDataString  : int32 entryCount, then per entry 7 x int32:
                       internalId, providerIndex, dependencyKey, dependencyHashValue,
                       dataIndex, primaryKey, resourceTypeIndex
"""
import base64
import json
import os
import struct

CATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog.json")


def decode_keys(data):
    count = struct.unpack_from("<i", data, 0)[0]
    keys, offsets = [], []
    pos = 4
    for _ in range(count):
        offsets.append(pos)
        t = data[pos]
        pos += 1
        if t == 0:
            ln = struct.unpack_from("<i", data, pos)[0]
            pos += 4
            keys.append(data[pos:pos + ln].split(b"\x00", 1)[0].decode("utf-8", "replace"))
            pos += ln
        elif t == 1:
            ln = struct.unpack_from("<i", data, pos)[0]
            pos += 4
            keys.append(data[pos:pos + ln].decode("utf-16-le", "replace").split("\x00", 1)[0])
            pos += ln
        elif t == 2:
            keys.append(struct.unpack_from("<H", data, pos)[0])
            pos += 2
        elif t == 3:
            keys.append(struct.unpack_from("<I", data, pos)[0])
            pos += 4
        elif t == 4:
            keys.append(struct.unpack_from("<i", data, pos)[0])
            pos += 4
        elif t == 5:
            keys.append(data[pos:pos + 16].hex())
            pos += 16
        else:
            raise ValueError(f"unknown key type {t} at {pos - 1}")
    assert pos == len(data), f"key data trailing bytes: {pos} != {len(data)}"
    return keys, offsets


def decode_buckets(data):
    count = struct.unpack_from("<i", data, 0)[0]
    buckets = []
    pos = 4
    for _ in range(count):
        key_off, n = struct.unpack_from("<ii", data, pos)
        pos += 8
        entries = list(struct.unpack_from(f"<{n}i", data, pos)) if n else []
        pos += 4 * n
        buckets.append((key_off, entries))
    assert pos == len(data), f"bucket trailing bytes: {pos} != {len(data)}"
    return buckets


def decode_entries(data):
    count = struct.unpack_from("<i", data, 0)[0]
    fields = ["internalId", "providerIndex", "dependencyKey", "dependencyHashValue",
              "dataIndex", "primaryKey", "resourceTypeIndex"]
    return [dict(zip(fields, struct.unpack_from("<7i", data, 4 + i * 28)))
            for i in range(count)]


class Catalog:
    def __init__(self, path=CATALOG):
        c = json.load(open(path, encoding="utf-8"))
        self.keys, offsets = decode_keys(base64.b64decode(c["m_KeyDataString"]))
        self.buckets = decode_buckets(base64.b64decode(c["m_BucketDataString"]))
        self.entries = decode_entries(base64.b64decode(c["m_EntryDataString"]))
        self.internal_ids = c["m_InternalIds"]
        self.resource_types = c["m_resourceTypes"]
        self._by_offset = dict(zip(offsets, range(len(self.keys))))

    def locations(self):
        """Yield (key, internalId, entry) for every key -> entry -> internalId."""
        for key_off, entry_idxs in self.buckets:
            ki = self._by_offset.get(key_off)
            if ki is None:
                continue
            key = self.keys[ki]
            for ei in entry_idxs:
                e = self.entries[ei]
                yield key, self.internal_ids[e["internalId"]], e


if __name__ == "__main__":
    cat = Catalog()
    print("keys", len(cat.keys), "buckets", len(cat.buckets), "entries", len(cat.entries))
    print("resource types:", len(cat.resource_types))
    n = 0
    for key, iid, e in cat.locations():
        if n < 5:
            print(f"  key={key[:70]!r}\n     -> {iid[:110]}")
        n += 1
    print("locations:", n)
