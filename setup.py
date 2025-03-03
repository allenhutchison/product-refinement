"""Setup configuration for the product refinement tool."""
from setuptools import setup, find_packages

setup(
    name="product-refinement",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click>=8.0.0",
        "rich>=10.0.0",
        "llm>=0.12.0",
    ],
    entry_points={
        "console_scripts": [
            "refine=product_refinement.__main__:cli",
        ],
    },
    author="Your Name",
    author_email="your.email@example.com",
    description="A tool for generating and refining product specifications using AI",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/product-refinement",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Documentation",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
) 