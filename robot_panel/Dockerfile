# Vale para las dos formas de usarlo:
#  - complemento de HA: el builder pasa BUILD_FROM (imagen base de HA)
#  - Docker suelto (Raspberry, NAS...): docker build -t robot-panel robot_panel
ARG BUILD_FROM=alpine:3.20
FROM ${BUILD_FROM}
RUN apk add --no-cache python3 py3-aiohttp
WORKDIR /app
COPY server.py run.sh ./
COPY robot ./robot
RUN chmod +x run.sh
EXPOSE 8106
CMD ["/app/run.sh"]
