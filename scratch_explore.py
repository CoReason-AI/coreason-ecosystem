import importlib
import pkgutil
import coreason_manifest

def get_all_submodules(module):
    submodules = []
    if hasattr(module, '__path__'):
        for _, name, _ in pkgutil.walk_packages(module.__path__, module.__name__ + '.'):
            submodules.append(name)
    return submodules

print("Submodules of coreason_manifest:")
for sub in get_all_submodules(coreason_manifest):
    print(sub)
    try:
        mod = importlib.import_module(sub)
        print(f"  Dir: {dir(mod)}")
    except Exception as e:
        print(f"  Error: {e}")
