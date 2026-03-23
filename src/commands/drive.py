"""push / pull commands — sync portfolio data to/from Google Drive."""
import os

import click

from drive_client import DriveClient
from helpers import _load_config, console

# Files to sync: (local_path, remote_drive_name)
# Note: drive_token.json is intentionally excluded — it's machine-specific.
SYNC_FILES = [
    ("data/portfolio.db",                   "psx_portfolio.db"),
    ("data/state.json",                     "psx_state.json"),
    ("config/config.yaml",                  "psx_config.yaml"),
    ("credentials/gmail_credentials.json",  "psx_gmail_credentials.json"),
    ("credentials/gmail_token.json",        "psx_gmail_token.json"),
    ("credentials/sheets_credentials.json", "psx_sheets_credentials.json"),
    ("credentials/sheets_token.json",       "psx_sheets_token.json"),
]


def _get_client() -> DriveClient:
    cfg = _load_config().get("drive", {})
    creds = cfg.get("credentials_path", "credentials/sheets_credentials.json")
    token = cfg.get("token_path", "credentials/drive_token.json")
    return DriveClient(creds, token)


@click.command()
def push():
    """Upload local data and config to Google Drive (overwrites remote)."""
    console.print("Connecting to Google Drive…")
    try:
        client = _get_client()
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        return

    console.print(f"Pushing {len(SYNC_FILES)} files to Drive:\n")
    uploaded = 0
    for local_path, remote_name in SYNC_FILES:
        if not os.path.exists(local_path):
            console.print(f"  [yellow]Skipped[/yellow]  {local_path} — not found locally")
            continue
        try:
            client.push_file(local_path, remote_name)
            console.print(f"  [green]OK[/green]  {local_path}")
            uploaded += 1
        except Exception as e:
            console.print(f"  [red]FAILED[/red]  {local_path}: {e}")

    console.print(f"\n[green]Push complete. {uploaded}/{len(SYNC_FILES)} files uploaded.[/green]")


@click.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def pull(yes: bool):
    """Download files from Google Drive to local paths (overwrites local)."""
    if not yes:
        console.print("This will overwrite the following local files with Drive copies:")
        for local_path, _ in SYNC_FILES:
            console.print(f"  {local_path}")
        confirm = click.prompt("\nContinue?", default="N")
        if confirm.strip().lower() not in ("y", "yes"):
            console.print("[yellow]Aborted.[/yellow]")
            return

    console.print("\nConnecting to Google Drive…")
    try:
        client = _get_client()
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        return

    console.print(f"Pulling {len(SYNC_FILES)} files from Drive:\n")
    downloaded = 0
    for local_path, remote_name in SYNC_FILES:
        try:
            found = client.pull_file(remote_name, local_path)
            if found:
                console.print(f"  [green]OK[/green]  {local_path}")
                downloaded += 1
            else:
                console.print(f"  [yellow]Skipped[/yellow]  {local_path} — not on Drive yet")
        except Exception as e:
            console.print(f"  [red]FAILED[/red]  {local_path}: {e}")

    console.print(f"\n[green]Pull complete. {downloaded}/{len(SYNC_FILES)} files downloaded.[/green]")
