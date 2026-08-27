# Gunakan base image Python yang ringan
FROM python:3.11-slim

# Set working directory di dalam kontainer
WORKDIR /app

# Salin file requirements.txt terlebih dahulu (untuk caching layer)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh sisa kode proyek ke dalam kontainer
COPY . .

# Expose port yang digunakan aplikasi (port 5000)
EXPOSE 5000

# Jalankan aplikasi menggunakan Gunicorn (production server)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]