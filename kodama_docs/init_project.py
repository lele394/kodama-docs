"""Create a starter project configuration (`kodama-docs init`)."""
from importlib.resources import files
from pathlib import Path

PROMPT_NAMES = (
    'function.txt',
    'function_chunk.txt',
    'variable.txt',
    'summary.txt',
)


def init_project(directory: str = '.', force: bool = False) -> dict:
    """Write ``settings.yaml`` and the prompt templates into ``directory``.

    Existing files are preserved unless ``force`` is true. Raises
    ``FileExistsError`` when settings.yaml already exists and force is off,
    so a typo in the working directory cannot silently overwrite a config.
    """
    root = Path(directory)
    settings = root / 'settings.yaml'
    if settings.exists() and not force:
        raise FileExistsError(
            f'{settings} already exists (use --force to overwrite it)')

    template = files('kodama_docs').joinpath('default_settings.yaml')
    root.mkdir(parents=True, exist_ok=True)
    settings.write_text(template.read_text(encoding='utf-8'),
                        encoding='utf-8')

    prompts_dir = root / 'prompts'
    prompts_dir.mkdir(parents=True, exist_ok=True)
    created, kept = [], []
    for name in PROMPT_NAMES:
        dest = prompts_dir / name
        if dest.exists() and not force:
            kept.append(name)
            continue
        source = files('prompts').joinpath(name)
        dest.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')
        created.append(name)

    return {'settings': str(settings), 'prompts_dir': str(prompts_dir),
            'created': created, 'kept': kept}
