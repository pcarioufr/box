FROM node:20-alpine

WORKDIR /app

# Install server dependencies
COPY package.json ./
RUN npm install --production

# Install frontend dependencies (source mounted at runtime)
COPY frontend/package.json /frontend/package.json
RUN cd /frontend && npm install

EXPOSE 3000

# Build frontend at startup, then start server
CMD cd /frontend && npm run build && cp -r dist /app/public && cd /app && npm start
