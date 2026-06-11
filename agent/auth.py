import json
import os
import pickle
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events'
]


def load_env_file():
    env_path = Path(__file__).resolve().parent.parent / '.env'
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()


def get_token_path():
    configured_path = os.getenv('GOOGLE_TOKEN_PICKLE_PATH', '').strip()
    if configured_path:
        return Path(configured_path).expanduser()
    return Path.home() / '.config' / 'my-own-agent' / 'token.pickle'


def load_credentials_config():
    credentials_value = os.getenv('GOOGLE_CREDENTIALS_JSON', '').strip()
    if credentials_value:
        if credentials_value.startswith('{'):
            return json.loads(credentials_value)
        candidate_path = Path(credentials_value).expanduser()
        if candidate_path.exists():
            with candidate_path.open() as f:
                return json.load(f)

    default_path = Path(__file__).resolve().parent / 'credentials.json'
    if default_path.exists():
        with default_path.open() as f:
            return json.load(f)

    raise RuntimeError('Set GOOGLE_CREDENTIALS_JSON to a JSON object or point it at a credentials.json file.')


def main():
    client_config = load_credentials_config()
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=8080, open_browser=False)

    token_path = get_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with token_path.open('wb') as f:
        pickle.dump(creds, f)

    print(f'✅ Authentication successful — token saved to {token_path}')


if __name__ == '__main__':
    main()