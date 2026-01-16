import argparse
import asyncio
import os
from getpass import getpass

from telethon import TelegramClient
from telethon.errors import (
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession


async def login_with_code(client: TelegramClient, phone: str) -> bool:
    if not phone:
        print("Phone number is required.")
        return False

    try:
        sent = await client.send_code_request(phone)
        code_type = getattr(sent.type, "__class__", type(sent.type)).__name__
        print(f"Login code sent via: {code_type}")
    except PhoneNumberInvalidError:
        print("Invalid phone number.")
        return False

    code = input("Login code: ").strip()
    try:
        await client.sign_in(phone=phone, code=code)
    except PhoneCodeInvalidError:
        print("Invalid login code.")
        return False
    except PhoneCodeExpiredError:
        print("Login code expired. Please run the script again.")
        return False
    except SessionPasswordNeededError:
        password = getpass("2FA password: ")
        try:
            await client.sign_in(password=password)
        except PasswordHashInvalidError:
            print("Invalid 2FA password.")
            return False

    return True


def write_qr_svg(url: str, path: str) -> bool:
    try:
        import qrcode
        from qrcode.image.svg import SvgImage
    except ImportError:
        print("Install QR support: python -m pip install qrcode")
        return False

    img = qrcode.make(url, image_factory=SvgImage)
    with open(path, "wb") as handle:
        img.save(handle)
    print(f"QR saved to: {path}")
    return True


async def login_with_qr(client: TelegramClient, qr_path: str | None) -> bool:
    qr_login = await client.qr_login()
    print("Open this link in Telegram (or generate a QR code):")
    print(qr_login.url)
    if qr_path:
        write_qr_svg(qr_login.url, qr_path)
    try:
        await qr_login.wait()
    except asyncio.TimeoutError:
        print("QR login expired. Run again and scan быстрее.")
        return False
    except SessionPasswordNeededError:
        password = getpass("2FA password: ")
        try:
            await client.sign_in(password=password)
        except PasswordHashInvalidError:
            print("Invalid 2FA password.")
            return False

    return True


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qr", action="store_true", help="Login using QR code")
    parser.add_argument(
        "--qr-file",
        default="tg_login_qr.svg",
        help="Path to save QR code SVG when using --qr (empty to disable)",
    )
    args = parser.parse_args()

    api_id = os.getenv("TG_API_ID", "").strip()
    api_hash = os.getenv("TG_API_HASH", "").strip()
    if not api_id or not api_hash:
        print("Missing TG_API_ID or TG_API_HASH in environment.")
        return

    try:
        api_id_int = int(api_id)
    except ValueError:
        print("TG_API_ID must be an integer.")
        return

    client = TelegramClient(StringSession(), api_id_int, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        if args.qr:
            qr_path = args.qr_file.strip() if args.qr_file else ""
            ok = await login_with_qr(client, qr_path or None)
        else:
            phone = input("Phone number: ").strip()
            ok = await login_with_code(client, phone)
        if not ok or not await client.is_user_authorized():
            print("Login was not completed.")
            await client.disconnect()
            return

    session = client.session.save()
    print("TG_SESSION_STRING:")
    print(session)
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
