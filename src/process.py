import time
import json
from pathlib import Path

IN_PATH = Path('data/raw')
OUT_PATH = Path(f'data/processed/combined_{time.time_ns()}.json')


def combine_results(in_path: Path = IN_PATH, out_path: Path = OUT_PATH):
    out_path.write_text(json.dumps({
        k: v
        for p in in_path.iterdir()
        for k, v in json.loads(p.read_text())['globalObjects']['tweets'].items()
    }, indent=2))


def main() -> int:
    combine_results()
    return 0


if __name__ == '__main__':
    exit(main())
