from setuptools import setup, find_packages
from pathlib import Path

with open("README.md") as file:
    long_description = file.read()

REQUIREMENTS = [
    "requests",
    "ruamel.yaml",
    "paramiko",
    "pycryptodome",
    "python-novaclient",
    "openstacksdk",
    "ansible",
    "ansible-runner",
    "dicttoxml",
]

setup(
    name="micado-client",
    version="0.11.2",
    description="A Python Client Library for MiCADO",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Márk Emődi & Jay DesLauriers",
    python_requires=">=3.8",
    url="https://github.com/micado-scale/micado-client",
    packages=find_packages(exclude=["tests"]),
    project_urls={
        "Bug Tracker": "https://github.com/micado-scale/micado-client/issues",
    },
    install_requires=REQUIREMENTS,
    license="Apache 2.0",
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
)
