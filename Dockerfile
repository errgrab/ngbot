FROM alpine:latest
RUN apk add --no-cache python3 py3-pip ffmpeg
WORKDIR /app
COPY requirements.txt /app
RUN pip3 install --break-system-packages --upgrade pip
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt
COPY . .
CMD ["python3", "bot.py"]
