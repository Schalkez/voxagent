"""Build Windows .exe installer for VoxAgent using PyInstaller."""

from __future__ import annotations

import sys


def build() -> None:
    """Build a standalone Windows executable.

    Requires PyInstaller: pip install pyinstaller
    """
    try:
        import PyInstaller.__main__
    except ImportError:
        print("PyInstaller not installed. Run: pip install pyinstaller")
        sys.exit(1)

    PyInstaller.__main__.run([
        "core/app.py",
        "--name=VoxAgent",
        "--onefile",
        "--windowed",
        "--add-data=../docs;docs",
        "--hidden-import=providers.openai_provider",
        "--hidden-import=providers.groq_provider",
        "--hidden-import=providers.anthropic_provider",
        "--hidden-import=providers.ollama_provider",
        "--hidden-import=providers.deepseek_provider",
        "--hidden-import=providers.mistral_provider",
        "--hidden-import=providers.openrouter_provider",
        "--hidden-import=skills.media_control",
        "--hidden-import=skills.app_launcher",
        "--hidden-import=skills.system_control",
        "--hidden-import=skills.terminal",
        "--hidden-import=skills.file_manager",
        "--hidden-import=skills.browser_control",
        "--hidden-import=skills.screen_reader",
        "--hidden-import=skills.code_reviewer",
    ])


if __name__ == "__main__":
    build()
