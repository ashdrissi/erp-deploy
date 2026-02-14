from setuptools import setup, find_packages

setup(
    name="orderlift",
    version="1.0.0",
    description="Custom ERP modules for Orderlift — multi-company elevator parts management",
    author="Syntax Line",
    author_email="contact@syntaxline.dev",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
)
