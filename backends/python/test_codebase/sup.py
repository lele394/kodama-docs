"""super() and self.* calls have a runtime target a static tool cannot see
through; they must stay VISIBLE as builtin and must not guess a project
target. The `Child()` constructor call DOES resolve to the local class."""
import probe


class Base:
    def __init__(self):
        self.ok = True


class Child(Base):
    def __init__(self):
        super().__init__()
        self.stop()

    def stop(self):
        return 'stopped'


def run():
    c = Child()
    return c.stop()
