from pathlib import Path
path = Path('frontend/src/components/EditorApp.tsx')
text = path.read_text()
old = 'const EditorApp = () => {\n'
if 'const [zoom' not in text:
    text = text.replace(old, old + '  const [zoom, setZoom] = useState(1);\n', 1)
    path.write_text(text)
