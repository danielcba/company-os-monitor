"""Guard arquitectónico de regresión: superficie JWT.

Analiza estáticamente (``ast``) el código de producción y detecta:

1. Importaciones de la biblioteca no autorizada (``jose`` / python-jose).
2. Llamadas de decodificación JWT fuera de los envoltorios autorizados.
3. Allowlists de algoritmos que no puedan demostrarse estáticamente.
4. Patrones dinámicos que pueden ocultar una ruta JWT
   (``getattr(...,"decode")``, importación dinámica, ``eval``/``exec``).

No ejecuta código del proyecto ni de pruebas. Solo inspecciona árboles
sintácticos. Los archivos de prueba, fixtures y ejemplos quedan fuera del
ámbito de escaneo (quedan bajo la política de revisión humana).

Limitaciones documentadas: no resuelve aliases de atributos arbitrarios ni
ejecuta código dinámico; se declara sobre las formas estáticas principales,
que son las usadas por el código actual. La excepción es el atributo
``self.algorithm``, que el constructor de ``JwtService`` /
``MachineJwtService`` restringe a HS256 o RS256, por lo que se acepta como
elemento de allowlist demostrable.
"""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_DIRS = [
    PROJECT_ROOT / "libs",
    *(p for p in PROJECT_ROOT.glob("apps/*/src") if p.is_dir()),
]

# Envolturas de decodificación autorizadas (nombre cualificado de función).
AUTHORIZED_DECODE_WRAPPERS = {
    "JwtService.decode",
    "MachineJwtService.decode",
    "_decode_verified",
}

ALLOWED_ALGORITHMS = {"HS256", "RS256"}

# Profundidad de pila que indica un método de clase (clase + método).
_WRAPPER_STACK_DEPTH = 2

# Argumentos mínimos de getattr(obj, "decode").
_GETATTR_DECODE_ARGS = 2

JWT_DECODE_CALLS = {"jwt.decode", "jwt.decode_complete"}


