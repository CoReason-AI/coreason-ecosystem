import importlib
import pkgutil
import coreason_manifest

def get_all_submodules(module):
    submodules = []
    if hasattr(module, '__path__'):
        for _, name, _ in pkgutil.walk_packages(module.__path__, module.__name__ + '.'):
            submodules.append(name)
    return submodules

with open('scratch_out_utf8.txt', 'w', encoding='utf-8') as f:
    f.write("Submodules of coreason_manifest:\n")
    for sub in get_all_submodules(coreason_manifest):
        f.write(sub + "\n")
        try:
            mod = importlib.import_module(sub)
            f.write(f"  Dir: {dir(mod)}\n")
        except Exception as e:
            f.write(f"  Error: {e}\n")
