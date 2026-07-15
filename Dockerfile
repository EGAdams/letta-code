FROM node:20-slim
LABEL archive.note="letta-code (EGAdams fork of letta-ai/letta-code) - node CLI project. Best-effort npm install."
WORKDIR /project
COPY . /project
RUN npm install || echo "npm install failed/partial - source archived regardless"
CMD ["bash"]
