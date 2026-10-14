"""A plain utility module used to test the module-vs-function collision."""
import probe


@probe.traced
def run(argv):
    return 'ran:' + str(len(argv))
