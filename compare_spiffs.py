import os
import sys

root = os.path.dirname(os.path.abspath(__file__))
# allow spiffs.bin either at repo root or inside test_spiffs (user moved file)
candidate_ours = [os.path.join(root, 'spiffs.bin'), os.path.join(root, 'test_spiffs', 'spiffs.bin')]
our = next((p for p in candidate_ours if os.path.exists(p)), None)
ref = os.path.join(root, 'test_spiffs', 'spiffs_example.bin')

missing = []
if our is None:
    missing.append('our spiffs (looked in: ' + ','.join(candidate_ours) + ')')
if not os.path.exists(ref):
    missing.append(ref)
if missing:
    print('ERROR: missing', '; '.join(missing))
    sys.exit(2)

with open(our,'rb') as f:
    a = f.read()
with open(ref,'rb') as f:
    b = f.read()

print('Our spiffs.bin size:', len(a))
print('Ref spiffs_example.bin size:', len(b))
print('Files identical:', a==b)

needle = b'/Server1.pem'

def occurrences(data):
    pos=0
    out=[]
    while True:
        i=data.find(needle,pos)
        if i==-1: break
        out.append(i)
        pos=i+1
    return out

oa = occurrences(a)
ob = occurrences(b)
print('\nOccurrences of /Server1.pem in our image:', oa)
print('Occurrences of /Server1.pem in ref image:', ob)

# show context around first occurrence
if oa:
    i=oa[0]
    s=max(0,i-64)
    e=min(len(a),i+128)
    print('\nOur first occurrence context (ascii):')
    print(''.join(chr(c) if 32<=c<127 else '.' for c in a[s:e]))
    print('\nhex:')
    print(' '.join(f"{c:02x}" for c in a[s:e]))

if ob:
    i=ob[0]
    s=max(0,i-64)
    e=min(len(b),i+128)
    print('\nRef first occurrence context (ascii):')
    print(''.join(chr(c) if 32<=c<127 else '.' for c in b[s:e]))
    print('\nhex:')
    print(' '.join(f"{c:02x}" for c in b[s:e]))

# find first differing offset
minlen=min(len(a),len(b))
first_diff=None
for i in range(minlen):
    if a[i]!=b[i]:
        first_diff=i
        break
if first_diff is None:
    if len(a)!=len(b):
        first_diff=minlen

print('\nFirst differing byte offset:', first_diff)
if first_diff is not None:
    s=max(0, first_diff-32)
    ea=min(len(a), first_diff+64)
    eb=min(len(b), first_diff+64)
    print('\nOur around diff (ascii):')
    print(''.join(chr(c) if 32<=c<127 else '.' for c in a[s:ea]))
    print('\nRef around diff (ascii):')
    print(''.join(chr(c) if 32<=c<127 else '.' for c in b[s:eb]))

# quick stats: counts of occurrences
print('\nCounts: our=', len(oa), 'ref=', len(ob))

# print simple header signature (first 64 bytes hex)
print('\nOur header hex (first 64 bytes):')
print(' '.join(f"{c:02x}" for c in a[:64]))
print('\nRef header hex (first 64 bytes):')
print(' '.join(f"{c:02x}" for c in b[:64]))
