from setuptools import setup, find_packages

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