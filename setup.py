from setuptools import setup, find_packages

setup(
    name="gene-sim",
    version="0.1.0",
    description="Genealogical simulation system for genetic inheritance modeling",
    author="Gene Sim Team",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.24.0",
        "pyyaml>=6.0",
    ],
    python_requires=">=3.10",
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
        ],
    },
)

