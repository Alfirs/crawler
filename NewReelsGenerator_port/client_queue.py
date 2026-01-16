import requests
import time
import yaml
from pathlib import Path
from datetime import datetime, timedelta

API = "http://127.0.0.1:8000"
PROXIES = {"http": None, "https": None}  # отключаем VPN/прокси


def add_job(kind, payload):
    r = requests.post(f"{API}/jobs", json={"kind": kind, "payload": payload}, proxies=PROXIES)
    r.raise_for_status()
    job_id = r.json()["id"]
    print(f"   ✅ Задача {kind} добавлена, id={job_id}")
    return job_id


def get_job(job_id):
    r = requests.get(f"{API}/jobs/{job_id}", proxies=PROXIES)
    r.raise_for_status()
    return r.json()


def normalize_start(payload: dict):
    """
    Конвертация времени старта:
    - start (фиксированная дата) → оставляем как есть
    - start_time (HH:MM) → ближайшее будущее время
    - start_offset (например, "15m", "2h", "1d") → now + offset
    """
    if "start" in payload:
        return payload

    now = datetime.now()

    if "start_time" in payload:
        hh, mm = map(int, payload["start_time"].split(":"))
        start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if start < now:
            start += timedelta(days=1)
        payload["start"] = start.strftime("%Y-%m-%d %H:%M")
        payload.pop("start_time")
        return payload

    if "start_offset" in payload:
        val = payload.pop("start_offset")
        unit = val[-1]
        num = int(val[:-1])
        if unit == "m":
            start = now + timedelta(minutes=num)
        elif unit == "h":
            start = now + timedelta(hours=num)
        elif unit == "d":
            start = now + timedelta(days=num)
        else:
            raise ValueError(f"Неизвестный формат start_offset: {val}")
        payload["start"] = start.strftime("%Y-%m-%d %H:%M")
        return payload

    # по умолчанию — сразу
    payload["start"] = now.strftime("%Y-%m-%d %H:%M")
    return payload



def run_queue(yaml_file: Path):
    print(f"\n📄 Запуск задач из {yaml_file.name}")
    with yaml_file.open("r", encoding="utf-8") as f:
        jobs = yaml.safe_load(f).get("jobs", [])

    for idx, job in enumerate(jobs, start=1):
        print(f"\n🚀 Задача {idx}/{len(jobs)} ({job['kind']})")
        payload = normalize_start(job["payload"])
        job_id = add_job(job["kind"], payload)

        # ждём выполнения
        while True:
            info = get_job(job_id)
            status = info["status"]
            print(f"   Статус: {status}")
            if status in ("done", "failed"):
                print(f"   ✅ Завершено: {status}")
                if info.get("result"):
                    print(f"   Результат: {info['result']}")
                if status == "failed":
                    print("   ❌ Останавливаем выполнение этого YAML")
                    return False
                break
            time.sleep(5)
    return True


if __name__ == "__main__":
    jobs_dir = Path("jobs")
    yaml_files = sorted(jobs_dir.glob("*.yaml"))

    if not yaml_files:
        print("⚠️  В папке jobs/ нет YAML-файлов")
        exit(0)

    print(f"🔎 Найдено {len(yaml_files)} YAML-файлов")
    for yfile in yaml_files:
        ok = run_queue(yfile)
        if not ok:
            print(f"⏹ Очередь остановлена из-за ошибки в {yfile.name}")
            break

    print("\n🎉 Все очереди выполнены")
