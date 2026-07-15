# Sistem Permohonan Latihan (Streamlit POC)

Ini adalah permulaan aplikasi permohonan latihan yang dibina menggunakan Streamlit.

Cara jalankan (lokal):

1. Clone repo
2. Buat virtualenv dan pasang kebergantungan:

   pip install -r requirements.txt

3. Jalankan app:

   streamlit run app.py

Nota:
- Ini adalah proof-of-concept. Ia menggunakan SQLite (apps.db) untuk simpan data dan tandatangan dalam bentuk BLOB. Untuk production, pertimbangkan Supabase/Postgres + storan (S3) + auth sebenar.
- Untuk deploy ke Streamlit Cloud: tambah repo ini sebagai aplikasi baru, tetapkan file utama `app.py` dan requirements.
