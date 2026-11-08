"""Cross-platform task runner. `make <task>` calls this; on Windows without make, run
`python tasks.py <task>` directly."""
from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = ROOT / "apps" / "api"
SHARED = ROOT / "packages" / "shared"
WEB = ROOT / "apps" / "web"
MODELS = {
    # Small offline speech models for vosk-browser (Apache 2.0, alphacephei.com).
    "vosk-model-small-en-in-0.4.tar.gz": "https://ccoreilly.github.io/vosk-browser/models/vosk-model-small-en-in-0.4.tar.gz",
    # Published as a zip only; repacked to the tar.gz that vosk-browser loads.
    "vosk-model-small-hi-0.22.tar.gz": "https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip",
}
# Natural offline voices for the agent (Piper, MIT; voices from rhasspy/piper-voices), about 60 MB each.
PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
PIPER_VOICES = ["hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium", "en/en_US/lessac/medium/en_US-lessac-medium"]
VENV = ROOT / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
NPM = "npm.cmd" if os.name == "nt" else "npm"


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    code = subprocess.call([str(c) for c in cmd], cwd=cwd)
    if code:
        sys.exit(code)


def python() -> Path:
    if not PY.exists():
        sys.exit("Python environment not found. Run `python tasks.py install` first.")
    return PY


def install() -> None:
    if not PY.exists():
        venv.create(VENV, with_pip=True)
    run([PY, "-m", "pip", "install", "-q", "-r", API / "requirements.txt"])
    run([NPM, "install", "--silent"], cwd=SHARED)
    run([NPM, "run", "gen:types"], cwd=SHARED)
    run([NPM, "install", "--silent", "--no-audit", "--no-fund"], cwd=WEB)
    if not (API / "nlu" / "models" / "intent.joblib").exists():
        train()
    models()


def models() -> None:
    """Download the offline speech models into apps/web/public/models (about 80 MB). Typed input and
    sample calls work without them."""
    import urllib.request

    target = WEB / "public" / "models"
    target.mkdir(parents=True, exist_ok=True)
    for name, url in MODELS.items():
        path = target / name
        if path.exists() and path.stat().st_size > 1_000_000:
            continue
        print(f"Downloading {name}")
        try:
            if url.endswith(".zip"):
                _zip_to_targz(url, path)
            else:
                urllib.request.urlretrieve(url, path)
        except Exception as exc:  # network is optional at install time
            print(f"  Could not download {name} ({exc}). Offline speech stays off until it is in {target}.")
            path.unlink(missing_ok=True)
    voices = ROOT / "data" / "models" / "piper"
    voices.mkdir(parents=True, exist_ok=True)
    for voice in PIPER_VOICES:
        for ext in (".onnx", ".onnx.json"):
            path = voices / (voice.rsplit("/", 1)[1] + ext)
            if path.exists() and path.stat().st_size > 1000:
                continue
            print(f"Downloading {path.name}")
            try:
                urllib.request.urlretrieve(PIPER_BASE + voice + ext, path)
            except Exception as exc:
                print(f"  Could not download {path.name} ({exc}). The Call desk uses the browser voice until it is in {voices}.")
                path.unlink(missing_ok=True)


def seed() -> None:
    run([python(), "-m", "seed.generate", "--seed", "42", *sys.argv[2:]], cwd=API)


PYDANTIC_FROM = {"order": "order.schema.json", "kot": "kot.schema.json"}


def types() -> None:
    """Generate TypeScript types and Pydantic models from packages/shared/schemas, and export the
    API's OpenAPI document next to them."""
    run([NPM, "run", "gen:types"], cwd=SHARED)
    pydantic_models()
    run([python(), "-m", "contract", "openapi", str(SHARED / "openapi.json")], cwd=API)


def pydantic_models(out_dir: Path | None = None) -> None:
    out_dir = out_dir or API / "schemas" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "__init__.py").write_text('"""Generated from packages/shared/schemas. Run make types."""\n')
    codegen = VENV / ("Scripts/datamodel-codegen.exe" if os.name == "nt" else "bin/datamodel-codegen")
    for name, schema in PYDANTIC_FROM.items():
        run([codegen, "--input", SHARED / "schemas" / schema, "--input-file-type", "jsonschema",
             "--output", out_dir / f"{name}.py", "--output-model-type", "pydantic_v2.BaseModel",
             "--use-annotated", "--field-constraints", "--enum-field-as-literal", "all", "--disable-timestamp",
             "--use-standard-collections", "--use-union-operator", "--target-python-version", "3.11",
             "--custom-file-header", "# Generated from packages/shared/schemas by `make types`. Do not edit."])


def train() -> None:
    run([python(), "-m", "nlu.train_intent"], cwd=API)


def evaluate() -> None:
    run([python(), "-m", "nlu.evaluate", *sys.argv[2:]], cwd=API)


def photos() -> None:
    """Download the dish photos (Wikimedia Commons, free licences) into apps/web/public/dishes."""
    run([python(), "-m", "seed.photos", *sys.argv[2:]], cwd=API)


def simulate() -> None:
    run([python(), "-m", "dialogue.simulate", *sys.argv[2:]], cwd=API)


def _zip_to_targz(url: str, out: Path) -> None:
    import io
    import tarfile
    import urllib.request
    import zipfile
    from pathlib import PurePosixPath

    data = urllib.request.urlopen(url, timeout=120).read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf, tarfile.open(out, "w:gz", format=tarfile.USTAR_FORMAT) as tf:
        files = [i for i in zf.infolist() if not i.is_dir()]
        dirs = sorted({str(PurePosixPath(i.filename).parents[k]) for i in files for k in range(len(PurePosixPath(i.filename).parents) - 1)})
        for d in dirs:  # vosk-browser needs directory entries to recreate the tree
            ti = tarfile.TarInfo(d + "/")
            ti.type, ti.mode = tarfile.DIRTYPE, 0o755
            tf.addfile(ti)
        for info in files:
            ti = tarfile.TarInfo(info.filename)
            ti.size, ti.mode = info.file_size, 0o644
            tf.addfile(ti, zf.open(info))


def dev() -> None:
    """API on :8000 and the web app on :5173. Ctrl+C stops both."""
    api = subprocess.Popen([str(python()), "-m", "uvicorn", "main:app", "--reload", "--port", "8000"], cwd=API)
    try:
        run([NPM, "run", "dev"], cwd=WEB)
    finally:
        api.terminate()


def shots() -> None:
    """Screenshots of every screen for the critique pass. Needs `dev` running."""
    run([NPM, "run", "shots"], cwd=WEB)


def test() -> None:
    run([python(), "-m", "pytest", *sys.argv[2:]], cwd=API)
    run([NPM, "test"], cwd=WEB)
    run([NPM, "run", "typecheck"], cwd=WEB)


TASKS = {"install": install, "models": models, "seed": seed, "train": train, "eval": evaluate, "photos": photos,
         "simulate": simulate, "types": types, "dev": dev, "test": test, "shots": shots}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in TASKS:
        sys.exit(f"usage: python tasks.py [{'|'.join(TASKS)}]")
    TASKS[sys.argv[1]]()
