import os, subprocess, tempfile, uuid

def _esc_text(s: str) -> str:
    # ffmpeg drawtext: экранируем кавычки/двоеточие/обратный слэш
    # и переводим пути в unix-стиль, чтобы не ронять фильтр
    if s is None:
        return ""
    s = s.replace("\\", "/")
    s = s.replace(":", r"\:")
    s = s.replace("'", r"\'")
    return s

def _esc_path(p: str) -> str:
    if not p:
        return ""
    return p.replace("\\", "/")

def overlay_title(
    inp, out, title,
    font_file=None, font_size=72, font_color="white",
    x="(w-text_w)/2", y="h*0.12",
    box=True, box_color="black@0.45", boxborderw=18,
    shadow=True, shadow_color="black", shadow_x=2, shadow_y=2,
):
    # Если заголовка нет — просто копируем
    if not title:
        cmd = f'ffmpeg -y -i "{inp}" -c copy "{out}"'
        subprocess.run(cmd, shell=True, check=True)
        return

    # Шрифт: либо fontfile, либо системный Arial
    font_expr = f":fontfile='{_esc_path(font_file)}'" if font_file else ":font='Arial'"

    title_esc = _esc_text(title)
    x_expr = x or "(w-text_w)/2"
    y_expr = y or "h*0.12"

    # Рисуем тень слоем ниже (смещение), затем основной текст
    shadow_layer = ""
    if shadow:
        shadow_layer = (
            f"drawtext=text='{title_esc}'{font_expr}"
            f":x=({x_expr})+{shadow_x}:y=({y_expr})+{shadow_y}"
            f":fontsize={font_size}:fontcolor={shadow_color}:box=0"
        ) + ","

    main_layer = (
        f"drawtext=text='{title_esc}'{font_expr}"
        f":x={x_expr}:y={y_expr}"
        f":fontsize={font_size}:fontcolor={font_color}"
        f":box={(1 if box else 0)}:boxcolor={box_color}:boxborderw={boxborderw}"
    )

    vf = shadow_layer + main_layer
    cmd = (
        f'ffmpeg -y -i "{inp}" -vf "{vf}" -c:a copy '
        f'-c:v libx264 -preset veryfast -crf 22 "{out}"'
    )
    print("FFMPEG:", cmd)
    subprocess.run(cmd, shell=True, check=True)

def render_reels(inputs, music=None, title=None, out_dir=".", **overlay):
    """
    inputs: список путей к видео
    music: (опц.) путь к музыке
    title: строка
    overlay: любые kwargs для overlay_title (font_file/font_size/font_color/x/y/box/... )
    """
    job_id = uuid.uuid4().hex
    concat = os.path.join(out_dir, f"_{job_id}_concat.mp4")
    mixed  = os.path.join(out_dir, f"_{job_id}_mixed.mp4")
    final  = os.path.join(out_dir, f"{job_id}.mp4")

    # 1) склеим входные видео через concat-list
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        for p in inputs:
            abs_p = os.path.abspath(p)
            f.write(f"file '{_esc_path(abs_p)}'\n")
        list_path = f.name

    cmd_concat = (
        f'ffmpeg -y -f concat -safe 0 -i "{list_path}" '
        f'-c:v libx264 -preset veryfast -crf 23 -c:a aac -b:a 192k "{concat}"'
    )
    print("FFMPEG:", cmd_concat)
    subprocess.run(cmd_concat, shell=True, check=True)

    # 2) подмешаем музыку (если есть). Пока — просто shortest микс.
    if music:
        cmd_mix = (
            f'ffmpeg -y -i "{concat}" -i "{music}" -shortest '
            f'-c:v copy -c:a aac -b:a 192k "{mixed}"'
        )
        print("FFMPEG:", cmd_mix)
        subprocess.run(cmd_mix, shell=True, check=True)
        base = mixed
    else:
        # без музыки — просто копия, чтобы унифицировать путь
        cmd_copy = f'ffmpeg -y -i "{concat}" -c copy "{mixed}"'
        print("FFMPEG:", cmd_copy)
        subprocess.run(cmd_copy, shell=True, check=True)
        base = mixed

    # 3) наложим заголовок
    overlay_title(base, final, title, **overlay)
    return job_id