class JWTGuardScanner(ast.NodeVisitor):
    """Recorre un árbol AST y recopila hallazgos sobre la superficie JWT."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.findings: list[str] = []
        self._stack: list[str] = []  # pila de nombres de función abiertos
        # Nombres vinculados al módulo jwt o a su función decode.
        self._jwt_bindings: dict[str, str] = {}
        # Nombres obtenidos mediante getattr(..., "decode"): rutas opacas.
        self._opaque_decode_names: set[str] = set()

    # ------------------------------------------------------------------
    # Importaciones
    # ------------------------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.asname or alias.name
            if alias.name == "jose" or alias.name.startswith("jose."):
                self.findings.append(
                    f"{self.filename}:{node.lineno}: "
                    f"importación no autorizada de la biblioteca 'jose': {alias.name}"
                )
            if alias.name == "jwt":
                self._jwt_bindings[name] = "module"
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if module == "jose" or module.startswith("jose."):
            self.findings.append(
                f"{self.filename}:{node.lineno}: "
                f"importación no autorizada desde 'jose': {module}"
            )
        if module == "jwt":
            for alias in node.names:
                self._jwt_bindings[alias.asname or alias.name] = alias.name
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Seguimiento de envoltura actual
    # ------------------------------------------------------------------
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_AsyncClassDef(self, node: ast.AsyncClassDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def _current_wrapper(self) -> str | None:
        if not self._stack:
            return None
        if len(self._stack) >= _WRAPPER_STACK_DEPTH:
            qualified = f"{self._stack[-2]}.{self._stack[-1]}"
        else:
            qualified = self._stack[-1]
        return qualified if qualified in AUTHORIZED_DECODE_WRAPPERS else None

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            value = node.value
            if not isinstance(value, ast.Call):
                continue
            func = value.func
            getattr_func = (
                func.id == "getattr"
                if isinstance(func, ast.Name)
                else (
                    isinstance(func, ast.Attribute) and func.attr == "getattr"
                )
            )
            if (
                getattr_func
                and len(value.args) >= _GETATTR_DECODE_ARGS
                and isinstance(value.args[1], ast.Constant)
                and value.args[1].value == "decode"
            ):
                self._opaque_decode_names.add(target.id)
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Detección de llamadas de decodificación
    # ------------------------------------------------------------------
    def _is_jwt_attribute_decode(self, node: ast.Call) -> bool:
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "decode"):
            return False
        if not isinstance(func.value, ast.Name):
            return False
        kind = self._jwt_bindings.get(func.value.id)
        return kind in ("module", "decode")

    def _is_direct_decode_call(self, node: ast.Call) -> bool:
        if not isinstance(node.func, ast.Name):
            return False
        return self._jwt_bindings.get(node.func.id) == "decode"

    @staticmethod
    def _element_is_permitted_algorithm(elt: ast.expr) -> bool:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            return elt.value in ALLOWED_ALGORITHMS
        # self.algorithm: el constructor lo restringe a HS256 o RS256.
        return (
            isinstance(elt, ast.Attribute)
            and isinstance(elt.value, ast.Name)
            and elt.value.id == "self"
            and elt.attr == "algorithm"
        )

    @staticmethod
    def _is_suspicious_import(node: ast.Call) -> bool:
        """Un ``__import__`` es sospechoso si el módulo es opaco o es JWT."""
        if not node.args:
            return True
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value in {"jwt", "pyjwt", "jose"}
        return True

    @staticmethod
    def _algorithms_allowlist_is_static(node: ast.Call) -> bool:
        for kw in node.keywords:
            if kw.arg != "algorithms":
                continue
            value = kw.value
            if not isinstance(value, ast.List) or not value.elts:
                return False
            return all(
                JWTGuardScanner._element_is_permitted_algorithm(elt)
                for elt in value.elts
            )
        # Sin ``algorithms`` explícito no hay allowlist demostrable.
        return False

    def _report_decode(self, node: ast.Call, reason: str) -> None:
        wrapper = self._current_wrapper()
        if wrapper is not None:
            # Dentro de un envoltorio autorizado: solo se exige allowlist.
            if not self._algorithms_allowlist_is_static(node):
                self.findings.append(
                    f"{self.filename}:{node.lineno}: "
                    f"decodificación JWT en '{wrapper}' sin allowlist de algoritmos "
                    "demostrable estáticamente"
                )
            return
        self.findings.append(
            f"{self.filename}:{node.lineno}: "
            f"decodificación JWT fuera de un envoltorio autorizado ({reason})"
        )

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func

        if isinstance(func, ast.Attribute) and func.attr in {"decode", "decode_complete"}:
            if isinstance(func.value, ast.Name):
                kind = self._jwt_bindings.get(func.value.id)
                if kind in ("module", "decode"):
                    self._report_decode(node, "jwt.decode / jwt.decode_complete")
                elif any(kw.arg == "algorithms" for kw in node.keywords):
                    self.findings.append(
                        f"{self.filename}:{node.lineno}: "
                        "llamada a '.decode()' con 'algorithms' sobre receptor "
                        "no jwt: ruta JWT opaca al análisis estático"
                    )
            elif any(kw.arg == "algorithms" for kw in node.keywords):
                self.findings.append(
                    f"{self.filename}:{node.lineno}: "
                    "llamada dinámica a '.decode()' con 'algorithms' sobre "
                    "receptor no literal: ruta JWT opaca al análisis estático"
                )
        elif isinstance(func, ast.Name):
            if self._is_direct_decode_call(node):
                self._report_decode(node, "llamada directa a jwt.decode")
            elif func.id in self._opaque_decode_names:
                self.findings.append(
                    f"{self.filename}:{node.lineno}: "
                    "llamada a nombre vinculado con getattr(..., 'decode'): "
                    "ruta JWT opaca al análisis estático"
                )

        # Otros patrones dinámicos que pueden ocultar rutas JWT.
        if isinstance(func, ast.Name) and func.id == "__import__":
            if self._is_suspicious_import(node):
                self.findings.append(
                    f"{self.filename}:{node.lineno}: "
                    f"importación dinámica '{func.id}' que puede ocultar una ruta JWT"
                )
        elif isinstance(func, ast.Name) and func.id in {"eval", "exec"}:
            self.findings.append(
                f"{self.filename}:{node.lineno}: "
                f"ejecución dinámica '{func.id}' que puede ocultar una ruta JWT"
            )
        if isinstance(func, ast.Attribute) and func.attr == "import_module":
            self.findings.append(
                f"{self.filename}:{node.lineno}: "
                "importlib.import_module que puede ocultar una ruta JWT"
            )
        self.generic_visit(node)


def scan_source(code: str, filename: str = "<synthetic>") -> list[str]:
    """Analiza una cadena de código y devuelve los hallazgos del guard."""
    tree = ast.parse(code, filename=filename)
    scanner = JWTGuardScanner(filename)
    scanner.visit(tree)
    return scanner.findings


def scan_file(path: Path) -> list[str]:
    """Analiza un archivo de producción y devuelve los hallazgos del guard."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    scanner = JWTGuardScanner(str(path.relative_to(PROJECT_ROOT)))
    scanner.visit(tree)
    return scanner.findings


def production_files() -> list[Path]:
    """Archivos de producción sujetos al guard (excluye tests/fixtures/ejemplos)."""
    files: list[Path] = []
    for directory in PRODUCTION_DIRS:
        files.extend(sorted(directory.rglob("*.py")))
    return files


