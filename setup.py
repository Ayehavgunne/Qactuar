from pathlib import Path

from setuptools import find_packages, setup

PROJECT_ROOT = Path(__file__).parent

with (PROJECT_ROOT / "qactuar" / "__init__.py").open("r") as fh:
    for line in fh.readlines():
        if line.startswith("__version__ = "):
            VERSION = line.split("=")[1].strip().replace('"', "")
            break

with (PROJECT_ROOT / "README.md").open("r") as fh:
    long_description = fh.read()

with (PROJECT_ROOT / "requirements.txt").open("r") as fh:
    requirements = fh.readlines()

with (PROJECT_ROOT / "dev_requirements.txt").open("r") as fh:
    dev_requirements = fh.readlines()

with (PROJECT_ROOT / "extra_requirements.txt").open("r") as fh:
    extra_requirements = fh.readlines()

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
    extras_require={"dev": dev_requirements, "extra": extra_requirements},
    python_requires=">=3.7",
    entry_points={"console_scripts": ["qactuar=qactuar.__main__:main"]},
)
