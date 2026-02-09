FROM node:20-alpine

WORKDIR /app

# Install server dependencies
COPY package.json ./
RUN npm install --production

# Install frontend dependencies in a location the volume mount won't shadow
COPY frontend/package.json /frontend_deps/package.json
RUN cd /frontend_deps && npm install

EXPOSE 3000

# At startup: assemble a writable build dir from mounted source + pre-installed deps, then build
CMD mkdir -p /build && \
    cp -r /frontend/* /build/ && \
    ln -sf /frontend_deps/node_modules /build/node_modules && \
    cd /build && npm run build && \
    cp -r dist /app/public && \
    cd /app && npm start
