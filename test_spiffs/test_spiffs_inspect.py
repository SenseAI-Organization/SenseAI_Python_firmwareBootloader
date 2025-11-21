import os
import sys

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'spiffs.bin')
if not os.path.exists(path):
    print('ERROR: spiffs.bin not found at', path)
    sys.exit(2)

with open(path, 'rb') as f:
    data = f.read()

print('spiffs.bin size:', len(data))

def hexdump(b):
    return ' '.join(f"{c:02x}" for c in b)

# Search for common markers
markers = [b'/spiffs/', b'/Server1.pem', b'Server1.pem', b'Server1', b'spiffs']
for m in markers:
    idx = data.find(m)
    print(f"marker {m!r} -> index: {idx}")
    if idx != -1:
        start = max(0, idx-64)
        end = min(len(data), idx+128)
        chunk = data[start:end]
        print('context (bytes):', chunk)
        print('context (hex):', hexdump(chunk))
        print('-'*60)

# Find all occurrences of Server1.pem
needle = b'Server1.pem'
pos = 0
found = []
while True:
    i = data.find(needle, pos)
    if i == -1:
        break
    found.append(i)
    pos = i + 1

print('All Server1.pem occurrences:', found)
for idx in found:
    start = max(0, idx-64)
    end = min(len(data), idx+128)
    chunk = data[start:end]
    print(f'--- occurrence at {idx} ---')
    print('ascii snippet:', ''.join((chr(c) if 32 <= c < 127 else '.') for c in chunk))
    print('hex snippet:', hexdump(chunk))

# Also print a short summary whether image contains filenames with leading '/'
print('\nSummary:')
print('Has /spiffs/:', b'/spiffs/' in data)
print('Has /Server1.pem:', b'/Server1.pem' in data)
print('Has Server1.pem:', needle in data)
