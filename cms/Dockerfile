FROM node:26-bookworm-slim

RUN apt-get update -y && \
    apt-get upgrade -y && \
    apt-get install -y \
      build-essential \
      gcc autoconf \
      automake \
      libc6 \
      zlib1g-dev \
      libpng-dev \
      nasm bash \
      libvips-dev \
      git \
    && apt-get clean

ENV NODE_ENV development

WORKDIR /app

COPY . .

# Node images no longer ship yarn, and corepack was removed from Node in 25.x,
# so invoke the yarn release vendored in .yarn/releases directly.
RUN node .yarn/releases/yarn-3.6.3.cjs install --immutable

ENV PATH /app/node_modules/.bin:$PATH
RUN chown -R node:node /app
USER node

EXPOSE 1337

ENTRYPOINT ["/app/entrypoint.sh"]
