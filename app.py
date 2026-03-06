import os
import ee
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from google.oauth2 import service_account

# 1. Muat konfigurasi .env (Hanya untuk penggunaan lokal)
load_dotenv()

app = Flask(__name__)

# 2. Konfigurasi CORS: Izinkan akses dari domain portofolio Anda
CORS(app, resources={r"/api/*": {"origins": ["https://lontara.tech", "http://localhost:5500", "http://127.0.0.1:5500"]}})

# ==========================================
# INISIALISASI GOOGLE EARTH ENGINE
# ==========================================
def init_gee():
    try:
        project_id = os.environ.get('EE_PROJECT_ID')
        
        # Cek apakah kita memiliki kunci privat di Environment Variable (untuk Render)
        # atau melalui file fisik (untuk Lokal)
        private_key_raw = os.environ.get('EE_PRIVATE_KEY')
        service_account_email = os.environ.get('EE_SERVICE_ACCOUNT')

        if private_key_raw and service_account_email:
            # Mode Produksi (Render): Membangun kredensial dari variabel teks
            # Perbaikan: Mengganti literal '\n' menjadi karakter newline asli
            private_key = private_key_raw.replace('\\n', '\n')
            info = {
                "private_key": private_key,
                "client_email": service_account_email,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            credentials = service_account.Credentials.from_service_account_info(info)
            print("☁️ Menggunakan Kredensial dari Environment Variables (Production)")
        else:
            # Mode Lokal: Menggunakan file credentials.json
            key_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'credentials.json')
            if not os.path.exists(key_path):
                raise FileNotFoundError(f"File {key_path} tidak ditemukan untuk inisialisasi lokal.")
            credentials = service_account.Credentials.from_service_account_file(key_path)
            print("💻 Menggunakan Kredensial dari File Lokal (Development)")

        scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/earthengine'])
        ee.Initialize(credentials=scoped_credentials, project=project_id)
        print("✅ Berhasil terhubung ke Google Earth Engine!")
        
    except Exception as e:
        print(f"\n⚠️ Gagal inisialisasi GEE: {e}\n")

init_gee()

# ==========================================
# IMPORT MODUL PEMROSESAN GEE LOKAL
# ==========================================
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

# ==========================================
# JALANKAN SERVER
# ==========================================
if __name__ == '__main__':
    # Render menggunakan port dinamis yang diberikan melalui variabel lingkungan PORT
    port = int(os.environ.get("PORT", 5000))
    # Gunakan debug=False untuk lingkungan produksi (Render)
    app.run(debug=True, host='0.0.0.0', port=port)