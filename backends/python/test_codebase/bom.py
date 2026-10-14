import probe


@probe.traced
def bom_fn(n):
    return 'bom:' + str(n)


def run():
    return bom_fn(1)
