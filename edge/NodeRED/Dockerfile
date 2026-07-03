# Digital Twin - Node-RED Edge Gateway
FROM nodered/node-red:4.0

USER root
RUN npm install --omit=dev --ignore-scripts node-red-contrib-modbus@5.45.2 \
    && npm install --omit=dev --ignore-scripts @node-red/nodes@4.0.9
USER node-red
