import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="reflex_wrapper",
    version="0.0.2",
    author="Baptiste Ferrand",
    author_email="bferrand.maths@gmail.com",
    description="A custom wrapper on top of the reflex library to ease creating and interacting with custom components.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/B4PT0R/reflex_wrapper",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "reflex>=0.4.8",
    ],
    python_requires='>=3.6',
)