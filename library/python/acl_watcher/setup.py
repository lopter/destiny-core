import setuptools

setuptools.setup(
    name="acl-watcher",
    version="1.0.0-rc.1",
    description=(
        "Watch for changes in a list of directories and adjust ownership "
        "and permissions of new files"
    ),
    author="Louis Opter",
    author_email="louis@opter.org",
    packages=setuptools.find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "acl-watcher = acl_watcher.__main__:main",
            "watchman-wait = acl_watcher.watchman_wait:main"
        ],
    },
    install_requires=[
        "click",
        "pywatchman",
    ],
)
