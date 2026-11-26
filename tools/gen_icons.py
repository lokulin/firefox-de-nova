#!/usr/bin/env python
"""Generate the old (Proton) icons for Nova Firefox: Proton-only SVGs plus the CSS that applies them.

Firefox ships many icons as one SVG holding two drawings, <g class="proton"> and <g class="nova">,
switched inside the file by @media -moz-pref("browser.nova.enabled"). Stylesheets cannot reach that
switch, but they can point an element at a different file. So this script

  1. writes a Proton-only copy of every such SVG, and
  2. reads Firefox's own skin stylesheets and, for every rule that gives an element one of these icons
     (list-style-image, background-image, content, custom properties, ...), emits the same rule
     pointing at the Proton-only copy. Rules Firefox applies only when Nova is OFF are emitted too, so
     elements that used a different old icon get it back.

Output (in <out>): de-nova-icons/*.svg, de-nova-icons.css (for userChrome.css) and
de-nova-icons-content.css (the same rules limited to about: and chrome: pages, for userContent.css).

Usage (extract Firefox's two omni.ja files first; they are zip archives):
    Expand-Archive <Firefox>\\omni.ja          <dir>\\toolkit
    Expand-Archive <Firefox>\\browser\\omni.ja  <dir>\\browser
    python gen_icons.py <dir>\\toolkit <dir>\\browser <profile>\\chrome

Re-run after a Firefox update.
"""
import re
import sys
from pathlib import Path

SWITCH = "browser.nova.enabled"
OUT_DIR = "de-nova-icons"
STYLE = re.compile(r"<style>.*?</style>\s*", re.S)
NOVA_G = re.compile(r'<g class="nova"[^>]*>.*?</g>\s*', re.S)
COMMENT = re.compile(r"/\*.*?\*/", re.S)
URL = re.compile(r"""url\(\s*(["']?)(chrome://[^)"']+?\.svg)(#[^)"']*)?\1\s*\)""")
PREF_NOT = re.compile(r"""(?:\(\s*not\s+-moz-pref\(\s*"browser\.nova\.enabled"\s*\)\s*\)|not\s+-moz-pref\(\s*"browser\.nova\.enabled"\s*\))\s*(?:and\s+)?""")
PREF_POS = re.compile(r"""(?:\(\s*-moz-pref\(\s*"browser\.nova\.enabled"\s*\)\s*\)|-moz-pref\(\s*"browser\.nova\.enabled"\s*\))\s*(?:and\s+)?""")


# ---------------------------------------------------------------- icons

def proton_only(svg: str):
    if SWITCH not in svg or '<g class="proton"' not in svg:
        return None
    return NOVA_G.sub("", STYLE.sub("", svg))


def chrome_url(skin_root: Path, path: Path):
    skin, *rest = path.relative_to(skin_root).parts
    return f"chrome://{skin}/skin/{'/'.join(rest)}"


def icon_name(url: str) -> str:
    return url.replace("chrome://", "").replace("/skin/", "__").replace("/", "_")


# ---------------------------------------------------------------- CSS parsing

def skip_string(s, i):
    q = s[i]
    i += 1
    while i < len(s) and s[i] != q:
        i += 2 if s[i] == "\\" else 1
    return i


def parse_items(s):
    """Parse a CSS block body into [('decl', text) | ('rule', prelude, items)]. Handles nesting."""
    items, buf, i, n, depth = [], [], 0, len(s), 0
    while i < n:
        c = s[i]
        if c in "\"'":
            j = skip_string(s, i)
            buf.append(s[i:j + 1])
            i = j
        elif c in "([":
            depth += 1
            buf.append(c)
        elif c in ")]":
            depth -= 1
            buf.append(c)
        elif c == ";" and depth == 0:
            text = "".join(buf).strip()
            if text:
                items.append(("decl", text))
            buf = []
        elif c == "{" and depth == 0:
            level, j = 1, i + 1
            while j < n and level:
                if s[j] in "\"'":
                    j = skip_string(s, j)
                elif s[j] == "{":
                    level += 1
                elif s[j] == "}":
                    level -= 1
                j += 1
            items.append(("rule", "".join(buf).strip(), parse_items(s[i + 1:j - 1])))
            buf = []
            i = j - 1
        else:
            buf.append(c)
        i += 1
    text = "".join(buf).strip()
    if text:
        items.append(("decl", text))
    return items


def split_top(s, sep=","):
    parts, buf, depth, i = [], [], 0, 0
    while i < len(s):
        c = s[i]
        if c in "\"'":
            j = skip_string(s, i)
            buf.append(s[i:j + 1])
            i = j
        elif c in "([":
            depth += 1
            buf.append(c)
        elif c in ")]":
            depth -= 1
            buf.append(c)
        elif c == sep and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(c)
        i += 1
    if "".join(buf).strip():
        parts.append("".join(buf).strip())
    return parts


def flatten(parents, child_list):
    """Resolve nested selectors textually (no :is(), so pseudo-elements in parents stay valid)."""
    out = []
    for c in split_top(child_list):
        for p in parents or [None]:
            if p is None:
                out.append(c)
            elif "&" in c:
                out.append(c.replace("&", p))
            else:
                out.append(f"{p} {c}")
    return out


def media_state(query: str):
    """Return (nova-pref state, remaining media condition text). State: 'nova', 'old' or None."""
    if "," in query and SWITCH in query:
        return None, query  # unusual; leave as is
    state, rest = None, query
    if PREF_NOT.search(rest):
        state, rest = "old", PREF_NOT.sub("", rest)
    elif PREF_POS.search(rest):
        state, rest = "nova", PREF_POS.sub("", rest)
    rest = re.sub(r"\s+", " ", rest).strip()
    rest = re.sub(r"\band\s*$", "", rest).strip()
    rest = re.sub(r"^and\b", "", rest).strip()
    return state, rest


