# Radary — image tự chứa: engine + API + dashboard + scheduler
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY radary/ radary/
COPY web/ web/
COPY server.py .
# Trong container bind 0.0.0.0 (Docker tự đóng vai tường lửa qua ports mapping)
ENV RADARY_HOST=0.0.0.0 PORT=8000
VOLUME /app/data
EXPOSE 8000
CMD ["python", "server.py"]
