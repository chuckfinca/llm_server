from setuptools import setup, find_packages

setup(
    name="llm-server",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.115.8",
        "uvicorn>=0.15.0",
        "pydantic>=2.0.0,<3.0.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=0.19.0",
        "pyyaml>=6.0.0",
        "dspy-ai>=2.0.0",
        "prometheus-client>=0.17.0",
        "typing-extensions>=4.0.0",
        "rich>=13.7.1",
        "importlib-metadata>=6.8.0",
        "typer>=0.12.3",
        "cloudpickle>=3.1.1",
    ],
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'python-multipart>=0.0.5',
            'httpx>=0.23.0',
            'email-validator>=2.0.0',
        ],
    },
    python_requires='>=3.9',
    description="A lightweight, extensible server for working with large language models",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author="Charles Feinn",
    author_email="charles@appsimple.io",
    url="https://github.com/chuckfinca/llm-server",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.9",
    ],
)