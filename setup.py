import os
import re
import setuptools
import types

MAIN_MODULE_NAME = "yuyo"
TARGET_PROJECT_NAME = "hikari-yuyo"


def load_meta_data():
    pattern = re.compile(r"__(?P<key>\w+)__\s=\s\"(?P<value>.+)\"")
    with open(os.path.join(MAIN_MODULE_NAME, "about.py"), "r") as file:
        code = file.read()

    groups = dict(group.groups() for group in pattern.finditer(code))
    return types.SimpleNamespace(**groups)


metadata = load_meta_data()

with open("requirements.txt") as f:
    REQUIREMENTS = f.readlines()

with open("README.md") as f:
    README = f.read()


setuptools.setup(
    name=TARGET_PROJECT_NAME,
    url=metadata.url,
    version=metadata.version,
    packages=setuptools.find_namespace_packages(include=[f"{MAIN_MODULE_NAME}*"]),
    author=metadata.author,
    author_email=metadata.email,
    license=metadata.license,
    description="A collection of utility classes and functions for use with Hikari",
    long_description=README,
    long_description_content_type="text/markdown",
    include_package_data=True,
    install_requires=REQUIREMENTS,
    python_requires=">=3.8.0,<3.10",
    classifiers=[
        "Development Status :: 1 - Planning",
        "License :: OSI Approved :: BSD License",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Communications :: Chat",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
        "Typing :: Typed",
    ],
)
