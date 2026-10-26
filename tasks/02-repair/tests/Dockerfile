FROM mcr.microsoft.com/playwright:v1.64.0-noble
WORKDIR /tests
COPY package.json /tests/package.json
RUN npm install --omit=dev --no-audit --no-fund
COPY test.sh verify.cjs /tests/
RUN mkdir -p /app /logs/verifier && chmod +x /tests/test.sh
WORKDIR /app
