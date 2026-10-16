#!/usr/bin/env python3
"""Pinpoint the Windows test crash and discriminate its mechanism. Prints no private source."""
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
native = root / 'app' / 'src-tauri' / 'native'
MARKERS = ['invalid operator', 'unordered', 'run-time check', 'pure virtual', 'terminate called',
           'buffer overrun', 'stack cookie', 'abort', 'assert', 'access violation', 'not found']


def staged_env(flags=None):
    env = os.environ.copy()
    env['PATH'] = str(native) + os.pathsep + env.get('PATH', '')
    if flags:
        env['CXXFLAGS'] = flags
    return env


def capture(argv, env=None):
    done = subprocess.run(argv, env=env or staged_env(), cwd=str(root),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
    return done.returncode, done.stdout or ''


def verdict(code, text):
    low = text.lower()
    return {m: low.count(m) for m in MARKERS if low.count(m)}


def main():
    _, out = capture(['cargo', 'test', '--workspace', '--locked', '--no-run', '--message-format=json'])
    exes = []
    for line in out.splitlines():
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get('reason') == 'compiler-artifact' and message.get('executable'):
            exes.append(Path(message['executable']))
    crasher = None
    for i, exe in enumerate(exes, 1):
        stem = exe.stem.rsplit('-', 1)[0]
        _, listing = capture([str(exe), '--list', '--format=terse'])
        names = [line.split(':')[0].strip() for line in listing.splitlines() if line.endswith(': test')]
        code, text = capture([str(exe), '--test-threads=1'])
        ok = sum(1 for l in text.splitlines() if l.endswith('... ok'))
        print(f'EXE{i} stem={stem} tests={len(names)} seq_rc={code} seq_ok={ok}')
        if code != 0:
            print(f'EXE{i} markers={json.dumps(verdict(code, text))}')
            solo = []
            for j, name in enumerate(names, 1):
                rc, body = capture([str(exe), name, '--exact', '--nocapture'])
                if rc != 0:
                    solo.append(j)
                    crasher = (exe, name)
                    print(f'EXE{i} solo_crashers_pos={j} of {len(names)} markers={json.dumps(verdict(rc, body))}')
            print(f'EXE{i} solo_total_crashers={len(solo)}')
    if crasher:
        exe, name = crasher
        for label, flags in [('GS_off', '/GS-'), ('O2', '/O2'), ('GS_off_and_O2', '/GS- /O2')]:
            subprocess.call(['cargo', 'clean', '-p', 'inbless-engine'], cwd=str(root))
            code, text = capture(['cargo', 'test', '-p', 'inbless-engine', '--lib', '--locked', '--', name,
                                  '--exact', '--nocapture'], staged_env(flags))
            print(f'AB_{label} rc={code} ok={sum(1 for l in text.splitlines() if l.endswith("... ok"))} '
                  f'err_prefix_lines={sum(1 for l in text.splitlines() if l.startswith("error"))} '
                  f'markers={json.dumps(verdict(code, text))}')
        subprocess.call(['cargo', 'clean', '-p', 'inbless-engine'], cwd=str(root))
        code, text = capture(['cargo', 'test', '-p', 'inbless-engine', '--lib', '--locked', '--', name, '--exact'])
        print(f'AB_baseline_rebuild rc={code} ok={sum(1 for l in text.splitlines() if l.endswith("... ok"))}')
        for threads in ['1', '2']:
            env = staged_env()
            env['RUST_TEST_THREADS'] = threads
            code, _ = capture([str(exe), name, '--exact'], env)
            print(f'THREADS_{threads}_rc={code}')
    print('probe_done')


if __name__ == '__main__':
    main()
