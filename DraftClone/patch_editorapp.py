# -*- coding: utf-8 -*-
from pathlib import Path
path = Path('frontend/src/components/EditorApp.tsx')
lines = path.read_text(encoding='utf-8').splitlines()
# We'll rebuild manually
before = lines[:47]
after = lines[70:]  # to remove block from useEffect to later? need manual? this approach messy
