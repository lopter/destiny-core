import setuptools


setuptools.setup(
    name="toolbelt",
    version="1.0.0-rc.1",
    author="Louis Opter",
    author_email="louis@opter.org",
    packages=setuptools.find_namespace_packages(),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "clan-destiny = toolbelt:main",
        ],
    },
)
