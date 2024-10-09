import setuptools


setuptools.setup(
    name="toolbelt",
    version="1.0.0-rc.1",
    author="Louis Opter",
    author_email="louis@opter.org",
    packages=setuptools.find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "multilab = toolbelt.main:main",
        ],
    },
)
