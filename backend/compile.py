from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules=cythonize(
        [
            "app/services/tax_engine.py",
            "app/services/sync_engine.py",
            "app/services/export_service.py",
            "app/services/label_service.py",
        ],
        compiler_directives={"language_level": "3"},
    )
)
