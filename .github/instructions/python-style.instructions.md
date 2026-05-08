---
applyTo: "**/*.py,**/*.pyt"
---

<!-- Generated from AGENTS.md by post_gen_project.py — do not edit directly. -->

### 1. Coding Standards

- **PEP 8**: All Python code must comply with [PEP 8](https://peps.python.org/pep-0008/).
- **Formatting**: Code is formatted with `black` (line length 100). Run `black src testing scripts`
  before committing.
- **Type Hints**: All functions and class methods must include explicit type hints for arguments
  and return values. Style decisions for this project:
    - Add `from __future__ import annotations` at the top of every module so annotations are
      evaluated lazily as strings.
    - Use PEP 604 union syntax: `int | None`, not `Optional[int]` or `Union[int, None]`.
    - Use built-in generics: `list[str]`, `dict[str, int]`, not `List[str]` / `Dict[str, int]`.
    - For ArcPy paths, annotate as `str | os.PathLike[str]` when both are accepted, else `str`.
- **Docstrings**: Use [Google-style](https://google.github.io/styleguide/pyguide.html) docstrings
  with `Args:`, and `Returns:` / `Raises:` sections when applicable. See §2 for an example and
  §3 for admonition syntax used inside docstrings.
- **Code samples in docstrings**: Do not use the `Example:` section header. Use a fenced code
  block with the `python` language tag instead.

### 2. Docstring Example

```python
variable: str = "This is a variable with a docstring example."
"""This variable is an example of how to include a docstring for a variable."""

def example_function(param1: int, param2: str) -> bool:
    """
    Brief description of what the function does.

    !!! note
        Additional notes about the function.

    ??? note "Collapsible Note with Title"
        This is a collapsible note section using a custom title.

    !!! warning
        Warnings about the function usage.

    ```python
    result = example_function(10, "test")
    print(result)
    ```
    
    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        bool: Description of the return value.
    """
    ...
```
