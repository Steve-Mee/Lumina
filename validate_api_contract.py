#!/usr/bin/env python3
"""Quick validation of runtime module API contracts."""
import sys
import importlib.util

# Import the runtime module using importlib
spec = importlib.util.spec_from_file_location("lumina_runtime", "lumina_runtime.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)

critical = [
    'get_current_dream_snapshot',
    'get_mtf_snapshots',
    'generate_price_action_summary',
    'is_significant_event',
    'log_thought',
    'detect_market_regime',
]

print('Checking runtime module API contracts...')
missing = []
for func in critical:
    try:
        obj = getattr(runtime, func)
        status = 'OK (callable)' if callable(obj) else 'WARN (not callable)'
        print(f'  {func}: {status}')
    except AttributeError as e:
        missing.append(func)
        print(f'  {func}: MISSING - {e}')

if missing:
    print(f'\nERROR: {len(missing)} critical functions missing!')
    sys.exit(1)
else:
    print('\nSUCCESS: All critical functions exposed!')
