from setuptools import setup, find_packages

setup(
    name="pyken",
    version="0.1.0",
    packages=find_packages(),
    # uplc version 1.0.7
    install_requires=[
        "uplc==1.0.7",
    ],  # Add dependencies from requirements.txt if needed
    python_requires=">=3.6",
    long_description=open("README.md").read(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
