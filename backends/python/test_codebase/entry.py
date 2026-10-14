"""An entry point guarded by `if __name__ == '__main__'` (import-safe)."""
import probe


@probe.traced
def main(argv):
    return len(argv)


def run():
    return main(['x'])


if __name__ == '__main__':
    run()
