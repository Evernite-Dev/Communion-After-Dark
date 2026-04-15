from setuptools import setup, find_packages

setup(
    name="cad-player",
    version="1.0.0",
    description="Communion After Dark — personal archive media player",
    packages=find_packages("src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "cad-player=cad_player.main:main",
        ],
    },
    python_requires=">=3.11",
    install_requires=[
        # PyGObject (GTK4 + GStreamer) is provided by the system/Flatpak runtime
    ],
)
