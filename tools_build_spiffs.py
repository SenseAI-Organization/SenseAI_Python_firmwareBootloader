#!/usr/bin/env python3
"""
Find a mkspiffs binary (prefer PlatformIO's espidf variant) and run it to build a SPIFFS image.
Usage: python tools_build_spiffs.py --data <data_dir> --out <output_file> --size <size>
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_mkspiffs():
    # 1) Check repo tools/
    script_dir = Path(__file__).resolve().parent
    tools_dir = script_dir / 'tools'
    candidates = []
    if tools_dir.exists():
        for p in tools_dir.rglob('*'):
            if p.is_file() and p.name.lower().startswith('mkspiffs'):
                candidates.append(str(p))

    # 2) Check PlatformIO packages folder
    pio_packages = Path.home() / '.platformio' / 'packages'
    if pio_packages.exists():
        for p in pio_packages.rglob('*'):
            if p.is_file() and p.name.lower().startswith('mkspiffs'):
                candidates.append(str(p))
            # also allow mkspiffs.exe inside tool folder
            if p.is_dir() and p.name.lower().startswith('tool-mkspiffs'):
                for sub in ('mkspiffs.exe', 'mkspiffs', 'bin/mkspiffs.exe', 'bin/mkspiffs'):
                    cand = p / sub
                    if cand.exists():
                        candidates.append(str(cand))

    # 3) Check PATH
    which = shutil.which('mkspiffs')
    if which:
        candidates.append(which)

    # Deduplicate while preserving order
    seen = set(); ordered = []
    for c in candidates:
        if c not in seen:
            seen.add(c); ordered.append(c)

    # Prefer files with 'espressif32_espidf' in name
    espidf = [c for c in ordered if 'espressif32_espidf' in os.path.basename(c).lower()]
    if espidf:
        # return first espidf variant
        return espidf[0]

    # Otherwise return first candidate
    if ordered:
        return ordered[0]

    return None


def run_mkspiffs(mk, data_dir, out_file, size, page=256, block=4096):
    cmd = [mk, '-c', data_dir, '-s', str(size), '-p', str(page), '-b', str(block), out_file]
    print('Running:', ' '.join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    return proc.returncode


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--size', required=True, type=int)
    args = p.parse_args()

    data = Path(args.data)
    if not data.exists() or not data.is_dir():
        print('Data folder not found:', data)
        sys.exit(2)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    mk = find_mkspiffs()
    if not mk:
        print('No mkspiffs found (repo tools/, PlatformIO packages, PATH).')
        print('Place a mkspiffs binary in the repo tools/ folder or install PlatformIO.')
        sys.exit(3)

    print('Using mkspiffs:', mk)
    rc = run_mkspiffs(mk, str(data), str(out), args.size)
    if rc != 0:
        print('mkspiffs returned non-zero exit code:', rc)
        sys.exit(rc)

    print('SPIFFS image created:', out)

if __name__ == '__main__':
    main()
