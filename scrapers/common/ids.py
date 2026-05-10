from slugify import slugify


def slugify_reservoir(name: str) -> str:
    return slugify(name, lowercase=True, separator="-", regex_pattern=r"[^a-z0-9]+")
