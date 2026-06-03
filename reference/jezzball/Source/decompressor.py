# Decompressor for JezzBall 1.23
# by Piotr Kowalewski (komame)

import uio

def lz77_rle_decompress():
    """
    Decompresses data using an LZ77 sliding-window algorithm
    with literal run-length encoding for literal runs.

    Literal runs are simply grouped blocks of consecutive bytes
    emitted by the compressor (“pseudo-RLE”), which reduces output size.

    Returns:
        Decompressed data as bytes.
    """
    with uio.FileIO('jezzball.bin', 'rb') as file:
        # Use memoryview for efficient, zero-copy byte access
        data_view = memoryview(file.read())

    # Using a list because list.extend() is often faster than bytearray.extend() in MicroPython
    decompressed_data = []
    position = 0
    data_length = len(data_view)

    while position < data_length:
        control_byte = data_view[position]
        position += 1
        length = control_byte & 0x7F  # lower 7 bits = length

        if control_byte & 0x80:
            # LZ77 Back-reference (Match): MSB=1 → next two bytes are distance
            distance = data_view[position] | (data_view[position + 1] << 8)
            position += 2

            ref_start = len(decompressed_data) - distance
            remaining = length

            # Handle overlapping copy by copying in chunks
            while remaining > 0:
                chunk = min(remaining, distance)
                decompressed_data.extend(
                    decompressed_data[ref_start:ref_start + chunk]
                )
                ref_start += chunk
                remaining -= chunk
        else:
            # Literal run: copy exactly 'length' raw bytes
            decompressed_data.extend(
                data_view[position:position + length]
            )
            position += length

    return bytes(decompressed_data)

# Execute the decompressed data as Python code by:
# 1. Decompressing the binary data into bytes containing Python source code
# 2. Compiling that source code in memory
# 3. Executing the compiled code in the current namespace
exec(compile(lz77_rle_decompress(), '', 'exec'))
