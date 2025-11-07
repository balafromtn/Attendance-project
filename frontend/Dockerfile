# Use an official Node.js runtime
FROM node:18-alpine

# Set the working directory inside the container
WORKDIR /app

# Copy package.json (and package-lock.json)
# This lets Docker cache the 'npm install' step
COPY package*.json ./
RUN npm install

# Copy the rest of the frontend code into the container
COPY . .

# Tell Docker what command to run when the container starts
CMD ["npm", "start"]