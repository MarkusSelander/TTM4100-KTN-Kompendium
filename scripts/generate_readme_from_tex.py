#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_TEX = REPO_ROOT / "main.tex"
README_MD = REPO_ROOT / "README.md"


def strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = re.sub(r"(?<!\\)%.*$", "", line)
        lines.append(line.rstrip())
    return "\n".join(lines)


def clean_math(text: str) -> str:
    replacements = [
        (r"\\d?frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)"),
        (r"\\binom\{([^{}]+)\}\{([^{}]+)\}", r"C(\1, \2)"),
        (r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)"),
        (r"\\cdot", " * "),
        (r"\\times", " * "),
        (r"\\to", " -> "),
        (r"\\rightarrow", " -> "),
        (r"\\Rightarrow", " => "),
        (r"\\leftrightarrow", " <-> "),
        (r"\\geq", " >= "),
        (r"\\leq", " <= "),
        (r"\\neq", " != "),
        (r"\\approx", " ~= "),
        (r"\\oplus", " xor "),
        (r"\\infty", "infty"),
        (r"\\mu", "mu"),
        (r"\\alpha", "alpha"),
        (r"\\beta", "beta"),
        (r"\\sum_", "sum_"),
        (r"\\text\{([^{}]+)\}", r"\1"),
    ]

    changed = True
    while changed:
        previous = text
        for pattern, repl in replacements:
            text = re.sub(pattern, repl, text)
        changed = text != previous

    text = text.replace(r"\,", "")
    text = text.replace(r"\ ", " ")
    text = text.replace(r"\(", "(")
    text = text.replace(r"\)", ")")
    text = text.replace("{,}", ",")
    text = text.replace("{", "")
    text = text.replace("}", "")
    text = re.sub(r"\\([A-Za-z]+)", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_text_segment(text: str) -> str:
    replacements = [
        (r"\\href\{([^{}]+)\}\{([^{}]+)\}", r"[\2](\1)"),
        (r"\\url\{([^{}]+)\}", r"<\1>"),
        (r"\\texttt\{(.+?)\}", r"`\1`"),
        (r"\\textbf\{(.+?)\}", r"**\1**"),
        (r"\\emph\{(.+?)\}", r"*\1*"),
        (r"\\textit\{(.+?)\}", r"*\1*"),
    ]

    changed = True
    while changed:
        previous = text
        for pattern, repl in replacements:
            text = re.sub(pattern, repl, text)
        changed = text != previous

    text = text.replace(r"\&", "&")
    text = text.replace(r"\%", "%")
    text = text.replace(r"\_", "_")
    text = text.replace(r"\#", "#")
    text = text.replace(r"\$", "$")
    text = text.replace(r"\{", "{")
    text = text.replace(r"\}", "}")
    text = re.sub(r"\\\\+", " ", text)
    text = text.replace("``", '"')
    text = text.replace("''", '"')
    text = text.replace("~", " ")
    text = text.replace(r"\ldots", "...")
    text = text.replace(r"\quad", " ")
    text = text.replace(r"\qquad", "  ")
    text = text.replace(r"\,", " ")
    text = text.replace(r"\;", " ")
    text = text.replace(r"\!", "")
    text = text.replace(r"\ ", " ")
    text = re.sub(r"\\(medskip|smallskip|bigskip|noindent)\b", "", text)
    text = re.sub(r"\\(left|right)\b", "", text)
    text = re.sub(r"\\(textwidth|linewidth|pagebreak|newpage|clearpage)\b", "", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", text)
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def replace_formatting(text: str) -> str:
    parts = re.split(r"(\$\$.*?\$\$|\$.*?\$)", text)
    converted: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("$$") and part.endswith("$$"):
            converted.append(f"$${clean_math(part[2:-2])}$$")
        elif part.startswith("$") and part.endswith("$"):
            converted.append(f"${clean_math(part[1:-1])}$")
        else:
            converted.append(clean_text_segment(part))
    joined = "".join(converted)
    joined = re.sub(r"(?<!\s)(\$[^$]+\$)", r" \1", joined)
    joined = re.sub(r"(\$[^$]+\$)(?![\s\.,;:!\?])", r"\1 ", joined)
    joined = joined.replace("$--", "$ --")
    joined = re.sub(r"\s+", " ", joined)
    return joined.strip()


def remove_block(text: str, env_name: str, replacement: str = "") -> str:
    pattern = re.compile(
        rf"\\begin\{{{env_name}\}}.*?\\end\{{{env_name}\}}",
        re.DOTALL,
    )
    return pattern.sub(replacement, text)


def flatten_box_title(line: str) -> str | None:
    match = re.match(r"\\begin\{(?:keybox|warnbox|formulabox|exambox)\}(?:\[([^\]]+)\])?", line)
    if match:
        title = match.group(1)
        if title:
            return f"**{replace_formatting(title)}**"
        return None

    match = re.match(r"\\begin\{tcolorbox\}\[.*title=([^\],]+).*", line)
    if match:
        return f"**{replace_formatting(match.group(1))}**"

    return None


def convert_tex_body(tex: str) -> str:
    tex = strip_comments(tex)
    tex = remove_block(tex, "tikzpicture", "\n\n_[Diagram omitted in Markdown version.]_\n\n")
    tex = remove_block(tex, "tabular", "\n\n_[Table omitted in Markdown version.]_\n\n")
    tex = remove_block(tex, "longtable", "\n\n_[Table omitted in Markdown version.]_\n\n")

    output: list[str] = []
    list_stack: list[str] = []
    in_code_block = False
    in_math_block = False

    for raw_line in tex.splitlines():
        line = raw_line.strip()
        if not line:
            output.append("")
            continue

        if line.startswith(r"\begin{lstlisting}"):
            in_code_block = True
            output.append("```text")
            continue

        if line.startswith(r"\end{lstlisting}"):
            in_code_block = False
            output.append("```")
            continue

        if in_code_block:
            output.append(raw_line.rstrip())
            continue

        if re.match(r"\\begin\{(?:align\*?|equation\*?|gather\*?)\}", line):
            in_math_block = True
            output.append("$$")
            continue

        if re.match(r"\\end\{(?:align\*?|equation\*?|gather\*?)\}", line):
            in_math_block = False
            output.append("$$")
            output.append("")
            continue

        if in_math_block:
            math_line = re.sub(r"\\\\\[[^\]]+\]$", "", line).strip()
            math_line = math_line.rstrip("\\").strip()
            math_line = math_line.replace("&", "")
            output.append(clean_math(math_line))
            continue

        if line in {r"\begin{center}", r"\end{center}"}:
            continue

        if re.match(r"\\begin\{(?:itemize|enumerate)\}", line):
            list_stack.append("1." if "enumerate" in line else "-")
            continue

        if re.match(r"\\end\{(?:itemize|enumerate)\}", line):
            if list_stack:
                list_stack.pop()
            output.append("")
            continue

        if re.match(r"\\end\{(?:keybox|warnbox|formulabox|exambox|tcolorbox)\}", line):
            output.append("")
            continue

        title = flatten_box_title(line)
        if title is not None:
            output.append("")
            output.append(title)
            output.append("")
            continue

        if line.startswith(r"\section{"):
            output.append(f"### {replace_formatting(line[9:-1])}")
            output.append("")
            continue

        if line.startswith(r"\subsection{"):
            output.append(f"#### {replace_formatting(line[12:-1])}")
            output.append("")
            continue

        if line.startswith(r"\subsubsection{"):
            output.append(f"##### {replace_formatting(line[15:-1])}")
            output.append("")
            continue

        if line == r"\[":
            output.append("$$")
            continue

        if line == r"\]":
            output.append("$$")
            output.append("")
            continue

        item_match = re.match(r"\\item\s*(.*)", line)
        if item_match:
            marker = list_stack[-1] if list_stack else "-"
            indent = "  " * max(len(list_stack) - 1, 0)
            item_text = replace_formatting(item_match.group(1))
            output.append(f"{indent}{marker} {item_text}")
            continue

        if line.startswith(r"\chapterdivider") or line.startswith(r"\input{"):
            continue

        if re.match(r"\\(begin|end)\{.*\}", line):
            continue

        output.append(replace_formatting(line))

    markdown = "\n".join(output)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip() + "\n"


def extract_chapters(main_tex: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        r"\\chapterdivider\{[^}]+\}\{([^}]+)\}\s*\\input\{([^}]+)\}",
        re.MULTILINE,
    )
    return [(title.strip(), chapter.strip()) for title, chapter in pattern.findall(main_tex)]


def build_readme() -> str:
    main_text = MAIN_TEX.read_text(encoding="utf-8")
    chapters = extract_chapters(main_text)

    lines = [
        "# TTM4100 KTN Study Guide",
        "",
        "This README is generated from the LaTeX source files in this repository.",
        "Diagrams and LaTeX-heavy tables are omitted in the GitHub version so the page stays readable.",
        "",
        "To regenerate it, run:",
        "",
        "```bash",
        "python3 scripts/generate_readme_from_tex.py",
        "```",
        "",
        "## Contents",
        "",
    ]

    for title, _chapter in chapters:
        anchor = re.sub(r"[^a-z0-9 -]", "", title.lower()).replace(" ", "-")
        lines.append(f"- [{title}](#{anchor})")

    for title, chapter in chapters:
        chapter_path = REPO_ROOT / f"{chapter}.tex"
        chapter_tex = chapter_path.read_text(encoding="utf-8")
        lines.extend(["", f"## {title}", ""])
        lines.append(convert_tex_body(chapter_tex).rstrip())

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    README_MD.write_text(build_readme(), encoding="utf-8")
    print(f"Updated {README_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
