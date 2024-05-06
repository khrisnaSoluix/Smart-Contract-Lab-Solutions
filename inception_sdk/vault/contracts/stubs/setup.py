# third party
from setuptools import find_namespace_packages, setup

setup(
    name="contracts_api-stubs",
    version="0.465.1",
    description="contracts_api stubs",
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
            "contracts_api-stubs.*",
            "contracts_api-stubs",
        ]
    ),
    package_data={"": ["*.pyi"]},
    zip_safe=False,
)
