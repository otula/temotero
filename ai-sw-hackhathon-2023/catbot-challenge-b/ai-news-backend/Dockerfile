# syntax=docker/dockerfile:1

# Get Node base image
FROM node:12.18.1

# Set prod env for increased performance
ENV NODE_ENV=production

# Copy the package.json files (without other source files)
# so that we can take advantage of docker caching when dependencies do not change!
COPY ["package.json", "package-lock.json*", "./"]

# Install the required npm packages
RUN npm install --production

# Copy all the source files now
COPY ["*.js", "./"]

# Run our service
CMD [ "node", "index.js" ]