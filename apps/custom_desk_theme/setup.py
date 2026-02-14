from setuptools import setup, find_packages

setup(
    name="custom_desk_theme",
    version="1.0.0",
    description="Custom Desk theme for Orderlift ERPNext — branded sidebar, navbar, and UI",
    author="Syntax Line",
    author_email="contact@syntaxline.dev",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
)
