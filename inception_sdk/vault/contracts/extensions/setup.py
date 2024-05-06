# third party
from setuptools import find_namespace_packages, setup

setup(
    name="contracts_api_extensions",
    version="0.460.2",
    description="contracts_api_extensions",
    classifiers=[
        "Development Status :: 1 - Planning",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
    packages=find_namespace_packages(
        include=[
            "contracts_api_extensions.*",
            "contracts_api_extensions",
        ]
    ),
    package_data={"": ["*.pyi", "*.py"]},
    zip_safe=False,
)
