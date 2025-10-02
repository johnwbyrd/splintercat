#!/usr/bin/env python3
import select
import subprocess
import sys
from pathlib import Path

import yaml


class Result:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

class CommandRunner:
    def __init__(self, interactive=False):
        self.interactive = interactive

    def run(self, cmd, stdin=None, check=True):
        """
        Run a command with optional stdin.
        cmd: command string (will use shell) or list of args (no shell)
        stdin: optional string to pass as stdin
        check: whether to warn on failure
        """
        if self.interactive:
            if isinstance(cmd, str):
                print(f"\nCommand: {cmd}")
            else:
                print(f"\nCommand: {' '.join(cmd)}")
            if stdin:
                print(f"stdin: {len(stdin)} bytes")
            input("Press Enter to execute...")

        # Determine if we need shell
        use_shell = isinstance(cmd, str)

        process = subprocess.Popen(
            cmd,
            shell=use_shell,
            stdin=subprocess.PIPE if stdin else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if stdin:
            # If we have stdin, use communicate (simpler, no real-time display needed for stdin case)
            stdout, stderr = process.communicate(input=stdin)
            if stdout:
                print(stdout, end='')
            if stderr:
                print(stderr, end='', file=sys.stderr)
            result = Result(process.returncode, stdout, stderr)
        else:
            # No stdin - use select for real-time output
            stdout_lines = []
            stderr_lines = []

            while True:
                reads = [process.stdout.fileno(), process.stderr.fileno()]
                ret = select.select(reads, [], [], 0.1)

                for fd in ret[0]:
                    if fd == process.stdout.fileno():
                        line = process.stdout.readline()
                        if line:
                            stdout_lines.append(line)
                            print(line, end='')
                    if fd == process.stderr.fileno():
                        line = process.stderr.readline()
                        if line:
                            stderr_lines.append(line)
                            print(line, end='', file=sys.stderr)

                if process.poll() is not None:
                    # Read any remaining output
                    remaining_out = process.stdout.read()
                    remaining_err = process.stderr.read()
                    if remaining_out:
                        stdout_lines.append(remaining_out)
                        print(remaining_out, end='')
                    if remaining_err:
                        stderr_lines.append(remaining_err)
                        print(remaining_err, end='', file=sys.stderr)
                    break

            result = Result(process.returncode, ''.join(stdout_lines), ''.join(stderr_lines))

        if check and result.returncode != 0 and not self.interactive:
            print(f"WARNING: Command failed with return code {result.returncode}")
            if result.stderr:
                print(f"stderr: {result.stderr}")

        return result

class Source:
    def __init__(self, config, runner, batch_size=20):
        self.config = config
        self.cmds = config['commands']
        self.runner = runner
        self.batch_size = batch_size

    def get_patches(self):
        self.runner.run(self.cmds['fetch'].format(**self.config))
        merge_base = self.runner.run(self.cmds['merge_base'].format(**self.config)).stdout.strip()
        if not merge_base:
            return []
        commits = self.runner.run(self.cmds['list_commits'].format(merge_base=merge_base, batch_size=self.batch_size, **self.config)).stdout.strip().split('\n')
        if not commits[0]:
            return []
        patches = []
        for c in commits:
            diff = self.runner.run(self.cmds['format_patch'].format(commit=c, **self.config)).stdout
            if diff:
                patches.append({'id': c, 'diff': diff})
        return patches

class Target:
    def __init__(self, config, test_cmd, runner):
        self.config = config
        self.cmds = config['commands']
        self.test_cmd = test_cmd
        self.runner = runner
        self.runner.run(self.cmds['checkout'].format(**self.config))

    def current_state(self):
        return self.runner.run(self.cmds['get_state'].format(**self.config)).stdout.strip()

    def apply(self, patches):
        for p in patches:
            # Use stdin to pass patch, avoiding shell escaping issues
            cmd = self.cmds['apply'].format(**self.config)
            result = self.runner.run(cmd, stdin=p['diff'], check=False)
            if result.returncode != 0:
                print(f"Patch application failed with return code {result.returncode}")
                print(f"Command was: {cmd}")
                print(f"Patch size: {len(p['diff'])} bytes")
                if result.stderr:
                    print(f"stderr: {result.stderr}")
                if result.stdout:
                    print(f"stdout: {result.stdout}")
                return False
        print("Patch applied successfully")
        return True

    def test(self):
        result = self.runner.run(self.test_cmd.format(**self.config), check=False)
        if result.returncode == 0:
            print("Build/test succeeded")
        else:
            print(f"Build/test failed with return code {result.returncode}")
            if result.stderr:
                print(f"stderr: {result.stderr}")
        return result.returncode == 0

    def commit(self, patches):
        self.runner.run(self.cmds['add'].format(**self.config))
        msg = f"Apply {len(patches)} patches"
        self.runner.run(self.cmds['commit'].format(message=msg, **self.config))

    def rollback(self, state):
        self.runner.run(self.cmds['rollback'].format(state=state, **self.config))

class Strategy:
    def __init__(self, config):
        self.batch_size = config.get('batch_size', 20)

    def run(self, source, target):
        patches = source.get_patches()[:self.batch_size]
        print(f"Found {len(patches)} patches")

        for patch in patches:
            state = target.current_state()
            if target.apply([patch]) and target.test():
                target.commit([patch])
                print(f"PASS {patch['id'][:8]}")
            else:
                target.rollback(state)
                print(f"FAIL {patch['id'][:8]}")

def main():
    config = yaml.safe_load(Path("config.yaml").read_text())
    interactive = config.get('interactive', True)
    batch_size = config['strategy'].get('batch_size', 20)

    runner = CommandRunner(interactive=interactive)
    source = Source(config['source'], runner, batch_size)
    target = Target(config['target'], config['test_command'], runner)
    strategy = Strategy(config['strategy'])

    strategy.run(source, target)

if __name__ == "__main__":
    main()

