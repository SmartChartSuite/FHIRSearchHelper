'''Setup file for fhirgenerator package'''
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

requirements = ["fhir.resources==7.0.0", "requests==2.28.2", "ruff==0.0.252"]

setuptools.setup(
    name="fhirsearchhelper",
    version="0.0.1",
    author="Andrew Stevens",
    author_email="andrew.stevens@gtri.gatech.edu",
    description="A package to help FHIR searching with needed search parameters are not available",
    install_requires=requirements,
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SmartChartSuite/FHIRSearchHelper",
    project_urls={
        "Bug Tracker": "https://github.com/SmartChartSuite/FHIRSearchHelper/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=setuptools.find_packages(),
    python_requires=">=3.10"
)
