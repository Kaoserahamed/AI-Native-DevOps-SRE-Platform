"""Repository automation scripts.

Exposed as a package (rather than implicit namespace modules) so that static analysis resolves each
script exactly once: ``scripts.check_repo_policy`` instead of both ``check_repo_policy`` and
``scripts.check_repo_policy``. Scripts are executed with ``python scripts/<name>.py`` and are also
importable for unit tests.
"""
