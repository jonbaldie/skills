"""Extract validated file paths from unstructured tool payloads.

Keep this module identical in the three independently installed resume skills.
"""

import json
import re


_TOOL_PATH = re.compile(
    r'\*\*\* (?:Update|Add|Delete) File:[ \t]*([^\r\n]*)'
    r'|"(?:path|file_path|filePath)"\s*:\s*("(?:\\.|[^"\\])*")'
)


def paths_from_tool_text(blob: str) -> list[str]:
    paths = []
    for match in _TOOL_PATH.finditer(blob):
        if match.group(2) is not None:
            try:
                path = json.loads(match.group(2))
            except ValueError:
                continue
        else:
            path = match.group(1).split("\\n", 1)[0].strip()
        if (not path.strip() or len(path) > 512 or any(ord(ch) < 32 or ord(ch) == 127 for ch in path)
                or any(ch in path for ch in "{}")):
            continue
        paths.append(path)
    return paths
