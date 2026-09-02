import os
from dotenv import load_dotenv
from idp_pegawai import create_app
from idp_pegawai.config import config_dict

load_dotenv()
env_name = os.getenv("FLASK_ENV", os.getenv("FLASK_CONFIG", "production")).lower()
config_class = config_dict.get(env_name, config_dict["default"])
this_app = create_app(config_class)

if __name__ == "__main__":
    port = int(os.getenv("FLASK_RUN_PORT", "9999"))
    this_app.run(host="0.0.0.0", port=port)
