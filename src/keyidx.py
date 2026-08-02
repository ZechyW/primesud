"""Binary keyword-index reader for mobs.bin / objs.bin. [PRIMESUD]

Both files share the KX01 layout built by tools/build_mob_index.py
(pack_key_index is the schema SSOT; tools/dump_key_bin.py renders one
back to text). Consumers doing raw field reads need these record offsets
-- records run from meta[0] up to meta[1], step 11 + tag_count:

    0 vnum u16   2 level u8 (0 for objects)   3 home_tag u8
    4 kw_off u16 (relative to meta[1], the keyword blob)   6 kw_len u8
    7 name_off u16 (relative to meta[2], the string table)   9 name_len u8
   10 tag_count u8   11.. spawn tag ids u8 x tag_count

Name search is two-phase and allocation-free until the (few) confirmed
candidates: the lowercased keyword blob is swept with native find() for
the target's first word, accepting only word-boundary hits, and the hits
are mapped back to records with one sequential two-pointer walk (records
and blob entries share an order). Per-record split()s cost ~13ms/line
on-device (docs/PERFORMANCE.md sec. Recommend scans), so nothing here
allocates per record.
"""

# No module-level imports: keyidx must stay a leaf so debug.py can import
# it at top level (handler imports debug, so a handler backref here would
# cycle). handler.is_name is imported inside candidates().


def _as_bytes(data):
    """Byte-cast an index read: device open(.., "rb") can hand back str.

    [PRIMESUD] MicroPython str.encode() returns the underlying byte payload
    without re-encoding, so a byte-faithful read mistagged as str recovers
    exactly; genuinely translated data fails the header checks downstream.
    """
    return data.encode() if type(data) is str else data


def _parse_header(data):
    """Decode a KX01 header. [PRIMESUD]

    Returns (records_off, kw_off, strings_off, record_count, tags), or
    None when the header is malformed. Raises IndexError/UnicodeError on
    truncated garbage -- the caller wraps.
    """
    if data[:4] != b"KX01":
        return None
    header_size = data[4] | data[5] << 8
    kw_off = data[6] | data[7] << 8 | data[8] << 16 | data[9] << 24
    strings_off = (data[10] | data[11] << 8 | data[12] << 16
                   | data[13] << 24)
    record_count = data[14] | data[15] << 8
    pos = 16
    count = data[pos]
    pos += 1
    tags = []
    for _ in range(count):
        length = data[pos]
        tags.append(data[pos + 1:pos + 1 + length].decode())
        pos += 1 + length
    if pos != header_size:
        return None
    if header_size > kw_off or kw_off > strings_off or strings_off > len(data):
        return None
    return header_size, kw_off, strings_off, record_count, tags


def load(fname):
    """Read a whole KX01 index file. [PRIMESUD]

    Args:
        fname (str): Index file name.

    Returns:
        tuple or None: (data, meta) where meta is
        (records_off, kw_off, strings_off, record_count, tags); None when
        the file is missing or malformed, so callers degrade to
        loaded-area results.
    """
    try:
        f = open(fname, "rb")
    except OSError:
        return None
    with f:  # one read; looped readline() is ~20ms/call on-device
        data = _as_bytes(f.read())
    try:
        meta = _parse_header(data)
    except (IndexError, ValueError, UnicodeError):
        return None
    if meta is None:
        return None
    return data, meta


def candidates(data, meta, target):
    """Return record offsets whose keywords is_name-match target. [PRIMESUD]

    Args:
        data (bytes): Whole index blob from load().
        meta (tuple): Header tuple from load().
        target (str): Space-separated name words typed by the player.

    Returns:
        list: Absolute record offsets, in file order.
    """
    records_off = meta[0]
    kw_off = meta[1]
    strings_off = meta[2]
    words = target.split()
    if not words:
        return []
    word = words[0]
    # A quoted first word can never prefix-match a keyword, so trimming
    # only widens the prefilter; is_name below still rejects it.
    while word and (word[0] == "'" or word[0] == '"'):
        word = word[1:]
    while word and (word[-1] == "'" or word[-1] == '"'):
        word = word[:-1]
    if not word:
        return []
    needle = word.lower().encode()

    # Phase 1: native sweep of the lowercased keyword blob. Only hits at a
    # word boundary are prefix matches; ints only, no allocation.
    hits = []
    pos = kw_off
    while True:
        hit = data.find(needle, pos)
        # hit < pos means find() ignored its start arg (never seen on
        # firmware, but unprovable from PC): break with partial hits
        # rather than sweep forever on-device.
        if hit < pos or hit >= strings_off:
            break
        lead = data[hit - 1]  # in bounds: the blob opens with a separator
        if lead == 10 or lead == 32:
            hits.append(hit)
        pos = hit + 1
    if not hits:
        return []

    # Phase 2: map hits back to records with one sequential walk -- record
    # order and blob order agree, so both pointers only move forward.
    found = []
    index = 0
    total = len(hits)
    pos = records_off
    while pos < kw_off and index < total:
        start = kw_off + (data[pos + 4] | data[pos + 5] << 8)
        end = start + data[pos + 6]
        while index < total and hits[index] < start:
            index += 1
        if index < total and hits[index] < end:
            found.append(pos)
            while index < total and hits[index] < end:
                index += 1
        pos += 11 + data[pos + 10]

    # Phase 3: confirm the remaining target words. Few candidates survive,
    # so the keyword slice is affordable here; the blob is already lower
    # case, and is_name lowercases both sides anyway.
    from handler import is_name  # deferred: see module docstring

    matched = []
    for pos in found:
        start = kw_off + (data[pos + 4] | data[pos + 5] << 8)
        if is_name(target, data[start:start + data[pos + 6]].decode()):
            matched.append(pos)
    return matched
