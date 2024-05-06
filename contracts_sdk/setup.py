import os
from setuptools import setup  # type: ignore


CWD = os.path.dirname(__file__)
# Need to strip() because bash script defaults CONTRACTS_API_VERSION to " " when not set
CONTRACTS_API_VERSION = os.environ.get("CONTRACTS_API_VERSION", "").strip() or "0.0.0+latest"


setup(
    name="contracts_api",
    version=CONTRACTS_API_VERSION,
    author="Thought Machine",
    author_email="press@thoughtmachine.net",
    description="Contracts Langauge API 4.0 framework for Vault banking Product development.",
    license="All rights reserved",
    keywords="smart contracts core banking thought machine vault api product",
    url="https://www.thoughtmachine.net",
    packages=[
        "contracts_api",
        "contracts_api.utils",
        "contracts_api.versions.version_400.common",
        "contracts_api.versions.version_400.common.types",
        "contracts_api.versions.version_400.smart_contracts",
        "contracts_api.versions.version_400.supervisor_contracts",
    ],
    package_dir={"contracts_api": "."},
    long_description=open(os.path.join(CWD, "README_PACKAGE.md")).read(),
    python_requires=">=3.9",
    install_requires=["python-dateutil"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: Copyright Thought Machine :: All rights reserved",
    ],
)
