slave2 =  [
    21536,
    18521,
    17440,
    17744,
    21248,
    0,
    0,
    12340
]

slave3 = [
    21536,
    18521,
    17440,
    17236,
    20529,
    0,
    0,
    12340
]

slave4 = [
    21569,
    8264,
    22852,
    21071,
    17224,
    17741,
    8265,
    12340
]

slave5 = [
    21536,
    18521,
    17440,
    18519,
    8272,
    12800,
    0,
    12340
]

slave6 = [
    21536,
    18521,
    17440,
    18519,
    8272,
    12544,
    0,
    12340
]


slaves = [slave2, slave3, slave4, slave5, slave6]


for registers in slaves:
    result = ""
    for reg in registers:
        # Extract high byte (most significant byte) and low byte
        high_byte = (reg >> 8) & 0xFF
        low_byte = reg & 0xFF

        # Convert to ASCII characters (skip null bytes)
        if high_byte != 0:
            result += chr(high_byte)
        if low_byte != 0:
            result += chr(low_byte)
    print(result)
