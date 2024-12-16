# OutOfSight
Created to encrypt and decrypt pdfs

### [Create a virtual environment in the terminal](https://code.visualstudio.com/docs/python/environments#_create-a-virtual-environment-in-the-terminal)
```shell
# macOS/Linux
# You may need to run `sudo apt-get install python3-venv` first on Debian-based OSs
python3 -m venv .venv

# Windows
# You can also use `py -3 -m venv .venv`
python -m venv .venv
```
After creating the virtual environment ensure that it is used for running commands on the terminal.

### Installing dependencies
```shell
pip install -r requirements.txt
```

### Running
```shell
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --log-level debug --workers 3 --reload
```