# ---------------------------------------------------------------------------
# Pruebas sintácticas: código en memoria, sin modificar producción
# ---------------------------------------------------------------------------

AUTHORIZED_OK = '''
from jwt import PyJWTError, decode as jwt_decode, encode as jwt_encode


def _decode_verified(token, key, *, audience, issuer, skip):
    claims = jwt_decode(token, key, algorithms=["HS256"], options={"verify_aud": False})
    return claims


class JwtService:
    def decode(self, token, key):
        claims = jwt_decode(token, key, algorithms=["HS256"], options={"verify_aud": False})
        return claims
'''

DIRECT_DECODE_OUTSIDE = '''
from jwt import decode as jwt_decode

def decode(token, key):
    return jwt_decode(token, key, algorithms=["HS256"])
'''

ALIAS_DECODE_OUTSIDE = '''
from jwt import decode as jose_jwt

def decode(token, key):
    return jose_jwt.decode(token, key, algorithms=["HS256"])
'''

DECODE_KWARGS_OUTSIDE = '''
from jwt import decode

def decode(token, key, decode_kwargs):
    return decode(**decode_kwargs)
'''

NO_ALLOWLIST_IN_WRAPPER = '''
class MachineJwtService:
    def decode(self, token, key):
        import jwt
        return jwt.decode(token, key, options={"verify_aud": False})
'''

DYNAMIC_GETATTR = '''
def decode_token(obj, token, key):
    method = getattr(obj, "decode")
    return method(token, key, algorithms=["HS256"])
'''

DYNAMIC_IMPORT = '''
def decode_token(token, key):
    mod = __import__("jwt")
    return mod.decode(token, key, algorithms=["HS256"])
'''

BAD_JOSE_IMPORT = '''
from jose import jwt
'''


def test_guard_no_hallazgos_en_codigo_de_produccion_actual() -> None:
    """La superficie actual migrada no debe producir hallazgos del guard."""
    for path in production_files():
        findings = scan_file(path)
        assert not findings, f"{path}: {findings}"


def test_envoltura_autorizada_con_allowlist_estatico_pasa() -> None:
    findings = scan_source(AUTHORIZED_OK)
    assert findings == [], findings


def test_decodificacion_directa_fuera_de_envoltorio_falla() -> None:
    findings = scan_source(DIRECT_DECODE_OUTSIDE)
    assert any("fuera de un envoltorio autorizado" in f for f in findings), findings


def test_alias_de_import_fuera_de_envoltorio_falla() -> None:
    findings = scan_source(ALIAS_DECODE_OUTSIDE)
    assert any("fuera de un envoltorio autorizado" in f for f in findings), findings


def test_decode_kwargs_fuera_de_envoltorio_falla() -> None:
    findings = scan_source(DECODE_KWARGS_OUTSIDE)
    assert any("fuera de un envoltorio autorizado" in f for f in findings), findings


def test_allowlist_no_estatico_dentro_de_envoltorio_falla() -> None:
    findings = scan_source(NO_ALLOWLIST_IN_WRAPPER)
    assert any("allowlist de algoritmos" in f for f in findings), findings


def test_getattr_dinamico_produce_diagnostico() -> None:
    findings = scan_source(DYNAMIC_GETATTR)
    assert any("getattr" in f for f in findings), findings


def test_import_dinamico_produce_diagnostico() -> None:
    findings = scan_source(DYNAMIC_IMPORT)
    assert any("dinámica" in f for f in findings), findings


def test_import_jose_es_rechazado() -> None:
    findings = scan_source(BAD_JOSE_IMPORT)
    assert any("no autorizada" in f and "jose" in f for f in findings), findings


def test_codigo_de_prueba_queda_fuera_del_ambito_de_escaneo() -> None:
    """El guard escanea producción (libs y apps/*/src), no tests."""
    assert not any("tests" in str(p) for p in production_files())
    synthetic = PROJECT_ROOT / "tests" / "architecture" / "_guard_synthetic_probe.py"
    synthetic.write_text(DIRECT_DECODE_OUTSIDE, encoding="utf-8")
    try:
        assert not any(str(p).endswith("_guard_synthetic_probe.py") for p in production_files())
    finally:
        synthetic.unlink(missing_ok=True)


def test_renombrar_variable_no_cambia_resultado() -> None:
    """Un renombrado inocuo de variables internas no altera el resultado."""
    findings_a = scan_source(AUTHORIZED_OK)
    renamed = (
        AUTHORIZED_OK.replace("claims = ", "token_claims = ")
        .replace("return claims", "return token_claims")
        .replace("_validate_aud_claims(claims,", "_validate_aud_claims(token_claims,")
    )
    findings_b = scan_source(renamed)
    assert findings_a == []
    assert findings_b == findings_a, findings_b
