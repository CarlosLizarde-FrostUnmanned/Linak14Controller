#!/usr/bin/env python3
"""
Setup script for LINAK 14 Controller
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="linak14-controller",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A Python GUI application for controlling LINAK 14 linear actuators via CAN interface",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/Linak14Controller",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Manufacturing",
        "Topic :: System :: Hardware :: Hardware Drivers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "linak14-controller=main:main",
        ],
    },
    keywords="linak actuator can j1939 gui tkinter automation",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/Linak14Controller/issues",
        "Source": "https://github.com/yourusername/Linak14Controller",
    },
)
