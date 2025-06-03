import ast
import pathlib


def _load_generar_contrasena():
    """Load the ``generar_contraseña`` function from module4 without importing
    external dependencies.
    """
    path = pathlib.Path(__file__).resolve().parents[1] / 'modules' / 'module4.py'
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source, filename=str(path))
    func_node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == 'generar_contraseña'
    )
    module = ast.Module(body=[func_node], type_ignores=[])
    ns = {}
    exec(compile(module, filename=str(path), mode='exec'), ns)
    func = ns['generar_contraseña']
    # Provide required globals
    import random, string
    func.__globals__.update({'random': random, 'string': string})
    return func


def test_generar_contrasena_basics():
    generar_contrasena = _load_generar_contrasena()
    password = generar_contrasena(12)
    assert len(password) == 12
    assert any(c.islower() for c in password), "Debe contener minúsculas"
    assert any(c.isupper() for c in password), "Debe contener mayúsculas"
    assert any(c.isdigit() for c in password), "Debe contener dígitos"
    specials = set("!@#$%&*")
    assert any(c in specials for c in password), "Debe contener caracteres especiales"
