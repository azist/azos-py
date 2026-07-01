import contextlib

class MyCM:
    def __enter__(self):
        print("Enter")
    def __exit__(self, exc_type, exc_value, traceback):
        print("Exit")

cm = MyCM()
print(isinstance(cm, contextlib.AbstractContextManager))
