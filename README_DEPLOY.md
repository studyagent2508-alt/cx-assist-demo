# CX Assist deployment package

Copy the contents of this folder into the root of the existing `CX Assist`
project. The `src/cx_assist/__init__.py` file can replace the existing empty
file. Keep `.env` local and never commit it.

## Local module test

```powershell
$env:PYTHONPATH = "$PWD\src"
python -c "from cx_assist.api import app; print('Deployment package imports successfully')"
```

## Local API test

```powershell
$env:PYTHONPATH = "$PWD\src"
uvicorn cx_assist.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`.

## Docker build

```powershell
docker build -t cx-assist-demo -f Dockerfile .
```

The container expects environment variables for AWS, S3, the model provider,
and its API key. On AWS App Runner, AWS credentials come from the instance role.

