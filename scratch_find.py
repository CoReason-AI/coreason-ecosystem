import importlib
import inspect

def inspect_module(module_name):
    try:
        mod = importlib.import_module(module_name)
        print(f"Found {module_name}")
        for name, obj in inspect.getmembers(mod):
            if name in ['FederatedDiscoveryIntent', 'OracleExecutionReceipt']:
                print(f"Found {name} in {module_name}")
                print(inspect.signature(obj))
    except Exception as e:
        print(f"Error importing {module_name}: {e}")

try:
    from coreason_manifest.intents import FederatedDiscoveryIntent
    from coreason_manifest.receipts import OracleExecutionReceipt
    print("Direct import worked!")
except Exception as e:
    print(f"Direct import failed: {e}")
