#!/usr/bin/env python3
"""Windows test-execution probe. Prints only numbers, flags and library basenames."""
import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
native = root / 'app' / 'src-tauri' / 'native'
sdkbin = root / 'vendor' / 'bin'


def with_path(extra):
    env = os.environ.copy()
    env['PATH'] = str(extra) + os.pathsep + env.get('PATH', '')
    return env


def rc(label, argv, env=None):
    try:
        code = subprocess.call(argv, env=env, cwd=str(root))
    except OSError as error:
        print(f'{label} spawn_oserror winerror={error.winerror} errno={error.errno}')
        return
    print(f'{label} rc={code}')


def main():
    print(f'os={os.name} py={sys.version_info.major}.{sys.version_info.minor}')
    print(f'native_dir={native.is_dir()} native_dlls={len(list(native.glob("*.dll")))}')
    print(f'sdkbin_dir={sdkbin.is_dir()} sdkbin_dlls={len(list(sdkbin.glob("*.dll"))) if sdkbin.is_dir() else -1}')
    built = subprocess.run(['cargo', 'test', '--workspace', '--locked', '--no-run', '--message-format=json'],
                           cwd=str(root), capture_output=True, text=True)
    print(f'build_rc={built.returncode}')
    exes = []
    for line in built.stdout.splitlines():
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get('reason') == 'compiler-artifact' and message.get('executable'):
            exes.append(message['executable'])
    print(f'exes={len(exes)}')
    for i, exe in enumerate(exes, 1):
        path = Path(exe)
        print(f'EXE{i} exists={path.is_file()} name_head={path.name[:2]} ext={path.suffix}')
        rc(f'EXE{i}_plain', [exe, '--quiet'])
        rc(f'EXE{i}_stagedpath', [exe, '--quiet'], with_path(native))
        rc(f'EXE{i}_sdkbinpath', [exe, '--quiet'], with_path(sdkbin))
        rc(f'EXE{i}_cirunner', [sys.executable, str(root / 'scripts' / 'test.py'), '--run', exe, '--quiet'],
           with_path(native))
    # Report only libraries that cannot be loaded and the Windows error number.
    if native.is_dir():
        cookie = os.add_dll_directory(str(native))
        for dll in sorted(native.glob('*.dll')):
            try:
                ctypes.WinDLL(str(dll))
            except OSError as error:
                print(f'LOADFAIL {dll.name} winerror={error.winerror}')
            except Exception as error:
                print(f'LOADFAIL {dll.name} kind={type(error).__name__}')
        cookie.close()
    print('load_scan_done')
    # The exact CI command, reduced to counters.
    log = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'probe-suite.log'
    suite = subprocess.call([sys.executable, str(root / 'scripts' / 'test.py')],
                            cwd=str(root), env=with_path(native), stdout=open(log, 'wb'),
                            stderr=subprocess.STDOUT)
    lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
    print(f'suite_rc={suite}')
    print(f'suite_ok={sum(1 for line in lines if line.endswith("... ok"))}')
    print(f'suite_failed={sum(1 for line in lines if line.endswith("... FAILED"))}')
    print(f'suite_result_lines={sum(1 for line in lines if "test result:" in line)}')
    print(f'suite_running={sum(1 for line in lines if line.startswith("running "))}')
    print(f'suite_panicked={sum(1 for line in lines if "panicked" in line)}')
    print(f'suite_error_prefix={sum(1 for line in lines if line.startswith("error"))}')
    print(f'suite_exitcode_lines={json.dumps([line[:160] for line in lines if "exit code" in line][:2])}')
    print(f'suite_couldnot_lines={json.dumps([line[:160] for line in lines if "could not" in line][:2])}')
    print(f'suite_lines={len(lines)}')


if __name__ == '__main__':
    main()
