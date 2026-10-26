FROM node:22-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends python3 ripgrep unzip curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN npm install -g @openai/codex@0.163.0 opencode-ai@1.19.3 && npm install -g --ignore-scripts @earendil-works/pi-coding-agent@1.3.0
RUN mkdir -p /root/.nvm && printf '# Preinstalled Node 22; no nvm installation needed.\n' > /root/.nvm/nvm.sh
RUN codex --version && opencode --version && pi --version
WORKDIR /app
COPY starter/index.html /app/index.html
RUN git init && git add index.html && git -c user.name=Showdown -c user.email=showdown@example.invalid commit -m "Identical round checkpoint"
