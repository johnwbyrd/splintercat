#!/usr/bin/env python3
import subprocess
import yaml
from pathlib import Path

def run(cmd, check=True):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"WARNING: {cmd}\n{result.stderr}")
    return result

class Source:
    def __init__(self, config):
        self.config = config
        self.cmds = config['commands']
    
    def get_patches(self):
        run(self.cmds['fetch'].format(**self.config))
        merge_base = run(self.cmds['merge_base'].format(**self.config)).stdout.strip()
        if not merge_base:
            return []
        commits = run(self.cmds['list_commits'].format(merge_base=merge_base, **self.config)).stdout.strip().split('\n')
        if not commits[0]:
            return []
        patches = []
        for c in commits:
            diff = run(self.cmds['format_patch'].format(commit=c)).stdout
            if diff:
                patches.append({'id': c, 'diff': diff})
        return patches

class Target:
    def __init__(self, config, test_cmd):
        self.config = config
        self.cmds = config['commands']
        self.test_cmd = test_cmd
        run(self.cmds['checkout'].format(**self.config))
    
    def current_state(self):
        return run(self.cmds['get_state'].format(**self.config)).stdout.strip()
    
    def apply(self, patches):
        for p in patches:
            result = run(self.cmds['apply'].format(diff=p['diff'].replace("'", "'\\''"), **self.config), check=False)
            if result.returncode != 0:
                return False
        return True
    
    def test(self):
        return run(self.test_cmd, check=False).returncode == 0
    
    def commit(self, patches):
        run(self.cmds['add'].format(**self.config))
        msg = f"Apply {len(patches)} patches"
        run(self.cmds['commit'].format(message=msg, **self.config))
    
    def rollback(self, state):
        run(self.cmds['rollback'].format(state=state, **self.config))

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
                print(f"✓ {patch['id'][:8]}")
            else:
                target.rollback(state)
                print(f"✗ {patch['id'][:8]}")

def main():
    config = yaml.safe_load(Path("config.yaml").read_text())
    
    source = Source(config['source'])
    target = Target(config['target'], config['test_command'])
    strategy = Strategy(config['strategy'])
    
    strategy.run(source, target)

if __name__ == "__main__":
    main()

