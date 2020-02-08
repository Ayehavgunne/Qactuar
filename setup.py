from qactuar.__version__ import VERSION
from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as fh:
    requirements = fh.readlines()

with open("dev_requirements.txt", "r") as fh:
    dev_requirements = fh.readlines()

setup(
    name="Qactuar",
    version=VERSION,
    description="ASGI compliant web server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Anthony Post",
    author_email="postanthony3000@gmail.com",
    license="MIT License",
    url="https://github.com/Ayehavgunne/Qactuar/",
    packages=find_packages(),
    install_requires=requirements,
    extras_require={"dev": dev_requirements},
    python_requires=">=3.7",
    entry_points={"console_scripts": ["qactuar=qactuar.__main__:main"]},
)
