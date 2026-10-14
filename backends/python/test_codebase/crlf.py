import probe


@probe.traced
def crlf_fn(n):
    return n + 40


def run():
    return crlf_fn(1)
