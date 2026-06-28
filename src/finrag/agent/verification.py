import ast
import io
import sys
from typing import Any, Dict, Set


class SafeASTVisitor(ast.NodeVisitor):
    """AST visitor to verify that Python code contains only mathematical whitelisted nodes."""

    def __init__(self, whitelisted_calls: Set[str]) -> None:
        self.whitelisted_calls = whitelisted_calls

    def visit(self, node: ast.AST) -> None:
        allowed_types = (
            ast.Module,
            ast.Expr,
            ast.Assign,
            ast.Name,
            ast.Store,
            ast.Load,
            ast.Constant,
            ast.BinOp,
            ast.UnaryOp,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.Mod,
            ast.Pow,
            ast.FloorDiv,
            ast.USub,
            ast.UAdd,
            ast.Call,
            ast.Compare,
            ast.Eq,
            ast.NotEq,
            ast.Lt,
            ast.LtE,
            ast.Gt,
            ast.GtE,
            ast.In,
            ast.NotIn,
            ast.List,
            ast.Tuple,
            ast.Dict,
            ast.Set,
            ast.Subscript,
            ast.Slice,
        )

        if not isinstance(node, allowed_types):
            raise ValueError(f"Disallowed AST node type: {type(node).__name__}")

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Disallowed non-name function call.")
            if node.func.id not in self.whitelisted_calls:
                raise ValueError(f"Disallowed function call: {node.func.id}")

        self.generic_visit(node)


class MathValidationSandbox:
    """A secure, isolated execution sandbox for evaluating arithmetic expressions and calculations.

    Uses abstract syntax tree (AST) traversal to block system calls, imports, and unsafe attributes.
    """

    def __init__(self) -> None:
        self.whitelisted_calls = {
            "print",
            "abs",
            "round",
            "sum",
            "min",
            "max",
            "len",
            "float",
            "int",
            "str",
            "list",
            "dict",
            "set",
            "range",
        }

    def execute(self, code_str: str) -> Dict[str, Any]:
        """Verify and execute code string, returning defined variables and standard output.

        Args:
            code_str: The Python calculation source code.

        Returns:
            A dict containing success flag, stdout, defined variables, and any error message.
        """
        if not code_str.strip():
            return {
                "success": True,
                "error": None,
                "stdout": "",
                "variables": {},
            }

        # 1. Parse AST and perform safety scan
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            return {
                "success": False,
                "error": f"SyntaxError: {e}",
                "stdout": "",
                "variables": {},
            }

        visitor = SafeASTVisitor(self.whitelisted_calls)
        try:
            visitor.visit(tree)
        except ValueError as e:
            return {
                "success": False,
                "error": f"SecurityError: {e}",
                "stdout": "",
                "variables": {},
            }

        # 2. Redirect standard out
        stdout_buffer = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = stdout_buffer

        # 3. Setup sandboxed builtins
        safe_builtins = {
            "abs": abs,
            "round": round,
            "sum": sum,
            "min": min,
            "max": max,
            "len": len,
            "float": float,
            "int": int,
            "str": str,
            "list": list,
            "dict": dict,
            "set": set,
            "range": range,
        }

        def custom_print(*args: Any, **kwargs: Any) -> None:
            print(*args, file=stdout_buffer, **kwargs)

        safe_builtins["print"] = custom_print

        local_scope: Dict[str, Any] = {}
        global_scope = {"__builtins__": safe_builtins}

        success = True
        error_msg = None

        try:
            compiled = compile(tree, filename="<sandbox>", mode="exec")
            exec(compiled, global_scope, local_scope)
        except Exception as e:
            success = False
            error_msg = f"RuntimeError: {type(e).__name__}: {e}"
        finally:
            sys.stdout = old_stdout

        return {
            "success": success,
            "error": error_msg,
            "stdout": stdout_buffer.getvalue(),
            "variables": local_scope,
        }
