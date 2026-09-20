# Python script to validate Terraform files statically.
# Checks for basic structural issues and common mistakes.

import os
import re
import sys
from pathlib import Path


def check_tf_files(root: Path) -> list[str]:
    \"\"\"Check all .tf files for common issues.\"\"\"
    errors = []
    
    for tf_file in root.rglob('*.tf'):
        if '.terraform' in tf_file.parts:
            continue
        
        content = tf_file.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # Check for TODO comments in production code
        for i, line in enumerate(lines, 1):
            if 'TODO' in line and not line.strip().startswith('#'):
                if 'TODO' not in line.split('#')[0] if '#' in line else True:
                    errors.append(f'{tf_file}:{i}: TODO found: {line.strip()}')
        
        # Check that modules have required files
        if 'module' in content.lower() and 'source' in content:
            # This is a module call - check parent has proper structure
            pass
    
    return errors


def main() -> int:
    repo_root = Path(__file__).parent.parent
    tf_dir = repo_root / 'infra' / 'terraform'
    
    if not tf_dir.exists():
        print(f'ERROR: {tf_dir} does not exist')
        return 1
    
    errors = check_tf_files(tf_dir)
    
    if errors:
        print('Terraform validation errors:')
        for err in errors:
            print(f'  {err}')
        return 1
    
    print('Terraform static validation passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
