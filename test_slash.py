path = "/a/b/////c///"
path = path.strip()
parts = [p.strip() for p in path.split("/") if p.strip()]
print("/" + "/".join(parts) if parts else "/")