# ---------------------------------------------------------------- rule extraction

class Extractor:
    """Replays the icon-setting rules of Firefox's skin stylesheets as they apply with Nova OFF.

    Rules are emitted with !important so they beat Firefox's own. To keep Firefox's specificity and order
    between competing rules, every rule that sets an icon is replayed (not only the two-drawing ones),
    with its original value, and only the two-drawing icons are swapped for the Proton-only copy.
    """

    def __init__(self, icon_urls):
        self.icon_urls = icon_urls
        self.nova, self.base = [], []   # nova-only rules first so Nova-off rules win ties
        self.skipped = []
        self.old = 0

    def swap(self, value):
        """Point two-drawing icons at their Proton-only copy; return (value, swapped?)."""
        swapped = [False]

        def sub(m):
            url, frag = m.group(2), m.group(3) or ""
            if url in self.icon_urls:
                swapped[0] = True
                return f'url("{OUT_DIR}/{icon_name(url)}{frag}")'
            return m.group(0)

        return URL.sub(sub, value), swapped[0]

    def decl(self, text, state):
        if ":" not in text:
            return None
        prop, value = text.split(":", 1)
        prop, value = prop.strip(), re.sub(r"\s*!important\s*$", "", value.strip())
        icon_url = "url(" in value and "chrome://" in value
        # Competing declarations of the same property are replayed whatever their value, so that
        # specificity and order decide between them as they do in Firefox.
        if prop == "list-style-image":
            wanted = True
        elif prop in ("background-image", "mask-image", "-webkit-mask-image"):
            wanted = icon_url or value == "none" or value.startswith("var(")
        else:
            wanted = icon_url
        if not wanted:
            return None
        new, swapped = self.swap(value)
        if state == "nova" and not swapped:
            return None  # Nova-only icon files: leave them to the Nova-off rules
        if prop in ("background", "mask", "-webkit-mask"):
            only = re.findall(r"url\([^)]*\)", new)
            if len(only) == 1 and "," not in new:
                prop = "background-image" if prop == "background" else "mask-image"
                new = only[0]
            else:
                self.skipped.append(text)
                return None
        return f"{prop}: {new} !important"

    def walk(self, items, parents, conds, state, source):
        decls = []
        for it in items:
            if it[0] == "decl" and parents:
                d = self.decl(it[1], state)
                if d:
                    decls.append(d)
        if decls:
            self.old += state == "old"
            (self.nova if state == "nova" else self.base).append((parents, tuple(conds), decls))
        for it in items:
            if it[0] != "rule":
                continue
            _, prelude, children = it
            if prelude.startswith("@"):
                name = prelude.split(None, 1)[0].split("(")[0]
                if name == "@media":
                    st, rest = media_state(prelude[len("@media"):].strip())
                    if st and state and st != state:
                        continue  # unreachable combination
                    c = list(conds) + ([f"@media {rest}"] if rest else [])
                    self.walk(children, parents, c, st or state, source)
                elif name in ("@supports", "@container"):
                    self.walk(children, parents, list(conds) + [prelude], state, source)
                elif name in ("@layer", "@scope"):
                    self.walk(children, parents, conds, state, source)
                # keyframes, font-face, property, etc. are ignored
            else:
                self.walk(children, flatten(parents, prelude), conds, state, source)


def render(rules):
    out, seen = [], set()
    for parents, conds, decls in rules:
        key = (tuple(parents), conds, tuple(decls))
        if key in seen:
            continue
        seen.add(key)
        body = f"{','.join(parents)} {{ {'; '.join(decls)}; }}"
        for cond in reversed(conds):
            body = f"{cond} {{ {body} }}"
        out.append(body)
    return out


# ---------------------------------------------------------------- main

def main(toolkit: Path, browser: Path, out: Path):
    icon_dir = out / OUT_DIR
    icon_dir.mkdir(parents=True, exist_ok=True)
    icons = {}
    skin_roots = [(toolkit / "chrome" / "toolkit" / "skin" / "classic"),
                  (browser / "chrome" / "browser" / "skin" / "classic")]
    for root in skin_roots:
        for f in sorted(root.rglob("*.svg")):
            svg = proton_only(f.read_text(encoding="utf-8", errors="replace"))
            if svg is None:
                continue
            url = chrome_url(root, f)
            icons[url] = icon_name(url)
            (icon_dir / icons[url]).write_text(svg, encoding="utf-8", newline="\n")

    ex = Extractor(icons)
    for root in skin_roots:
        for css in sorted(root.rglob("*.css")):
            text = COMMENT.sub("", css.read_text(encoding="utf-8", errors="replace"))
            ex.walk(parse_items(text), [], [], None, css.name)

    rules = render(ex.nova) + render(ex.base)
    attr = [f'  :is(img, image)[src="{u}"] {{ content: url("{OUT_DIR}/{n}") !important; }}' for u, n in icons.items()]
    header = "/* Generated by tools/gen_icons.py: the old (Proton) icon drawings on Nova Firefox. */\n"
    (out / "de-nova-icons.css").write_text(header + "\n".join(rules + [a.strip() for a in attr]) + "\n",
                                           encoding="utf-8", newline="\n")
    body = "\n".join("  " + r for r in rules) + "\n" + "\n".join(attr)
    (out / "de-nova-icons-content.css").write_text(
        header + '@-moz-document url-prefix("about:"), url-prefix("chrome:") {\n' + body + "\n}\n",
        encoding="utf-8", newline="\n")
    print(f"{len(icons)} icons, {len(rules)} rules ({ex.old} Nova-off rules); "
          f"{len(ex.skipped)} multi-layer declarations skipped")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*(Path(a) for a in sys.argv[1:]))
