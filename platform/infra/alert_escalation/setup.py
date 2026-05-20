from setuptools import setup, find_packages

setup(
    name="alert_escalation",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.95.0",
        "uvicorn>=0.21.0",
        "python-dotenv>=0.21.0",
        "pydantic>=1.10.0",
        "requests>=2.28.0",
        "redis>=4.5.0",
        "sentry-sdk>=1.15.0",
        "prometheus-client>=0.16.0",
        "python-json-logger>=2.0.0",
        "croniter>=1.3.0",
        "pytz>=2023.3"
    ],
    entry_points={
        'console_scripts': [
            'alert-escalation=alert_escalation.main:main',
            'escalation-worker=alert_escalation.worker:main'
        ]
    }
)
