#!/bin/bash
set -e

# Node images no longer ship yarn, and corepack was removed from Node in 25.x,
# so invoke the yarn release vendored in .yarn/releases directly.
yarn="node /app/.yarn/releases/yarn-3.6.3.cjs"

case "${NODE_ENV}" in
    development)
        echo "Running Development Server"
        exec ${yarn} dev
        ;;
    test)
        echo "Running Test"
        exec ${yarn} test
        ;;
    production)
        echo "Import config"
        ${yarn} config-sync import -y
        echo "Running Production Server"
        exec ${yarn} start
        ;;
    *)
        echo "Unknown NODE environment: \"${NODE_ENV}\""
esac
