# PyInstaller: executavel do agente em modo onedir, sem janela de console.
# Uso (na pasta agent): pyinstaller --noconfirm packaging/PcXControl.spec
from pathlib import Path

AGENT = Path(SPECPATH).parent
ASSETS = AGENT / "pcx_agent" / "assets"

a = Analysis(
    [str(AGENT / "packaging" / "entry.py")],
    pathex=[str(AGENT)],
    datas=[(str(ASSETS), "pcx_agent/assets")],
    hiddenimports=[
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan.on",
        "pystray._win32",
        "win32pdh",
        "pynvml",
    ],
    excludes=["pytest", "httpx", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PcXControl",
    console=False,
    icon=str(ASSETS / "icon.ico"),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="PcXControl", upx=False)
