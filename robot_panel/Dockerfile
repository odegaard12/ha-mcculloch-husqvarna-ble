# Vale para las dos formas de usarlo:
#  - complemento de HA: el builder pasa BUILD_FROM (imagen base de HA)
#  - Docker suelto (Raspberry, NAS...): docker build -t robot-panel robot_panel
ARG BUILD_FROM=alpine:3.22
FROM ${BUILD_FROM}
# aiohttp y certifi de PyPI (las de Alpine se quedan atrás en arreglos de seguridad); cryptography va del sistema
# para no compilarla
RUN apk add --no-cache python3 py3-cryptography py3-pip
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt
COPY server.py push.py run.sh ./
COPY robot ./robot
RUN chmod +x run.sh
EXPOSE 8106
CMD ["/app/run.sh"]
