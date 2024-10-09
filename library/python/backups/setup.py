import setuptools


setuptools.setup(
    name="multilab-backups",
    version="0.0.1",
    author="Louis Opter",
    author_email="louis@opter.org",
    description="Dump and restore backups using rsync or restic.",
    packages=setuptools.find_namespace_packages("src"),
    package_dir={"": "src"},
    install_requires=[
        "click",
    ],
    entry_points={
        "console_scripts": [
            "multilab-backups-dump=multilab.backups.dump.__main__:main",
            "multilab-backups-restore=multilab.backups.restore.__main__:main",
        ]
    },
)
