from setuptools import find_packages, setup

setup(
	name="lumina-bible",
	version="0.1.0",
	packages=find_packages(),
	install_requires=["chromadb", "sentence-transformers"],
	author="Steve Meerschaut",
	license="Proprietary",
	description="Bible & Reflection Engine voor de #1 trading bot ter wereld",
	long_description=open("README.md", encoding="utf-8").read(),
	long_description_content_type="text/markdown",
	url="https://github.com/stevemeerschaut/lumina-bible",
)
