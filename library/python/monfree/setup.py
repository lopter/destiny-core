import setuptools


_ = setuptools.setup(
    name="monfree",
    version="1.0.0",
    author="Louis Opter",
    author_email="louis@opter.org",
    packages=setuptools.find_namespace_packages(),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "monfree = monfree:main",
        ],
    },
)
