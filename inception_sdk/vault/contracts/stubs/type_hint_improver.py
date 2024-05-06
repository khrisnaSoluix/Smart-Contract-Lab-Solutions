# standard libs
import ast
import glob
import os
import sys
from typing import Optional


class TypeHintImprover(ast.NodeTransformer):
    def visit_ClassDef(self, node: ast.ClassDef):
        attributes: dict[ast.Name, ast.AnnAssign] = {}
        init_args: dict[str, Optional[ast.expr]] = {}
        for stmt in node.body:
            # stubgen always defaults types to `Any` annotation so we ignore ast.Assign
            if isinstance(stmt, ast.AnnAssign):
                if isinstance(stmt.target, ast.Name):
                    attributes[stmt.target] = stmt
            # we assume we can infer the class attribute types from the corresponding
            # `__init__` args, which relies on them being named identically
            if isinstance(stmt, ast.FunctionDef) and stmt.name == "__init__":
                # as far as I can tell we only use args and kwonlyargs
                # (i.e. no positional only, *args or **kwargs)
                for arg in stmt.args.args + stmt.args.kwonlyargs:
                    init_args[arg.arg] = arg.annotation

        for attribute_name, assign in attributes.items():
            if annotation := init_args.get(attribute_name.id):
                assign.annotation = annotation
        return self.generic_visit(node)


if __name__ == "__main__":
    stub_directory = sys.argv[1]
    if os.path.exists(stub_directory):
        for stub_filepath in glob.glob(
            f"{os.path.join(stub_directory, '**', '*.pyi')}", recursive=True
        ):
            with open(stub_filepath, mode="r") as stream:
                contents = stream.read()
                module = ast.parse(source=contents)
                module = TypeHintImprover().visit(module)
            with open(stub_filepath, mode="w") as stream:
                new_contents = ast.unparse(module)
                stream.write(new_contents)
    else:
        print(f"Path {stub_directory=} does not exist.")
