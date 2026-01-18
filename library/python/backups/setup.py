import setuptools


setuptools.setup(
    name="backups",
    version="0.0.1",
    author="Louis Opter",
    author_email="louis@opter.org",
    description="Dump and restore backups using rsync or restic.",
    packages=setuptools.find_namespace_packages(),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "clan-destiny-backups=clan_destiny.backups.__main__:main",
        ]
    },
)  # pyright: ignore[reportUnusedCallResult]
