from __future__ import annotations

import compileall
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def construct_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"Clave YAML duplicada detectada: {key!r}")
        value = loader.construct_object(value_node, deep=deep)
        mapping[key] = value
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    construct_mapping,
)


def validate_yaml() -> bool:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        yaml.load(f, Loader=UniqueKeyLoader)
    print("OK config.yaml sin claves duplicadas.")
    return True


def validate_compile() -> bool:
    ok = compileall.compile_dir(str(ROOT), quiet=1)
    if not ok:
        raise RuntimeError("Falló compileall.")
    print("OK compilación Python.")
    return True


def main() -> int:
    try:
        validate_yaml()
        validate_compile()
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
