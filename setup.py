from setuptools import setup, find_packages
from pathlib import Path

with open("README.md") as file:
    long_description = file.read()

REQUIREMENTS = [
    "requests",
    "ruamel.yaml",
    "pycryptodome",
    "python-novaclient",
    "openstacksdk",
    "ansible",
]

setup(
    name="micado-client",
    version="0.9.2-dev",
    description="A Python Client Library for MiCADO",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Márk Emődi & Jay DesLauriers",
    python_requires=">=3.6",
    url="https://github.com/micado-scale/micado-client",
    packages=find_packages(exclude=["tests"]),
    install_requires=REQUIREMENTS,
    license="Apache 2.0",
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
)
