def get_parent(p):
    idx = p.rfind("/")
    if idx == 0:
        return "/"
    return p[:idx]

paths = ["/a", "/a/b", "/a/b/c"]
for p in paths:
    print(f"{p} -> {get_parent(p)}")
