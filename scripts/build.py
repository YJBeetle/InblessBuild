#!/usr/bin/env python3
"""Run the pinned private project's checks without publishing raw build logs."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'Inbless'


def build(platform):
    logs = Path(os.environ.get('RUNNER_TEMP', ROOT / '.private-build')) / 'inbless-logs'
    logs.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # Credentials belong to checkout/encryption steps, never to build subprocesses.
    env.pop('ARTIFACT_PASSWORD', None)
    env.pop('INBLESS_READ_TOKEN', None)
    extra = []
    if platform == 'windows-x64':
        extra = ['--protocol-deps', str(SOURCE / '.ci-vcpkg/installed/x64-windows')]
    android = platform == 'android-arm64'
    commands = [
        ('sdk', [sys.executable, 'scripts/build-sdk.py', *( ['--android'] if android else extra)], SOURCE),
        ('frontend-dependencies', ['npm', 'ci'], SOURCE / 'app'),
        ('stage-runtime', [sys.executable, 'scripts/stage-native.py', *( ['--android'] if android else [])], SOURCE),
        ('format', ['cargo', 'fmt', '--all', '--check'], SOURCE),
        ('clippy', ['cargo', 'clippy', '--workspace', '--all-targets', '--locked', '--', '-D', 'warnings'], SOURCE),
        ('tests', [sys.executable, 'scripts/test.py'], SOURCE),
    ]
    if android:
        # Gradle assembles and self-signs the APK; a keystore is only needed for stores.
        commands.append(('apk', ['npm', 'run', 'tauri', '--', 'android', 'build', '-t', 'aarch64',
                                 '--', '--locked'], SOURCE / 'app'))
    else:
        commands.append(('installers', ['npm', 'run', 'tauri', '--', 'build', '--bundles',
                        'app,dmg' if platform == 'macos-arm64' else 'nsis' if platform == 'windows-x64' else 'deb',
                        *([] if platform == 'macos-arm64' else ['--no-sign']), '--', '--locked'], SOURCE / 'app'))
    commands.append(('verify-packages', [sys.executable, 'scripts/package-artifacts.py', '--platform', platform], SOURCE))
    # npm is a command script on Windows; resolve it explicitly for CreateProcess.
    if os.name == 'nt':
        import shutil
        for _, command, _ in commands:
            if command[0] == 'npm':
                command[:1] = ['cmd.exe', '/d', '/c', shutil.which('npm.cmd') or 'npm.cmd']
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip()
    (logs / 'revision.txt').write_text(revision + '\n', encoding='utf-8')
    for name, command, cwd in commands:
        print(f'::group::{name}', flush=True)
        try:
            with (logs / (name + '.log')).open('wb') as output:
                result = subprocess.run(command, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT)
            if result.returncode:
                print(f'::error::{name} failed (exit {result.returncode}); details are in the encrypted logs.', flush=True)
                return 1
            print(f'{name}: passed', flush=True)
        except OSError:
            print(f'::error::{name} could not start; check runner prerequisites.', flush=True)
            return 1
        finally:
            print('::endgroup::', flush=True)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', required=True, choices=['linux-x64', 'windows-x64', 'macos-arm64', 'android-arm64'])
    raise SystemExit(build(parser.parse_args().platform))
