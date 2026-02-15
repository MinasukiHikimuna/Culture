from setuptools import find_packages, setup


setup(
    name="NZB",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "polars",
        "requests",
        "python-dotenv"
    ]
)
