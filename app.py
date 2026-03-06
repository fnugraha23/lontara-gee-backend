import os
import ee
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from google.oauth2 import service_account

# 1. Muat konfigurasi .env
load_dotenv()

app = Flask(__name__)

# --- PERBAIKAN CORS ---
# Gunakan konfigurasi yang lebih terbuka untuk memastikan handshake berhasil
CORS(app) 

# ==========================================
# INISIALISASI GOOGLE EARTH ENGINE
# ==========================================
def init_gee():
    try:
        project_id = os.environ.get('EE_PROJECT_ID')
        private_key_raw = os.environ.get('EE_PRIVATE_KEY')
        service_account_email = os.environ.get('EE_SERVICE_ACCOUNT')

        if private_key_raw and service_account_email:
            # Perbaikan: Mengganti literal '\n' menjadi karakter newline asli
            private_key = private_key_raw.replace('\\n', '\n')
            info = {
                "private_key": private_key,
                "client_email": service_account_email,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            credentials = service_account.Credentials.from_service_account_info(info)
            print("☁️ Menggunakan Kredensial Environment (Production)")
        else:
            # Mode Lokal
            key_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'credentials.json')
            credentials = service_account.Credentials.from_service_account_file(key_path)
            print("💻 Menggunakan Kredensial Lokal (Development)")

        scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/earthengine'])
        ee.Initialize(credentials=scoped_credentials, project=project_id)
        print("✅ Berhasil terhubung ke Google Earth Engine!")
        
    except Exception as e:
        print(f"\n⚠️ Gagal inisialisasi GEE: {e}\n")

init_gee()

# Import modul GEE lokal
try:
    import gee_modules
except ImportError:
    gee_modules = None
    print("⚠️ Peringatan: gee_modules.py tidak ditemukan.")

# ==========================================
# ROUTING / ENDPOINT API
# ==========================================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "success",
        "message": "Backend LontaraGeo (Flask) aktif!"
    })

@app.route('/api/process-image', methods=['POST'])
def process_image():
    try:
        params = request.get_json()
        if not params:
            return jsonify({"status": "error", "error": "No parameters provided"}), 400

        if gee_modules:
            # Memanggil fungsi pemrosesan utama di gee_modules.py
            result = gee_modules.process_satellite_data(params)
            return jsonify(result)
        else:
            return jsonify({"status": "error", "error": "GEE Module missing"}), 500

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

if __name__ == '__main__':
    # Koyeb biasanya menggunakan port yang dinamis
    port = int(os.environ.get("PORT", 8000))
    app.run(debug=False, host='0.0.0.0', port=port)
