
# AI Game Decompiler


A web app that decompiles Unity (Mono) games and uses Claude on Amazon Bedrock to make the result readable.


## How it works
1. Upload a game folder as .zip (or Assembly-CSharp.dll).
2. ILSpy (ilspycmd) decompiles it to C#.
3. Claude renames identifiers, adds comments and writes OVERVIEW.md.
4. Download the result as a zip. NOTES.txt lists what happened to each file.

## Stack
- AWS EC2 (Ubuntu 24.04), IAM role, Amazon Bedrock
- Python, FastAPI, uvicorn
- ILSpy command line tool on .NET 8
- Nginx reverse proxy (basic auth) and a systemd service


## Files
- main.py: API (upload, status, download) and job processing
- decompile.py: safe unzip, game detection, ILSpy call
- ai.py: Bedrock calls and prompts
- static/index.html: web page
- deploy/: systemd and Nginx configuration

## Setup summary
- Install .NET 8 SDK and ilspycmd (version 9.1.0.7988 works with .NET 8).
- pip install -r requirements.txt
- Give the server an IAM role with Bedrock access and set MODEL to a Bedrock inference profile ID.
- Run with uvicorn behind Nginx.

## Limits
- Only Unity games using the Mono backend are supported.
- Only a limited number of files per run is processed by the AI.
- Only use it on games you own or may analyze.

