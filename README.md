
# AI Game Decompiler (version 2)

A web app hosted on AWS that decompiles Unity games and uses
Claude Opus 4.6 on Amazon Bedrock to make the code readable.

## How it works
1. Upload Assembly-CSharp.dll, an Android APK or a zip of the game folder.
2. ILSpy decompiles it to C#. Files are classified (game, library, generated) and ranked.
3. You choose the files. The page shows an estimate of tokens and cost.
4. Big files are split into parts. Claude renames local variables and adds comments.
5. Every AI reply is checked. If a check fails, the original code is kept.
6. Compare before and after in the browser and download the zip
   (with OVERVIEW.md and NOTES.txt).
## Improvements in version 2
- Large files are split into parts instead of skipped.
- Game code is ranked above libraries and generated code.
- Cost estimate and a token limit per run.
- Replies are validated (braces, length, public names).
- Jobs are saved and survive a restart.
- Game-type detection, Unity Android APK support, clear message for IL2CPP.
- Before/after viewer, progress per file, cancel button.

## Stack
AWS EC2, IAM role, Amazon Bedrock, Python, FastAPI, ILSpy (ilspycmd), Nginx, systemd.

## Files
- main.py: web API
- pipeline.py: decompile phase and AI cleanup phase
- detect.py, decompile.py: game-type detection and decompiler tools
- scan.py, chunking.py, validate.py: ranking, splitting and checks
- ai.py, store.py, config.py: AI calls, saved jobs, settings
- static/index.html: web page
- tests/: automated tests (python tests/run_tests.py)
- tools/, update.sh, deploy/: helper scripts and server settings

## Setup (summary)
1. EC2 server (Ubuntu), .NET 8 SDK and ilspycmd, Python venv.
2. pip install -r requirements.txt
3. IAM role with Bedrock access. Set MODEL to a Bedrock inference profile ID.
4. Run with uvicorn behind Nginx as a systemd service (see deploy/).

## Status and limits
Automated tests and initial testing on a real game passed. More QA is still needed.
Only Unity Mono builds are fully supported. IL2CPP and native games are not.

## Legal
Only analyze games you own or are allowed to analyze.
